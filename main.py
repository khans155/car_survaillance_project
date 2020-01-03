import time
import picamera
from picamera.array import PiRGBArray
import datetime as dt
import logging
import json
import cv2
import shlex
import subprocess
import shutil
import imutils
import RPi.GPIO as GPIO
from multiprocessing import Process

recording_len = 10*60           # 10 min video loop
recording = False
ignitionPin = 12
motion_record_len = 5*60        # Minimum 5 min video
logging.basicConfig(filename="messages.log", level=logging.DEBUG)

def action():
    move_motor(250, axisCentered=True)  # Initialize motor, make sure its centered
    global recording
    print('MAIN: Program initiated.')
    logging.debug('MAIN: Program initiated.')
    threadList = []
    while True:
        ignition = check_ignition()
        if ignition:  # This section will record for recording_len on a loop until car ignition is off
            with picamera.PiCamera() as camera:
                camera.resolution = (1280, 720)
                camera.framerate = 30
                time.sleep(1)
                savePath = '/share/Remotecode/ignition_on_recordings/'
                filename = dt.datetime.now().strftime('%d_%m_20%y__%H_%M_%S')
                camera.start_recording(f'{savePath}{filename}.h264', format='h264', bitrate=5000000)
                print(f'Ignition on: New recording started at {filename}...')
                logging.debug(f'Ignition on: New recording started at {filename}...')
                recording = True
                t0 = time.time()
                t1 = time.time()
                while ignition and ((t1 - t0) < recording_len):
                    camera.wait_recording(0.5)
                    ignition = check_ignition()
                    t1 = time.time()
                camera.stop_recording()
                recording = False
                print(f'Ignition on: Recording {filename}.h264 done, starting background conversion into MP4...')
                logging.debug(f'Ignition on: Recording {filename}.h264 done, starting background conversion into MP4...')
                threadList.append(Process(target=convert_video, args=(filename, savePath,)).start())
        else:  # This section checks for motion and records if motion is detected
            move_motor(250, axisCentered=True)
            prev = 250
            width = 500
            camera = picamera.PiCamera()
            camera.resolution = (1280, 720)
            camera.framerate = 30
            rawCapture = PiRGBArray(camera, size=(1280, 720))
            time.sleep(1)
            avg = None
            i = 0
            motion = False
            lostFrames = 10
            t0 = 0
            recordingMotion = False
            switch = False

            while True:
                if motion and not recordingMotion:
                    camera.close()
                    camera = picamera.PiCamera()
                    camera.resolution = (1280, 720)
                    camera.framerate = 30
                    savePath = '/share/Remotecode/sentry_mode_recordings/'
                    filename = dt.datetime.now().strftime('%d_%m_20%y__%H_%M_%S')
                    camera.start_recording(f'{savePath}{filename}.h264', format='h264', bitrate=1000000)
                    rawCapture = PiRGBArray(camera, size=(1280, 720))
                    print(f'Sentry mode: Motion detected. Recording started on {filename}.')
                    logging.debug(f'Sentry mode: Motion detected. Recording started on {filename}.')
                    recordingMotion = True
                for capture in camera.capture_continuous(rawCapture, format='bgr', use_video_port=True):
                    frame = capture.array
                    if i < lostFrames:
                        i += 1
                        rawCapture.truncate(0)
                        continue

                    frame = imutils.resize(frame, width=width)
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    gray = cv2.GaussianBlur(gray, (21, 21), 0)
                    rawCapture.truncate(0)
                    if avg is None:
                        avg = gray.copy().astype("float")
                        rawCapture.truncate(0)
                        continue
                    cv2.accumulateWeighted(gray, avg, 0.5)
                    frameDelta = cv2.absdiff(gray, cv2.convertScaleAbs(avg))
                    thresh = cv2.threshold(frameDelta, 8, 255, cv2.THRESH_BINARY)[1]
                    thresh = cv2.dilate(thresh, None, iterations=5)
                    contours = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    contours = imutils.grab_contours(contours)
                    contourX = 0
                    contourXlen = 0
                    for cnt in contours:
                        if (cv2.contourArea(cnt) < 4000) or (cv2.contourArea(cnt) > 40000):
                            continue
                        (x, y, w, h) = cv2.boundingRect(cnt)
                        contourX += x + w / 2
                        contourXlen += 1
                        motion = True
                    ignition = check_ignition()
                    if recordingMotion and (((time.time() - t0) > motion_record_len) or ignition):
                        try:
                            travelTime = (abs(250 - prev) // 10) * 0.02
                            prev = 250
                            lostFrames = int(travelTime * camera.framerate) + 3
                            i = 0
                            avg = None
                            camera.stop_recording()
                            threadList.append(Process(target=convert_video, args=(filename, savePath,)).start())
                            recordingMotion = False
                            motion = False
                            print('Sentry mode: Recording stopped.')
                            logging.debug('Sentry mode: Recording stopped.')
                            Process(target=move_motor, args=(250, True, )).start()
                            break
                        except Exception:
                            break

                    if not recordingMotion and ignition:
                        switch = True
                        break

                    if contourXlen != 0:
                        contourX = contourX / contourXlen
                        i = 0
                        contourX = (contourX // 10) * 10
                        avg = None
                        Process(target=move_motor, args=(contourX,)).start()
                        contourX = (contourX - 250 + prev) * 0.72222
                        travelTime = (abs(contourX - prev) // 10) * 0.02
                        prev = contourX
                        lostFrames = int(travelTime * camera.framerate) + 3
                        t0 = time.time()
                        break
                if switch:
                    break
            move_motor(250, axisCentered=True)
            cv2.destroyAllWindows()
            camera.close()


def check_ignition():
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(ignitionPin, GPIO.IN)
    if GPIO.input(ignitionPin) == GPIO.HIGH:
        ignition = True
    else:
        ignition = False
    GPIO.cleanup()
    return ignition


def convert_video(filename, savePath):
    with open('video_itinerary.json', 'r') as file:
        videoItinerary = json.load(file)
    videoItinerary.append([filename, savePath])
    command = shlex.split(f'MP4Box -add {savePath}{filename}.h264 {savePath}{filename}.mp4')
    subprocess.check_output(command, stderr=subprocess.STDOUT)
    command = shlex.split(f'rm {savePath}{filename}.h264')
    subprocess.check_output(command, stderr=subprocess.STDOUT)
    print(f'Video Conversion: Conversion of {filename}.h264 into MP4 completed.')
    logging.debug(f'Video Conversion: Conversion of {filename}.h264 into MP4 completed.')
    Process(target=preserve_storage, args=(videoItinerary, )).start()


def preserve_storage(videoItinerary):
    total, used, free = shutil.disk_usage("/")
    total, used, free = total // 2 ** 30, used // 2 ** 30, free // 2 ** 30
    used = 60
    while used > 50 and videoItinerary != []:
        video = videoItinerary[0]
        try:
            command = shlex.split(f'rm {video[1]}{video[0]}.mp4')
            subprocess.check_output(command, stderr=subprocess.STDOUT)
            print(f'Storage Management: {video[1]}{video[0]}.mp4 deleted to preserve storage.')
            logging.debug(f'Storage Management: {video[1]}{video[0]}.mp4 deleted to preserve storage.')
        except subprocess.CalledProcessError:
            print(f'Storage Management: {video[1]}{video[0]}.mp4 not found, removing from itinerary.')
            logging.debug(f'Storage Management: {video[1]}{video[0]}.mp4 not found, removing from itinerary.')
        del videoItinerary[0]

    with open('video_itinerary.json', 'w') as file:
        json.dump(videoItinerary, file)


def move_motor(moveTo, axisCentered=False):
    with open('motor_data.json', 'r') as file:
        prevMotorData = json.load(file)
    frm = prevMotorData[1]
    if axisCentered is True:
        frm = prevMotorData[1]
        motorData = [frm, moveTo]
        with open('motor_data.json', 'w') as file:
            json.dump(motorData, file)
        command = shlex.split(f'python move_motor.py')
        subprocess.check_output(command, stderr=subprocess.STDOUT)
        print('Motor Controller: Motor centered')
        logging.debug('Motor Controller: Motor centered')
    else:
        moveTo = (moveTo - 250 + frm) * 0.72222
        if moveTo > 500:
            motorData = [frm, 500]
        elif moveTo < 0:
            motorData = [frm, 0]
        else:
            motorData = [frm, moveTo]
        with open('motor_data.json', 'w') as file:
            json.dump(motorData, file)
        command = shlex.split(f'python move_motor.py')
        subprocess.check_output(command, stderr=subprocess.STDOUT)


if __name__ == '__main__':
    try:
        action()
    except KeyboardInterrupt:
        pass

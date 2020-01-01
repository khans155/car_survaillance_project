import time
import picamera
from picamera.array import PiRGBArray
import datetime as dt
import json
import cv2
import shlex
import subprocess
import imutils
from multiprocessing import Process

recording_len = 10  # 5 min videos
recording = False
ignition = False


def action():
    move_motor(250, axisCentered=True)  # Initialize motor, make sure its centered
    global ignition
    global recording
    t0 = None
    threadList = []
    while True:
        ignition = check_ignition(ignition)
        if ignition:  # This section will record for recording_len on a loop until car ignition is off
            with picamera.PiCamera() as camera:
                camera.resolution = (1280, 720)
                camera.framerate = 30
                rawCapture = PiRGBArray(camera, size=(1280, 720))
                time.sleep(1)
                savePath = '/home/pi/Desktop/camera/ignition_on_recordings/'
                filename = dt.datetime.now().strftime('%d_%m_20%y__%H_%M_%S')
                camera.start_recording(f'{savePath}{filename}.h264', format='h264', bitrate=1000000)
                print(f'Main: New recording started at {filename}...')
                recording = True
                t0 = time.time()
                t1 = time.time()
                while ignition and ((t1 - t0) < recording_len):
                    camera.wait_recording(0.5)
                    ignition = check_ignition(ignition)
                    t1 = time.time()
                camera.stop_recording()
                recording = False
                print(f'Main: Recording {filename}.h264 done, starting background conversion into MP4...')
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
            breaK = False

            while True:
                if motion and not recordingMotion:
                    camera.close()
                    camera = picamera.PiCamera()
                    camera.resolution = (1280, 720)
                    camera.framerate = 30
                    savePath = '/home/pi/Desktop/camera/sentry_mode_recordings/'
                    filename = dt.datetime.now().strftime('%d_%m_20%y__%H_%M_%S')
                    camera.start_recording(f'{savePath}{filename}.h264', format='h264', bitrate=1000000)
                    rawCapture = PiRGBArray(camera, size=(1280, 720))
                    print('recording started')
                    recordingMotion = True
                for capture in camera.capture_continuous(rawCapture, format='bgr', use_video_port=True):

                    if i < lostFrames:
                        i += 1
                        rawCapture.truncate(0)
                        continue
                    frame = capture.array
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
                    ignition = check_ignition(ignition)
                    if recordingMotion and (((time.time() - t0) > 10) or ignition):
                        try:
                            camera.stop_recording()
                            threadList.append(Process(target=convert_video, args=(filename, savePath,)).start())
                            recordingMotion = False
                            print('recording stopped')
                        except Exception:
                            pass

                    if not recordingMotion and ignition:
                        breaK = True
                        break

                    if contourXlen != 0:
                        contourX = contourX / contourXlen
                        i = 0
                        contourX = (contourX // 10) * 10
                        print(contourX)
                        avg = None
                        Process(target=move_motor, args=(contourX,)).start()
                        contourX = (contourX - 250 + prev) * 0.72222
                        travelTime = (abs(contourX - prev) // 10) * 0.02
                        prev = contourX
                        lostFrames = int(travelTime * camera.framerate) + 3
                        t0 = time.time()
                        break
                if breaK:
                    break
            move_motor(250, axisCentered=True)
            cv2.destroyAllWindows()
            camera.close()


def check_ignition(ignite):
    try:
        with open("ignition_state.json", "r") as file:
            ignite = json.load(file)
        return ignite
    except ValueError:
        return ignite


def convert_video(filename, savePath):
    command = shlex.split(f'MP4Box -add {savePath}{filename}.h264 {savePath}{filename}.mp4')
    output = subprocess.check_output(command, stderr=subprocess.STDOUT)
    command = shlex.split(f'rm {savePath}{filename}.h264')
    output = subprocess.check_output(command, stderr=subprocess.STDOUT)
    print(f'Subprocess: Conversion of {filename}.h264 into MP4 completed.')


def move_motor(moveTo, axisCentered=False):
    if axisCentered is True:
        with open('motor_data.json', 'r') as file:
            prevMotorData = json.load(file)
        frm = prevMotorData[1]
        motorData = [frm, moveTo]
        with open('motor_data.json', 'w') as file:
            json.dump(motorData, file)
        command = shlex.split(f'python move_motor.py')
        output = subprocess.check_output(command, stderr=subprocess.STDOUT)
        print('Motor moved, centered')
    else:
        with open('motor_data.json', 'r') as file:
            prevMotorData = json.load(file)
        frm = prevMotorData[1]
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
        output = subprocess.check_output(command, stderr=subprocess.STDOUT)
        print('motor moved')
        return motorData


def main():
    try:
        action()
    except KeyboardInterrupt:
        pass


main()

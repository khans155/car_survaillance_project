import time
import picamera  # To access camera module
from picamera.array import PiRGBArray  # To capture frames from camera in array form
import datetime as dt  # To keep track of the date
import logging  # For debugging
import json  # For communicating with other scripts and saving data
import cv2  # For visual processing to detect motion
import shlex  # To execute os commands
import subprocess  # To execute os commands
import shutil  # For keeping tack of storage
import imutils  # For frame processing
import RPi.GPIO as GPIO  # To access Raspberry Pi GPIO pins (to move motor and detect ignition state)
from multiprocessing import Process  # To initiate processes in background

recording_len = 10 * 60  # 10 min video loop for ignition on recording
ignitionPin = 12  # Raspberry Pi board location of ignition pin
motorPin = 11  # Raspberry Pi board location of ignition pin
maxStorage = 70  # Maximum storage allowed in GB for video files
motion_record_len = 5 * 60  # Minimum 5 min video for motion detection
logging.basicConfig(filename="/share/Remotecode/program_logs.log", level=logging.DEBUG)


# Main program that runs on loop
def action():  # Initialize motor, make sure its centered
    print('MAIN: Program initiated.')
    logging.debug('MAIN: Program initiated.')
    move_motor(250, axisCentered=True)  # Initialize motor, make sure its centered
    threadList = []  # To keep track of all open threads in case program need to be closed
    ignition = check_ignition()
    convert_left_over_videos()

    while True:
        if ignition:  # This section will record for recording_len on a loop until car ignition is off
            with picamera.PiCamera() as camera:
                camera.resolution = (1280, 720)
                camera.framerate = 30
                time.sleep(1)  # Give time for the camera to warm up
                savePath = '/share/Remotecode/ignition_on_recordings/'
                filename = dt.datetime.now().strftime('%d_%m_20%y__%H_%M_%S')
                camera.start_recording(f'{savePath}{filename}.h264', format='h264', bitrate=5000000)
                add_to_conversion_itinerary([filename, savePath])
                print(f'Ignition on: New recording started at {filename}...')
                logging.debug(f'Ignition on: New recording started at {filename}...')

                t0 = time.time()
                t1 = time.time()
                while ignition and ((t1 - t0) < recording_len):
                    ignition = check_ignition()
                    t1 = time.time()
                camera.stop_recording()

                print(f'Ignition on: Recording {filename}.h264 done, starting background conversion into MP4...')
                logging.debug(
                    f'Ignition on: Recording {filename}.h264 done, starting background conversion into MP4...')

                # Video is converted in the background using multiprocessing so recording starts back up right away.
                threadList.append(Process(target=convert_video, args=(filename, savePath,)).start())
        else:  # This section checks for motion and records if motion is detected
            prev = 250
            width = 500
            camera = picamera.PiCamera()
            camera.resolution = (1280, 720)
            camera.framerate = 30
            rawCapture = PiRGBArray(camera, size=(1280, 720))  # RawCapture object used to process frames in OpenCV
            time.sleep(1)

            # Initiating variables
            avg = None
            i = 0
            motion = False
            lostFrames = 10
            t0 = 0
            recordingMotion = False
            switch = False

            while True:
                if motion and not recordingMotion:  # Camera object must be re-initiated to start recording
                    camera.close()
                    camera = picamera.PiCamera()
                    camera.resolution = (1280, 720)
                    camera.framerate = 30
                    savePath = '/share/Remotecode/sentry_mode_recordings/'
                    filename = dt.datetime.now().strftime('%d_%m_20%y__%H_%M_%S')
                    add_to_conversion_itinerary([filename, savePath])
                    camera.start_recording(f'{savePath}{filename}.h264', format='h264', bitrate=10000000)
                    rawCapture = PiRGBArray(camera, size=(1280, 720))
                    print(f'Sentry mode: Motion detected. Recording started on {filename}.')
                    logging.debug(f'Sentry mode: Motion detected. Recording started on {filename}.')
                    recordingMotion = True

                # Capturing frames from camera stream for visual processing
                for capture in camera.capture_continuous(rawCapture, format='bgr', use_video_port=True):
                    frame = capture.array
                    if i < lostFrames:  # Frames that are ignored when camera moves
                        i += 1
                        rawCapture.truncate(0)
                        continue

                    # Visual processing to detect motion
                    frame = imutils.resize(frame, width=width)  # Resizing frame to desired width
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)  # Removing unneeded color from frame
                    gray = cv2.GaussianBlur(gray, (21, 21), 0)  # Blur frame to remove noise
                    rawCapture.truncate(0)
                    if avg is None:
                        avg = gray.copy().astype("float")
                        rawCapture.truncate(0)
                        continue
                    cv2.accumulateWeighted(gray, avg, 0.5)
                    frameDelta = cv2.absdiff(gray, cv2.convertScaleAbs(avg))
                    thresh = cv2.threshold(frameDelta, 7, 255, cv2.THRESH_BINARY)[1]
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

                    # Conditions for stopping recording
                    ignition = check_ignition()
                    if recordingMotion and (((time.time() - t0) > motion_record_len) or ignition):
                        try:
                            # When recording is stopped motor will be centered again thus lost frames must be calculated
                            # and avg set to None
                            travelTime = (abs(250 - prev) // 10) * 0.02
                            prev = 250
                            lostFrames = int(travelTime * camera.framerate) + 3
                            i = 0
                            avg = None

                            # Stops recording and activates convert_video() function in background
                            camera.stop_recording()
                            threadList.append(Process(target=convert_video, args=(filename, savePath,)).start())

                            # Relevant variables are reset
                            recordingMotion = False
                            motion = False

                            # Log results and move motor in background to save time
                            print('Sentry mode: Recording stopped.')
                            logging.debug('Sentry mode: Recording stopped.')
                            Process(target=move_motor, args=(250, True,)).start()
                            break
                        except Exception:  # For ignoring random errors with stop_recording() method
                            break

                    # Condition for breaking out of for loop and outside while loop
                    if not recordingMotion and ignition:
                        switch = True
                        break

                    # Some processing of x position of detected object to determine where the motor needs to be
                    # moved to and the frames lost in the process
                    if contourXlen != 0:
                        contourX = contourX / contourXlen
                        i = 0
                        contourX = (contourX // 10) * 10
                        avg = None  # Because camera moves to new position
                        Process(target=move_motor, args=(contourX,)).start()

                        # Calculation of frames that need to be ignored and setting new motor position in prev variable
                        contourX = (contourX - 250 + prev) * 0.72222
                        travelTime = (abs(contourX - prev) // 10) * 0.02
                        prev = contourX
                        lostFrames = int(travelTime * camera.framerate) + 3

                        t0 = time.time()  # To keep track of length of recording
                        break
                if switch:
                    break
            move_motor(250, axisCentered=True)  # Centre the camera for ignition recording
            camera.close()


def check_ignition():  # Checks ignition pin for high which indicates ignition is on.
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(ignitionPin, GPIO.IN)
    if GPIO.input(ignitionPin) == GPIO.HIGH:
        ignition = False
    else:
        ignition = True
    GPIO.cleanup()
    return ignition


def add_to_conversion_itinerary(video):
    filename = video[0]
    savePath = video[1]
    readFile = False
    while not readFile:
        try:
            with open('/share/Remotecode/conversion_itinerary.json', 'r') as file:
                conversionItinerary = json.load(file)
                readFile = True
        except ValueError:
            pass
    conversionItinerary.append([filename, savePath])
    writeFile = False
    while not writeFile:
        try:
            with open('/share/Remotecode/conversion_itinerary.json', 'w') as file:
                json.dump(conversionItinerary, file)
                writeFile = True
        except ValueError:
            pass


def convert_video(filename, savePath):  # Converts raw video output from camera.start_recording() playable MP4 format
    with open('/share/Remotecode/video_itinerary.json', 'r') as file:  # Itinerary keeps track of all videos recorded
        videoItinerary = json.load(file)
    videoItinerary.append([filename, savePath])  # Adding the newest video
    # Convert video to MP4 using system installed MP4Box
    command = shlex.split(f'MP4Box -add {savePath}{filename}.h264 {savePath}{filename}.mp4')
    subprocess.check_output(command, stderr=subprocess.STDOUT)
    # Delete H264 file using system rm command
    command = shlex.split(f'rm {savePath}{filename}.h264')
    subprocess.check_output(command, stderr=subprocess.STDOUT)
    readFile = False
    while not readFile:
        try:
            with open('/share/Remotecode/conversion_itinerary.json', 'r') as file:
                conversionItinerary = json.load(file)
                readFile = True
        except ValueError:
            pass
    del conversionItinerary[0]

    writeFile = False
    while not writeFile:
        try:
            with open('/share/Remotecode/conversion_itinerary.json', 'w') as file:
                json.dump(conversionItinerary, file)
                writeFile = True
        except ValueError:
            pass

    # Log results into log file and print to terminal
    print(f'Video Conversion: Conversion of {filename}.h264 into MP4 completed.')
    logging.debug(f'Video Conversion: Conversion of {filename}.h264 into MP4 completed.')
    preserve_storage(videoItinerary)


def convert_left_over_videos():
    with open('/share/Remotecode/conversion_itinerary.json', 'r') as file:
        conversionItinerary = json.load(file)
        readFile = True
    while conversionItinerary:
        print('Main: Converting left over videos from previous session.')
        logging.debug('Main: Converting left over videos from previous session.')
        for video in conversionItinerary:
            filename = video[0]
            savePath = video[1]
            try:
                command = shlex.split(f'MP4Box -add {savePath}{filename}.h264 {savePath}{filename}.mp4')
                subprocess.check_output(command, stderr=subprocess.STDOUT)
                command = shlex.split(f'rm {savePath}{filename}.h264')
                subprocess.check_output(command, stderr=subprocess.STDOUT)
                print(f'Main: Conversion of {filename}.h264 into MP4 completed.')
                logging.debug(f'Main: Conversion of {filename}.h264 into MP4 completed.')
                with open('/share/Remotecode/video_itinerary.json',
                          'r') as file:
                    videoItinerary = json.load(file)
                videoItinerary.append([filename, savePath])
                with open('/share/Remotecode/video_itinerary.json', 'w') as file:
                    json.dump(videoItinerary, file)
            except subprocess.CalledProcessError:
                print(f'Main: Could not convert or delete {video[1]}{video[0]}. Removing from conversion itinerary.')
                logging.debug(f'Main: Could not convert or delete {video[1]}{video[0]}. Removing from conversion '
                              f'itinerary.')
            del conversionItinerary[0]
        print('Main: Converting leftovers done.')
    with open('/share/Remotecode/conversion_itinerary.json', 'w') as file:
        json.dump(conversionItinerary, file)


def preserve_storage(videoItinerary):  # Checks storage and deletes older videos if maximum is exceeded
    total, used, free = shutil.disk_usage("/")
    total, used, free = total // 2 ** 30, used // 2 ** 30, free // 2 ** 30

    # Check if used storage exceeds maximum, ignore if itinerary is empty
    while used > maxStorage and videoItinerary != []:
        video = videoItinerary[0]  # Oldest video in itinerary
        try:
            # Try to remove old video
            command = shlex.split(f'rm {video[1]}{video[0]}.mp4')
            subprocess.check_output(command, stderr=subprocess.STDOUT)
            print(f'Storage Management: {video[1]}{video[0]}.mp4 deleted to preserve storage.')
            logging.debug(f'Storage Management: {video[1]}{video[0]}.mp4 deleted to preserve storage.')
        except subprocess.CalledProcessError:
            # If removing oldest video failed log to log file.
            print(f'Storage Management: {video[1]}{video[0]}.mp4 not found, removing from itinerary.')
            logging.debug(f'Storage Management: {video[1]}{video[0]}.mp4 not found, removing from itinerary.')
        del videoItinerary[0]
        total, used, free = shutil.disk_usage("/")
        total, used, free = total // 2 ** 30, used // 2 ** 30, free // 2 ** 30

    # Update itinerary
    with open('/share/Remotecode/video_itinerary.json', 'w') as file:
        json.dump(videoItinerary, file)


def move_motor(moveTo, axisCentered=False):  # Launches motor_mover.py script which moves motor.
    with open('/share/Remotecode/motor_data.json', 'r') as file:  # File used to communicate with move_motor.py script
        prevMotorData = json.load(file)
    frm = prevMotorData[1]

    if axisCentered is True:  # Moves motor directly to the moveTo value
        frm = prevMotorData[1]
        motorData = [frm, moveTo, motorPin]
        with open('/share/Remotecode/motor_data.json', 'w') as file:
            json.dump(motorData, file)
        command = shlex.split(f'python /share/Remotecode/move_motor.py')
        subprocess.check_output(command, stderr=subprocess.STDOUT)
        print('Motor Controller: Motor centered')
        logging.debug('Motor Controller: Motor centered')

    else:  # Converts moveTo value from camera range to motor range then moves motor.
        # Calculation is based on motor range of motion, frame width, and camera field of view.
        moveTo = (moveTo - 250 + frm) * 0.72222  # 0.72222 factor used to compensate for camera field of view
        if moveTo > 500:  # 500 corresponds to 180 degrees and motor cant move past that
            motorData = [frm, 500, motorPin]
        elif moveTo < 0:  # 0 corresponds to 0 degrees and motor cant move past that
            motorData = [frm, 0, motorPin]
        else:
            motorData = [frm, moveTo, motorPin]
        with open('/share/Remotecode/motor_data.json', 'w') as file:
            json.dump(motorData, file)
        command = shlex.split(f'python /share/Remotecode/move_motor.py')
        subprocess.check_output(command, stderr=subprocess.STDOUT)


if __name__ == '__main__':
    try:
        action()
    except KeyboardInterrupt:
        pass

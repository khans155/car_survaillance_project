import cv2
import time
import imutils
import numpy as np
from picamera.array import PiRGBArray
import picamera
import datetime as dt
import RPi.GPIO as GPIO
from mover import move_motor
from multiprocessing import Process


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
            contourX += x + w/2
            contourXlen += 1
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            motion = True
        cv2.imshow("motion detect", frame)
        key = cv2.waitKey(1) & 0xFF

        if recordingMotion and ((time.time()-t0) > 10):
            try:
                camera.stop_recording()
                recordingMotion = False
                print('recording stopped')
            except Exception:
                pass

        if key == ord('q'):
            breaK = True
            break

        if contourXlen != 0:
            contourX = contourX/contourXlen
            i = 0
            contourX = (contourX//10)*10
            print(contourX)
            avg = None
            Process(target=move_motor, args=(contourX,)).start()
            contourX = (contourX - 250 + prev) * 0.72222
            travelTime = (abs(contourX - prev)//10)*0.02
            prev = contourX
            lostFrames = int(travelTime*camera.framerate) + 3
            t0 = time.time()
            break
    if breaK:
        break
cv2.destroyAllWindows()
camera.close()

# Car Surveillance Project
A project with the aim to create a car surveillance system using a Raspberry Pi, a camera, the OpenCV library, and Python.

## Intro
Initially my goal was to make a simple dash cam system from a camera module and Raspberry Pi board. Searching for
tutorials on how to use the camera module in Python, I came across an article on *pyimagesearch.com* describing how to use
OpenCV, an open source visual processing library, to detect motion by capturing frames from the camera and comparing them to previous frames. Since I had a SG90 servo motor laying around, I thought it would be cool if I made a camera system that detects motion
and rotates towards the motion, recording while doing so. When the car is on the system would go back to being a regular
dashcam that records on a loop.

## Motion Detection
The libraries requiered for motion detection are *picamera*, *picamera.array*, and *OpenCV*. picamera gives us access
to the camera module which is contected to the camera port of the Raspberry Pi. picamera.array contains the class 
*PiRGBArray* which returns frames from the camera as arrays of RGB values. This array format is required to process the frames in OpenCV. OpenCV contains a whole bunch of stuff that can be used to preocess frames. The basic idea is to continously capture frames from the camera in the form of RGB arrays and compare them to previously captured frames to see if there is a big eneough difference, which would in ideal conditions indicate motion. Heres how the comparison is done. 
```python
for capture in camera.capture_continuous(rawCapture, format='bgr', use_video_port=True):
  if avg is None:
      avg = gray.copy().astype("float")
      rawCapture.truncate(0)
      continue
  frame = capture.array
  frame = imutils.resize(frame, width=width)  
  gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) 
  gray = cv2.GaussianBlur(gray, (21, 21), 0)
  cv2.accumulateWeighted(gray, avg, 0.5)
  frameDelta = cv2.absdiff(gray, cv2.convertScaleAbs(avg))
  thresh = cv2.threshold(frameDelta, 7, 255, cv2.THRESH_BINARY)[1]
  thresh = cv2.dilate(thresh, None, iterations=5)
  contours = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
  contours = imutils.grab_contours(contours)
  for cnt in contours:
    if (cv2.contourArea(cnt) < 4000) or (cv2.contourArea(cnt) > 40000):
      continue
    (x, y, w, h) = cv2.boundingRect(cnt)
```

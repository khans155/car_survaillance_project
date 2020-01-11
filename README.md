# Car Surveillance Project
A project with the aim to create a car surveillance system using a Raspberry Pi, a camera, the OpenCV library, and Python.

## Intro
Initially my goal was to make a simple dash cam system from a camera module and Raspberry Pi board. Searching for
tutorials on how to use the camera module in Python, I came across an article on *pyimagesearch.com* describing how to use
OpenCV, an open source visual processing library, to detect motion by capturing frames from the camera and comparing them to previous frames. Since I had a SG90 servo motor laying around, I thought it would be cool if I made a camera system that detects motion
and rotates towards the motion, recording while doing so. When the car is on the system would go back to being a regular
dashcam that records on a loop.

## Motion Detection
The libraries required for motion detection are *picamera*, *imutils*, and *OpenCV*. picamera gives us access
to the camera module which is connected to the camera port of the Raspberry Pi and *picamera.array* contains the class
*PiRGBArray* which returns frames from the camera as arrays of RGB values. This array format is required to process the frames in OpenCV. OpenCV and imutils contains a whole bunch of stuff that can be used to process frames. The basic idea is to continuously capture frames from the camera in the form of RGB arrays and compare them to previously captured frames to see if there is a big enough difference, which would in ideal conditions indicate motion. Here's a simplified explaination of how the comparison is done. 
```python
for capture in camera.capture_continuous(rawCapture, format='bgr', use_video_port=True):
  frame = capture.array
  frame = imutils.resize(frame, width=width)  
  gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) 
  gray = cv2.GaussianBlur(gray, (21, 21), 0)
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
  if contourXlen != 0:
    contourX = contourX / contourXlen
    i = 0
    contourX = (contourX // 10) * 10
```
Each frame that is captured is resized to have a width of 500, to reduce computational time. The frame is then changed to grayscale, to further remove unnecessary data, and blurred to remove some noise that can interfere with detection. The first frame captured is used to initialize the *avg* variable, which is to be the average of previous frames that new frames are compared to. Background subtraction is used to determine the difference in frames, which is performed by the *cv2.absdiff* function by simply taking the difference of the current frame and the average of the previous frames. The *cv2.threshold* function ensures only a big enough difference is detected. The *cv2.findContours* and *imutils.grab_contours* functions create and retrieve contours that bound the areas highlighted by *frameDelta*. The resulting contours are used with *cv2.boundingRect* to determine the x coordinate of the centre of the contours, which are averaged for all contours and stored in *contourX*. contourX is now the value that can be used to determine how the servo motor responds.

Various additions are made to the above code in *main.py* to allow for recording, moving the motor, ignition detection, and stability. One important change that is made is allowing the motion detection to pause while the motor is moving the camera, otherwise that motion is detected. This is done by determining the number of frames that have to be skipped from the time it will take the motor to the new position, and the frame rate of the camera.

## Motor Response To Motion
The servo motor used is SG90 which has a range of motion 0 to 180 degrees. Signals with duty cycles between 2.5% to 12.5% are used to move the motor between 0 and 180 degrees. The relation between the two is linear. The Raspberry Pi I/O pins and the *RPi.GPIO* library is used to communicate with the motor. The value retrieved from the motion detection code (in contourX) is a value between 0 and 500. This value has to be converted to a value of duty cycle inorder to tell the motor where to move. This is done by the equation: `dutyCycle = 0.02 * contourX + 2.5`

The motor is positioned such that the forward direction (front of the car) corresponds to the motors 90 degree position, thus allowing the motor to move 90 degrees towards the left and right of the car. The current position of the motor must be considered when determining where to move the motor to when the camera detects motion. The camera's field of view must also be considered, so that the motor doesn't 'over-turn' in response to motion. For this particular camera, the field of view is stated to be 130 degrees, thus 0 to 500 pixels correspond to 0 to 130 degrees. The *move_motor()* function in *main.py* does these calculations.

### move_motor.py
The script that actually communicates with the motor is located here, separate from the main program. I found it more stable to separate this part of the program, as the motor behaved unpredictably when accessed from the same session twice. The *subprocess* library is used to launch this script from *main.py* and *motor_data.json* is used to communicate between the two programs as well as store the current position of the motor. 

## Ignition Detection
To determine when to switch between looped recording mode and motion detection mode, the program needed a way to detect the ignition of the car. My cars cigarette lighter ports conveniently only provide power when the car ignition is on. The I/O pins of the Raspberry Pi can support a maximum of 3.3V, while the car supplies 12V. Thus, a DC step down converter is used to bring that down to 3.3V.

### check_ignition()
This function from *main.py* returns ignition state of the car and also powers of the Raspberry Pi if it operates on battery power for too long. The function is called throughout the main program at various points to ensure that the car turning on or off changes the program from one mode to another.


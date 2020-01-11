# Car Surveillance Project
A project with the aim to create a car surveillance system using a Raspberry Pi, a camera, the OpenCV library, and Python.

## Intro
Initially my goal was to make a simple dash cam system from a camera module and Raspberry Pi board. Searching for
tutorials on how to use the camera module in Python, I came across an article on *pyimagesearch.com* describing how to use
OpenCV, an open source visual processing library, to detect motion by capturing frames from the camera and comparing them to previous
frames. Since I had a SG90 servo motor laying around, I thought it would be cool if I made a camera system that detects motion
and rotates towards the motion, recording while doing so. When the car is on the system would go back to being a regular
dashcam that records on a loop.

import RPi.GPIO as GPIO
import time
import json


def update_motor():

    with open('motor_data.json', 'r') as file:
        motorData = json.load(file)

    motorPin = motorData[2]
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(motorPin, GPIO.OUT)
    GPIO.output(motorPin, GPIO.LOW)
    sig = None

    increment = 10
    incrementTime = 0.02
    if motorData[0] > motorData[1]:
        increment = -increment

    for pos in range(int(motorData[0]), int(motorData[1]), increment):
        dutyCycle = 0.02 * pos + 2.5
        if sig is None:
            sig = GPIO.PWM(motorPin, 50)
            sig.start(dutyCycle)
            time.sleep(incrementTime)
            continue
        sig.ChangeDutyCycle(dutyCycle)
        time.sleep(incrementTime)
    if sig is not None:
        sig.stop()
        GPIO.cleanup()


update_motor()



import json
import shlex
import subprocess


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
        print('motor moved, axis centered')
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

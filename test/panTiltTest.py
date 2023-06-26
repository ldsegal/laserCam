from adafruit_servokit import ServoKit
from time import sleep

TILT = 0
PAN = 1

HOME_PAN = 90
HOME_TILT = 90
FULL_LEFT = 0
FULL_RIGHT = 180
FULL_DOWN = 50
FULL_UP = 160

panTilt = ServoKit(channels=8)

print("Centered")
panTilt.servo[PAN].angle = HOME_PAN
panTilt.servo[TILT].angle = HOME_TILT
sleep(1)

print("Down & left")
panTilt.servo[PAN].angle = FULL_LEFT
panTilt.servo[TILT].angle = FULL_DOWN
sleep(1)

print("Up & left")
panTilt.servo[PAN].angle = FULL_LEFT
panTilt.servo[TILT].angle = FULL_UP
sleep(1)

print("Up & right")
panTilt.servo[PAN].angle = FULL_RIGHT
panTilt.servo[TILT].angle = FULL_UP
sleep(1)

print("Down & right")
panTilt.servo[PAN].angle = FULL_RIGHT
panTilt.servo[TILT].angle = FULL_DOWN
sleep(1)

print("Centered")
panTilt.servo[PAN].angle = HOME_PAN
panTilt.servo[TILT].angle = HOME_TILT










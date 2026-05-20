from gpio import *
from time import sleep

print("Centered")
center_pan_tilt()
sleep(1)

print("Down & left")
set_pan_tilt(PAN_MIN, TILT_MIN)
sleep(1)

print("Up & left")
set_pan_tilt(PAN_MIN, TILT_MAX)
sleep(1)

print("Up & right")
set_pan_tilt(PAN_MAX, TILT_MAX)
sleep(1)

print("Down & right")
set_pan_tilt(PAN_MAX, TILT_MIN)
sleep(1)

print("Centered")
center_pan_tilt()










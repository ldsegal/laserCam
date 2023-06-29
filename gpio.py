# Handles gpio for laser, led, & PCA9685 servo driver
import RPi.GPIO as gpio
from adafruit_servokit import ServoKit
from state_data import set_laser as set_laser_state

# Pin assignments
LED_PIN = 27
LASER_PIN = 14

# Servo pan/tilt parameters
TILT_IDX = 0
PAN_IDX = 1
TILT_MIN = 50 # down
TILT_CENTER = 85
TILT_MAX = 120 # up
PAN_MIN = 0 # left
PAN_CENTER = 90
PAN_MAX = 180 # right

# Gpio setup
gpio.setmode(gpio.BCM)
gpio.setup(LASER_PIN, gpio.OUT)
gpio.setup(LED_PIN, gpio.OUT)

#PCA9685 servo driver setup
pan_tilt = ServoKit(channels=8)

# Turn indicator led on
def set_indicator_led():
    gpio.output(LED_PIN, gpio.HIGH)

# Turn indicator led off
def clear_indicator_led():
    gpio.output(LED_PIN, gpio.LOW)

# Turn laser on
def set_laser():
    gpio.output(LASER_PIN, gpio.HIGH)
    set_laser_state(True)

# Turn laser off
def clear_laser():
    gpio.output(LASER_PIN, gpio.LOW)
    set_laser_state(False)

# Get servo tilt angle
def get_tilt():
    return pan_tilt.servo[TILT_IDX].angle

# Set servo tilt angle
def set_tilt(angle):
    if TILT_MIN <= angle and angle <= TILT_MAX:
        pan_tilt.servo[TILT_IDX].angle = angle

# Get servo pan angle
def get_pan():
    return pan_tilt.servo[PAN_IDX].angle

# Set servo pan angle
def set_pan(angle):
    if PAN_MIN <= angle and angle <= PAN_MAX:
        pan_tilt.servo[PAN_IDX].angle = angle


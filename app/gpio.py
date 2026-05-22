# Handles gpio for laser, led, & PCA9685 servo driver
import RPi.GPIO as gpio
from adafruit_servokit import ServoKit
import threading

# Pin assignments
LED_PIN = 27
LASER_PIN = 14

# Servo pan/tilt range calibrations
TILT_IDX = 0      # vertical tilting servo (SG90)
PAN_IDX = 1       # horizontal panning servo (MG90S)
TILT_MIN = 50     # down
TILT_CENTER = 85  # vertical center
TILT_MAX = 120    # up
PAN_MIN = 0       # left
PAN_CENTER = 90   # horizontal center
PAN_MAX = 180     # right

# PCA9685 servo PWM driver config
pan_tilt = ServoKit(channels=8)
#pan_tilt.servo[TILT_IDX].pulse_range = (1000, 2000) # SG90
#pan_tilt.servo[PAN_IDX].pulse_range = (1000, 2000) # MG90S
servo_idle_timers = {} # Store idle timers for each servo
servo_pos = {TILT_IDX: TILT_CENTER, PAN_IDX: PAN_CENTER} # Store last known position for each servo


def move_servo(servo_idx: int, angle: int, idle_time: float = 0.1) -> None:
    """
    Performs servo movement. First checks movement is within bounds, then moves servo, and finally sets timer to 'idle' the servo after period of inactivity.
    """
    if not within_bounds(servo_idx, angle):
        return
    if servo_idle_timers.get(servo_idx):
        servo_idle_timers[servo_idx].cancel() # Cancel existing timer
    servo_idle_timers[servo_idx] = threading.Timer(idle_time, idle_servo, args=[servo_idx]) # Create new timer
    pan_tilt.servo[servo_idx].angle = angle # Move servo
    servo_pos[servo_idx] = angle  # Store new commanded position
    servo_idle_timers[servo_idx].start() # Start idle timer

def within_bounds(servo_idx: int, angle: int) -> bool:    
    """
    Checks if angle is within bounds for given servo index.
    """
    if servo_idx == TILT_IDX:
        return TILT_MIN <= angle <= TILT_MAX
    elif servo_idx == PAN_IDX:
        return PAN_MIN <= angle <= PAN_MAX
    return False

def idle_servo(servo_idx: int) -> None:
    """
    Sets servo to idle by disabling PWM signal. Prevents buzzing and jittering.
    """
    pan_tilt.servo[servo_idx].angle = None

def init_gpio() -> None:
    """GPIO setup"""
    gpio.setmode(gpio.BCM)
    gpio.setup(LASER_PIN, gpio.OUT)
    gpio.setup(LED_PIN, gpio.OUT)

    center_pan_tilt() # Center camera
    clear_laser() # Turn off laser

def set_indicator_led() -> None:
    """Turn indicator led on"""
    gpio.output(LED_PIN, gpio.HIGH)

def clear_indicator_led() -> None:
    """Turn indicator led off"""
    gpio.output(LED_PIN, gpio.LOW)

def set_laser() -> None:
    """Turn laser on"""
    gpio.output(LASER_PIN, gpio.HIGH)

def clear_laser() -> None:
    """Turn laser off"""
    gpio.output(LASER_PIN, gpio.LOW)

def get_tilt() -> int:
    """Get servo tilt angle (cached value, not from hardware)"""
    return servo_pos.get(TILT_IDX, TILT_CENTER)

def set_tilt(angle: int) -> None:
    """Set servo tilt angle"""
    move_servo(TILT_IDX, angle)

def get_pan() -> int:
    """Get servo pan angle (cached value, not from hardware)"""
    return servo_pos.get(PAN_IDX, PAN_CENTER)

def set_pan(angle: int) -> None:
    """Set servo pan angle"""
    move_servo(PAN_IDX, angle)

def set_pan_tilt(pan_angle: int, tilt_angle: int) -> None:
    """Set both pan and tilt servos"""
    move_servo(TILT_IDX, tilt_angle)
    move_servo(PAN_IDX, pan_angle)

def center_pan_tilt() -> None:
    """Center both pan and tilt servos"""
    move_servo(TILT_IDX, TILT_CENTER)
    move_servo(PAN_IDX, PAN_CENTER)

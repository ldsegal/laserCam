# Handles gpio for laser, led, & PCA9685 servo driver
import RPi.GPIO
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


class _GPIO():
    """
    Hardware control class. Manages:
    - Laser on/off
    - Indicator LED on/off
    - Servo pan/tilt movement with idle timeout to prevent jittering
    """
    def __init__(self):
        # GPIO pin setup
        RPi.GPIO.setmode(RPi.GPIO.BCM)
        RPi.GPIO.setup(LASER_PIN, RPi.GPIO.OUT)
        RPi.GPIO.setup(LED_PIN, RPi.GPIO.OUT)

        # PCA9685 servo PWM driver config
        self._pan_tilt = ServoKit(channels=8)
        #self._pan_tilt.servo[TILT_IDX].pulse_range = (1000, 2000) # SG90
        #self._pan_tilt.servo[PAN_IDX].pulse_range = (1000, 2000) # MG90S

        # State vars
        self._laser_on = False
        self._led_on = False
        self._servo_pos = {TILT_IDX: TILT_CENTER, PAN_IDX: PAN_CENTER} # Store last known position for each servo
        self._servo_idle_timers = {} # Store idle timers for each servo

        # Set hardware to default states
        self.clear_laser()
        self.clear_indicator_led()
        self.center_pan_tilt()

    @staticmethod
    def _within_bounds(servo_idx: int, angle: int) -> bool:    
        """
        Checks if angle is within bounds for given servo index.
        """
        if servo_idx == TILT_IDX:
            return TILT_MIN <= angle <= TILT_MAX
        elif servo_idx == PAN_IDX:
            return PAN_MIN <= angle <= PAN_MAX
        return False

    def _move_servo(self, servo_idx: int, angle: int, idle_time: float = 0.1) -> None:
        """
        Performs servo movement. First checks movement is within bounds, then moves servo, and finally sets timer to 'idle' the servo after period of inactivity.
        """
        if not self._within_bounds(servo_idx, angle):
            return
        if self._servo_idle_timers.get(servo_idx):
            self._servo_idle_timers[servo_idx].cancel() # Cancel existing timer
        self._servo_idle_timers[servo_idx] = threading.Timer(idle_time, self._idle_servo, args=[servo_idx]) # Create new timer
        self._pan_tilt.servo[servo_idx].angle = angle # Move servo
        self._servo_pos[servo_idx] = angle  # Store new commanded position
        self._servo_idle_timers[servo_idx].start() # Start idle timer

    def _idle_servo(self, servo_idx: int) -> None:
        """
        Sets servo to idle by disabling PWM signal. Prevents buzzing and jittering.
        """
        self._pan_tilt.servo[servo_idx].angle = None

    def set_indicator_led(self) -> None:
        """Turn indicator led on"""
        RPi.GPIO.output(LED_PIN, RPi.GPIO.HIGH)
        self._led_on = True

    def clear_indicator_led(self) -> None:
        """Turn indicator led off"""
        RPi.GPIO.output(LED_PIN, RPi.GPIO.LOW)
        self._led_on = False

    def set_laser(self) -> None:
        """Turn laser on"""
        RPi.GPIO.output(LASER_PIN, RPi.GPIO.HIGH)
        self._laser_on = True

    def clear_laser(self) -> None:
        """Turn laser off"""
        RPi.GPIO.output(LASER_PIN, RPi.GPIO.LOW)
        self._laser_on = False

    def get_tilt(self) -> int:
        """Get servo tilt angle (cached value, not from hardware)"""
        return self._servo_pos.get(TILT_IDX, TILT_CENTER)

    def set_tilt(self, angle: int) -> None:
        """Set servo tilt angle"""
        self._move_servo(TILT_IDX, angle)

    def get_pan(self) -> int:
        """Get servo pan angle (cached value, not from hardware)"""
        return self._servo_pos.get(PAN_IDX, PAN_CENTER)

    def set_pan(self, angle: int) -> None:
        """Set servo pan angle"""
        self._move_servo(PAN_IDX, angle)

    def set_pan_tilt(self, pan_angle: int, tilt_angle: int) -> None:
        """Set both pan and tilt servos"""
        self._move_servo(TILT_IDX, tilt_angle)
        self._move_servo(PAN_IDX, pan_angle)

    def center_pan_tilt(self) -> None:
        """Center both pan and tilt servos"""
        self._move_servo(TILT_IDX, TILT_CENTER)
        self._move_servo(PAN_IDX, PAN_CENTER)

# Singleton GPIO controller instance
gpio = _GPIO()
# Handles gpio for laser, led, & PCA9685 servo driver
import RPi.GPIO
from adafruit_servokit import ServoKit
import threading
import time

# Pin assignments
LED_PIN = 27
LASER_PIN = 14

# Servo pan/tilt range calibrations
TILT_IDX = 0      # Vertical tilting servo (SG90)
PAN_IDX = 1       # Horizontal panning servo (MG90S)
TILT_MIN = 15     # Down
TILT_CENTER = 85  # Vertical center
TILT_MAX = 100    # Up
PAN_MIN = 0       # Left
PAN_CENTER = 90   # Horizontal center
PAN_MAX = 180     # Right
SERVO_IDLE_TIME = 0.2 # Seconds without movement before turning off PWM signal to servo (to prevent buzzing/jittering)
SERVO_UPDATE_DELAY = 0.001 # 1000hz (1ms)


class _Servo():
    """Helper structure to store servo data"""
    position: float
    velocity: float
    idle_timer: threading.Timer | None

    def __init__(self, position=90, velocity=0, idle_timer=None) -> None:
        self.position = position
        self.velocity = velocity
        self.idle_timer = idle_timer


class _GPIO():
    """
    Hardware control class. Manages:
    - Laser on/off
    - Indicator LED on/off
    - Servo pan/tilt movement with idle timeout to prevent jittering
    """
    def __init__(self) -> None:
        # GPIO pin setup
        RPi.GPIO.setmode(RPi.GPIO.BCM)
        RPi.GPIO.setup(LASER_PIN, RPi.GPIO.OUT)
        RPi.GPIO.setup(LED_PIN, RPi.GPIO.OUT)

        # PCA9685 servo PWM driver config
        self._pan_tilt = ServoKit(channels=8)
        self._pan_tilt.servo[TILT_IDX].set_pulse_width_range(1000, 2000) # SG90
        self._pan_tilt.servo[PAN_IDX].set_pulse_width_range(1000, 2000) # MG90S

        # State vars
        self._laser_on = False
        self._led_on = False
        self._servos: list[_Servo] = [
            _Servo(position=TILT_CENTER),  # Ch0 (TILT)
            _Servo(position=PAN_CENTER)   # Ch1 (PAN)
        ]
        self._servo_move_thread = None # Background thread to handle movement while servos are given a velocity

        # Set hardware to default states
        self.set_laser(False)
        self.set_indicator_led(False)
        self.center_pan_tilt()

    @staticmethod
    def _within_bounds(servo_idx: int, angle: float) -> bool:    
        """
        Checks if angle is within bounds for given servo index.
        """
        if servo_idx == TILT_IDX:
            return TILT_MIN <= angle <= TILT_MAX
        elif servo_idx == PAN_IDX:
            return PAN_MIN <= angle <= PAN_MAX
        return False
    
    def _servo_update_loop(self):
        """
        Performs movement for servos with velocity in background thread
        """
        while True:
            vel_zeroed = True
            for idx, servo in enumerate(self._servos):
                if servo.velocity != 0:
                    vel_zeroed = False
                    self._move_servo(idx, servo.position + servo.velocity)

            # Exit when all movement is done
            if vel_zeroed:
                break
            time.sleep(SERVO_UPDATE_DELAY)

    def _move_servo(self, servo_idx: int, angle: float, idle_time: float = SERVO_IDLE_TIME) -> None:
        """
        Performs servo movement to a set position. First checks movement is within bounds, then moves servo, and finally sets timer to 'idle' the servo after period of inactivity.
        """
        servo = self._servos[servo_idx]
        if not servo:
            raise ValueError(f"No servo object found for index: {servo_idx}")
        if not self._within_bounds(servo_idx, angle):
            return
        if servo.idle_timer:
            servo.idle_timer.cancel() # Cancel existing timer
        servo.idle_timer = threading.Timer(idle_time, self._idle_servo, args=[servo_idx]) # Create new timer
        self._pan_tilt.servo[servo_idx].angle = angle # type: ignore    Move servo
        servo.position = angle  # Store new commanded position
        servo.idle_timer.start() # Start idle timer

    def _idle_servo(self, servo_idx: int) -> None:
        """
        Sets servo to idle by disabling PWM signal. Prevents buzzing and jittering.
        """
        self._pan_tilt.servo[servo_idx].angle = None

    def set_pan_tilt_velocity(self, pan_vel: float = 0, tilt_vel: float = 0) -> None:
        """Set PAN/TILT servo movement by velocity"""
        self._servos[TILT_IDX].velocity = tilt_vel
        self._servos[PAN_IDX].velocity = pan_vel
        if self._servo_move_thread is None or not self._servo_move_thread.is_alive():
            if tilt_vel != 0 or pan_vel != 0:
                self._servo_move_thread = threading.Thread(target=self._servo_update_loop)
                self._servo_move_thread.start()

    def get_tilt(self) -> float:
        """Get servo tilt angle (cached value, not from hardware)"""
        return self._servos[TILT_IDX].position

    def set_tilt(self, angle: float) -> None:
        """Set servo tilt angle"""
        self._move_servo(TILT_IDX, angle)

    def get_pan(self) -> float:
        """Get servo pan angle (cached value, not from hardware)"""
        return self._servos[PAN_IDX].position

    def set_pan(self, angle: float) -> None:
        """Set servo pan angle"""
        self._move_servo(PAN_IDX, angle)

    def set_pan_tilt(self, pan_angle: float, tilt_angle: float) -> None:
        """Set both pan and tilt servos"""
        self._move_servo(TILT_IDX, tilt_angle)
        self._move_servo(PAN_IDX, pan_angle)

    def center_pan_tilt(self) -> None:
        """Center both pan and tilt servos"""
        self._move_servo(TILT_IDX, TILT_CENTER)
        self._move_servo(PAN_IDX, PAN_CENTER)

    def set_indicator_led(self, enable: bool) -> None:
        """Toggle indicator led"""
        if enable:
            RPi.GPIO.output(LED_PIN, RPi.GPIO.HIGH)
        else:
            RPi.GPIO.output(LED_PIN, RPi.GPIO.LOW)
        self._led_on = enable

    def get_indicator_led(self) -> bool:
        """Get LED state"""
        return self._led_on

    def set_laser(self, enable: bool) -> None:
        """Toggle laser"""
        if enable:
            RPi.GPIO.output(LASER_PIN, RPi.GPIO.HIGH)
        else:
            RPi.GPIO.output(LASER_PIN, RPi.GPIO.LOW)
        self._laser_on = enable

    def get_laser(self) -> bool:
        """Get laser state"""
        return self._laser_on

    def close(self) -> None:
        """Ensure all background threads are finished for cleanup"""
        for servo in self._servos:
            if servo.idle_timer:
                servo.idle_timer.cancel()
        if self._servo_move_thread:
            self._servo_move_thread.join()

# Singleton GPIO controller instance
gpio = _GPIO()
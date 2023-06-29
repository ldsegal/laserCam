
from flask import Flask, render_template, Response, request
import gevent
import RPi.GPIO as gpio
from camera import Camera
import cv2
from adafruit_servokit import ServoKit
import redis

# Gpio setup
LASER_PIN = 14
LED_PIN = 27
gpio.setmode(gpio.BCM)
gpio.setup(LASER_PIN, gpio.OUT)
gpio.setup(LED_PIN, gpio.OUT)

# Servo pan/tilt setup
TILT = 0
PAN = 1
PAN_MIN = 0 # left
PAN_CENTER = 90
PAN_MAX = 180 # right
TILT_MIN = 50 # down
TILT_CENTER = 85
TILT_MAX = 120 # up
BUTTON_MOVE_ANGLE = 2
pan = PAN_CENTER
tilt = TILT_CENTER
pan_tilt = ServoKit(channels=8)
pan_tilt.servo[PAN].angle = pan
pan_tilt.servo[TILT].angle = tilt

# Redis setup, used to share global data across all workers & connected clients
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Web app setup
GEVENT_SLEEP_TIME = 0.01
app = Flask(__name__)

# Routes
@app.route('/')
def index():
    return render_template('index.html')

def gen_frames(camera):
    while True:
        frame = camera.get_frame()

        # Add crosshair to frame
        if int(redis_client.get('show_crosshair')):
            height, width, _ = frame.shape # Get frame size
            cv2.drawMarker(frame, (width // 2, height // 2), (0, 0, 255), cv2.MARKER_CROSS, 20, 2) # Draw cross

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        gevent.sleep(GEVENT_SLEEP_TIME)
        
@app.route('/video')
def video():
    return Response(gen_frames(Camera()), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/move_servo', methods=['POST'])
def move_servo():
    global pan
    global tilt
    direction = request.json['direction']
    if direction == 'up' and tilt < TILT_MAX:
        tilt += BUTTON_MOVE_ANGLE
    elif direction == 'down' and tilt > TILT_MIN:
        tilt -= BUTTON_MOVE_ANGLE
    elif direction == 'left' and pan > PAN_MIN:
        pan -= BUTTON_MOVE_ANGLE
    elif direction == 'right' and pan < PAN_MAX:
        pan += BUTTON_MOVE_ANGLE
    pan_tilt.servo[PAN].angle = pan
    pan_tilt.servo[TILT].angle = tilt
    return '', 204

@app.route('/toggle_laser', methods=['POST'])
def toggle_laser():
    value = request.json['value']
    if value:
        gpio.output(LASER_PIN, gpio.HIGH)
    else:
       gpio.output(LASER_PIN, gpio.LOW) 
    return '', 204

@app.route('/toggle_crosshair', methods=['POST'])
def toggle_crosshair():
    redis_client.set('show_crosshair', int(request.json['value']))
    return '', 204

# App main entry point
if __name__ == '__main__':

    # Set defaults
    if redis_client.get('show_crosshair') is None:
        redis_client.set('show_crosshair', int(False))

    app.run(host='0.0.0.0', debug=False)

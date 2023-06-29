
from flask import Flask, render_template, Response, request
import gevent
from camera import Camera
from gpio import set_laser, clear_laser, get_tilt, set_tilt, get_pan, set_pan
from state_data import set_crosshair

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
        yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        gevent.sleep(GEVENT_SLEEP_TIME)
        
@app.route('/video')
def video():
    return Response(gen_frames(Camera()), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/move_servo', methods=['POST'])
def move_servo():
    direction = request.json['direction']
    BUTTON_MOVE_ANGLE = 2
    if direction == 'up':
        set_tilt(get_tilt() + BUTTON_MOVE_ANGLE)
    elif direction == 'down':
        set_tilt(get_tilt() - BUTTON_MOVE_ANGLE)
    elif direction == 'left':
        set_pan(get_pan() - BUTTON_MOVE_ANGLE)
    elif direction == 'right':
        set_pan(get_pan() + BUTTON_MOVE_ANGLE)
    return '', 204

@app.route('/toggle_laser', methods=['POST'])
def toggle_laser():
    if request.json['value']:
        set_laser()
    else:
        clear_laser() 
    return '', 204

@app.route('/toggle_crosshair', methods=['POST'])
def toggle_crosshair():
    set_crosshair(request.json['value'])
    return '', 204

# App main entry point
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False)

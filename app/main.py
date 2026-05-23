
from gevent import monkey
monkey.patch_all()  # Patch standard library for gevent compatibility (for WebSockets)

import atexit
from flask import Flask, render_template, request
from flask_socketio import SocketIO
from app.camera import VideoStream
from app.gpio import init_gpio, set_laser, clear_laser

# Global app state data
num_clients = 0

# Web app setup
app = Flask(__name__)
socketio = SocketIO(app, async_mode='gevent', cors_allowed_origins="*") # TODO test without this security setting
init_gpio()   # Initialize GPIO control for laser,servos, & LEDs
stream = VideoStream() # Start camera stream (singleton instance) on app startup

# Routes
@app.route('/')
def index():
    """Serves the main web control interface"""
    return render_template('index.html')

@app.route('/toggle_laser', methods=['POST'])
def toggle_laser():
    if request.json['value']:
        set_laser()
    else:
        clear_laser() 
    return '', 204

@socketio.on('connect')
def handle_connect():
    """New client connected"""
    global num_clients
    num_clients += 1
    print(f'Client connected. Active Viewers: {num_clients}')
    if stream.is_idle():
        stream.start() # Start stream if it was idle

@socketio.on('disconnect')
def handle_disconnect():
    """Client disconnected"""
    global num_clients
    num_clients = max(0, num_clients - 1)
    print(f"Client Disconnected. Active Viewers: {num_clients}")
    if num_clients == 0:
        stream.idle() # Pause stream if no active viewers

@socketio.on('joystick_move')
def handle_joystick_move(data):
    """
    Receives continuous coordinate streams from the frontend joystick
    """
    x = data.get('x', 0)
    y = data.get('y', 0)

@atexit.register
def global_shutdown():
    """Shutdown handler to clean up resources on exit"""
    stream.stop()

# Development testing entry point
if __name__ == '__main__':
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        pass

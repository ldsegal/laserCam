
from gevent import monkey
monkey.patch_all()  # Patch standard library for gevent compatibility (for WebSockets)

import os
import atexit
import threading
from dotenv import load_dotenv
from flask import Flask, render_template, request
from flask_socketio import SocketIO
from app.camera import stream
from app.gpio import gpio
from app.overlays import imageProcessor

# Global app state data
num_clients = 0
stream_idle_timer = None
stream_idle_timeout = 10.0 # Seconds of inactivity before pausing stream

# Web app setup
load_dotenv()
app = Flask(__name__)
socketio = SocketIO(app, async_mode='gevent', cors_allowed_origins="*") # TODO test without this security setting

# Routes
@app.route('/')
def index():
    """Serves the main web control interface"""
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    """New client connected (to login screen)"""
    print('Client Connected. Awaiting password...')

@ app.route('/check_password', methods=['POST'])
def check_password():
    """Simple password check for login"""
    pw = request.json.get('password')
    if pw == os.getenv('PASSWORD'):
        add_client()
        return {'success': True}, 200
    return {'success': False}, 401

def add_client():
    """Add client to stream"""
    global num_clients, stream_idle_timer
    num_clients += 1
    print(f'Client joined. Active Viewers: {num_clients}')
    if stream_idle_timer:
        stream_idle_timer.cancel() # Cancel any existing timer
        stream_idle_timer = None
    if stream.is_idle():
        stream.start() # Start stream if it was idle

@app.route('/set_laser', methods=['POST'])
def set_laser():
    if request.json['value']:
        gpio.set_laser()
    else:
        gpio.clear_laser()
    return '', 204

@app.route('/set_crosshair', methods=['POST'])
def set_crosshair():
    imageProcessor.enable_crosshair(request.json['value'])
    return '', 204

@socketio.on('joystick_move')
def handle_joystick_move(data):
    """
    Receives continuous coordinate streams from the frontend joystick
    """
    x = data.get('x', 0)
    y = data.get('y', 0)

@socketio.on('disconnect')
def handle_disconnect():
    """Client disconnected"""
    global num_clients, stream_idle_timer
    num_clients = max(0, num_clients - 1)
    print(f"Client Disconnected. Active Viewers: {num_clients}")
    if num_clients == 0:
        if stream_idle_timer:
            stream_idle_timer.cancel() # Cancel any existing timer
        stream_idle_timer = threading.Timer(stream_idle_timeout, stream.idle)
        stream_idle_timer.start() # Set timer to idle stream

@atexit.register
def global_shutdown():
    """Shutdown handler to clean up resources on exit"""
    stream.stop()

# Development testing entry point
if __name__ == '__main__':
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)
    except KeyboardInterrupt:
        pass

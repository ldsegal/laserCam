# LaserCam: RaspberryPi Cat Toy
Remote Control Laser Pointer Webserver for RaspberryPi.  

## 🛠 Hardware Used
- Raspberry Pi 4 
- Raspberry Pi Camera Module
- Waveshare Pan-Tilt Pi HAT (PCA9685 I2C Servo Driver, MG90S servo for pan, SG90 servo for tilt)
- 5V laser diode
- Misc status leds 

## 🏗 Architecture
### System Goals
The aim is for the system to feel smooth enough to be able to interact and play with the cats from anywhere, yet stay simple. It should allow for multiple clients to connect simultaneously with video stream latency low enough to control the robotics. Clients can access the web interface from my local network, or externally as a peer connection from zerotier. 

### Backend, Video Pipeline, and State Syncronization
The main application is implemented in Python with a Flask webserver. This allows for very simple code to receive HTTP POST commands from the web interface and control GPIO functions accordingly. 

A Python subprocess captures the camera frames, processing and adding overlays to the stream with openCV, then efficiently encoding with ffmpeg taking advantage of the Pi's dedicated H.264 hardware chip. Standard HTTP websocket streaming with TCP is a bottleneck, we instead send the stream to MediaMTX, a lightweight binary which runs as a relay server, converting the stream to WebRTC format. This gives a much lower latency UDP stream to be delivered back to Flask for display in HTML.

When one client toggles a control option, this update needs to be reflected in the interface for all users. Redis is used to store this state data in a shared memory pool all backend processes can use, and clients can poll for updates.

### Frontend
Nginx acts as a reverse proxy to effeciently serve the frontend from Flask to clients safely and securely.
Bootstrap5 will be used for a responsive layout on both desktop and mobile. NippleJS provides the virtual joystick.

### Data Flow
              +---------------------------------------------------+
              |                 Client Browser                    |
              |   +-------------------+   +-------------------+   |
              |   |   Bootstrap UI    |   | WebRTC Video element| |
              +---+---------+---------+---+---------^---------+---+
                            |                       |
            HTTP POST (Commands)              WebRTC / UDP (SRTP)
                            |                       |
                            v                       |
              +-------------+---------+   +---------+---------+
              |  Flask Server (Port 5000)  | |  MediaMTX Server  |
              +-------------+---------+   |   (Port 8889)     |
                            |             +---------^---------+
                        Read/Write                  |
                            |                    RTSP (H.264)
                            v                       |
              +-------------+---------+   +---------+---------+
              |  Redis State Machine  <---+ OpenCV Streamer   |
              |      (Port 6379)      |   |    & FFmpeg       |
              +-----------------------+   +-------------------+

### Dependencies
- Flask
- Nginx
- opencv-python
- RPi.GPIO
- adafruit-circuitpython-servokit
- Redis
- MediaMTX
- Bootstrap5, NippleJS

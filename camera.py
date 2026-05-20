
import cv2
import time
import requests
import threading
import subprocess
from gpio import set_indicator_led, clear_indicator_led
from state_data import get_crosshair


CAM_INDEX = 0       # Camera device index
CAM_WIDTH = 1280    # Camera capture width
CAM_HEIGHT = 720    # Camera capture height
CAM_FPS = 30        # Camera capture frames per second
BITRATE = "2000k"   # FFmpeg encoding bitrate
ACTIVE_USER_CHECK_INTERVAL = 5 # Seconds between checks for active users
RTSP_OUTPUT = "rtsp://localhost:8554/stream"  # Stream output URL
MEDIA_MTX_API_URL = "http://localhost:9997/v1/stats" # MediaMTX stats endpoint for monitoring active users


class VideoStream:
    """
    Improved camera pipeline:
    - Captures frames with OpenCV
    - Pipes to FFmpeg with H.264 hardware encoding (Raspberry Pi)
    - Streams RTSP to MediaMTX for WebRTC conversion
    """
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def __new__(cls, *args, **kwargs) -> 'VideoStream':
        """Get or create singleton instance"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Video stream initialization"""
        if self._initialized:
            return  # Already initialized
        
        self._idle = False                     # Flag: is camera capture currently paused
        self._wake_event = threading.Event()   # Event to wake capture thread from idle
        self._ffmpeg_process = None            # FFmpeg subprocess for encoding stream

        # Start background camera capture thread
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()

        self.check_users_active() # Start monitoring for active users
        self._initialized = True

    @staticmethod
    def _draw_crosshair(frame):
        """Draw crosshair marker on frame"""
        height, width, _ = frame.shape
        cv2.drawMarker(frame, (width // 2, height // 2), (0, 0, 255), cv2.MARKER_CROSS, 20, 2)

    @staticmethod
    def _get_ffmpeg_command(width=CAM_WIDTH, height=CAM_HEIGHT, fps=CAM_FPS, bitrate=BITRATE):
        """
        Build FFmpeg command for hardware-accelerated H.264 encoding
        Pipes raw frames to FFmpeg via stdin, outputs RTSP to MediaMTX
        """
        return [
            'ffmpeg',
            '-f', 'rawvideo',
            '-pixel_format', 'bgr24',
            '-video_size', f'{width}x{height}',
            '-framerate', str(fps),
            '-i', 'pipe:0',  # stdin
            '-c:v', 'h264_v4l2m2m',  # Raspberry Pi hardware encoder
            '-b:v', bitrate,
            '-preset', 'veryfast',
            '-f', 'rtsp',
            RTSP_OUTPUT,
        ]
    
    def check_users_active(self):
        """Idles the stream if no users are currently active, checks on a regular interval"""
        try:
            resp = requests.get(MEDIA_MTX_API_URL, timeout=5)
            paths = resp.json().get('paths', {})
            users_active = paths.get('camera', {}).get('readers', {}).get('rtsp', 0) > 0

            # Set status
            if users_active:
                set_indicator_led()
                self._idle = False
                self._wake_event.set() # Wake capture thread if it was idle
            else:
                clear_indicator_led()
                self._idle = True

        except Exception as e:
            print(f'ERROR: Failed to reach MediaMTX to check active users: {e}')

        # Schedule the next check (Recurring Timer)
        user_monitor_thread = threading.Timer(ACTIVE_USER_CHECK_INTERVAL, self.check_users_active)
        user_monitor_thread.daemon = True # Ensure thread closes when main script exits
        user_monitor_thread.start()

    def _capture_loop(self):
        """Main capture thread: OpenCV -> FFmpeg -> MediaMTX"""

        # Open camera
        camera = cv2.VideoCapture(CAM_INDEX, cv2.CAP_V4L2) # Open camera
        if not camera.isOpened():
            print('ERROR: Could not open camera device')
            return
        
        # Apply camera settings
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)
        camera.set(cv2.CAP_PROP_FPS, CAM_FPS)
        print('Camera thread started, intializing FFmpeg pipeline...')
        
        try:
            # Start FFmpeg subprocess
            self._ffmpeg_process = subprocess.Popen(
                self._get_ffmpeg_command(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print(f'FFmpeg streaming to {RTSP_OUTPUT}')

            # Main capture loop
            while camera.isOpened():

                # Wait for active clients
                if self._idle:
                    self._wake_event.wait()
                    self._wake_event.clear()
                    print('Video stream resumed')

                # Capture frame
                ret, frame = camera.read()
                if not ret:
                    print('ERROR: Failed to read frame from camera')
                    time.sleep(0.1)
                    continue
                
                # Draw overlays
                if get_crosshair():
                    self._draw_crosshair(frame)
                
                # Send frame to FFmpeg stdin
                try:
                    assert self._ffmpeg_process and self._ffmpeg_process.stdin
                    self._ffmpeg_process.stdin.write(frame.tobytes())
                except (BrokenPipeError, OSError):
                    print('ERROR: FFmpeg process disconnected')
                    break

                # Yield CPU time
                time.sleep(0.001)
                
        finally:
            # Cleanup FFmpeg
            if self._ffmpeg_process and self._ffmpeg_process.stdin:
                try:
                    self._ffmpeg_process.stdin.close()
                    self._ffmpeg_process.wait(timeout=5)
                except:
                    self._ffmpeg_process.kill()
            
            # Cleanup camera access
            camera.release()
            clear_indicator_led()
            print('Camera pipeline shut down')

    def stop(self):
        """Stop capture thread"""
        if self._capture_thread:
            self._capture_thread.join(timeout=5)





import cv2
import time
import requests
import threading
import subprocess
from picamera2 import Picamera2
from gpio import set_indicator_led, clear_indicator_led
from state_data import get_crosshair


CAM_INDEX = 0       # Camera device index
CAM_WIDTH = 1280    # Camera capture width
CAM_HEIGHT = 720    # Camera capture height
CAM_FPS = 30        # Camera capture frames per second
BITRATE = "2M"      # FFmpeg encoding bitrate
ACTIVE_USER_CHECK_INTERVAL = 5 # Seconds between checks for active users
RTSP_OUTPUT = "rtsp://localhost:8554/stream"  # Stream output URL
MEDIA_MTX_API_URL = "http://localhost:9997/v3/paths/list" # MediaMTX stats endpoint for monitoring active users


class VideoStream:
    """
    Improved camera pipeline:
    - Captures frames with OpenCV
    - Pipes to FFmpeg with H.264 hardware encoding (Raspberry Pi)
    - Streams RTSP to MediaMTX for WebRTC conversion
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls) -> 'VideoStream':
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
        
        self._cam = Picamera2()                # Picamera2 instance
        self._idle = False                     # Flag: is camera capture currently paused
        self._shutdown = False                 # Flag: signal capture thread to shutdown
        self._wake_event = threading.Event()   # Event to wake capture thread from idle
        self._ffmpeg_process = None            # FFmpeg subprocess for encoding stream

        # Configure camera settings
        self._cam.configure(
            self._cam.create_video_configuration(
            main={"size": (CAM_WIDTH, CAM_HEIGHT), "format": "BGR888"}, 
            controls={"FrameRate": CAM_FPS})
        )
        if not self._cam.is_open:
            print('ERROR: Failed to open camera')
            return
        print('Camera configured, starting capture...')
        self._start_stream() # Start the stream!

        # Start background camera capture thread
        self._capture_thread = threading.Thread(target=self._capture_loop)
        self._capture_thread.start()

        self.users_active = 0 # Track current number of viewers
        #self._check_viewers() # Start monitoring for viewers
        self._initialized = True

    @staticmethod
    def _draw_crosshair(frame) -> None:
        """Draw crosshair marker on frame"""
        height, width, _ = frame.shape
        cv2.drawMarker(frame, (width // 2, height // 2), (0, 0, 255), cv2.MARKER_CROSS, 20, 2)

    @staticmethod
    def _get_ffmpeg_command(width=CAM_WIDTH, height=CAM_HEIGHT, fps=CAM_FPS, bitrate=BITRATE) -> list:
        """
        Build FFmpeg command for hardware-accelerated H.264 encoding
        Pipes raw frames to FFmpeg via stdin, outputs RTSP to MediaMTX
        """
        return [
            'ffmpeg',
            '-f', 'rawvideo',
            '-pixel_format', 'rgb24',
            '-video_size', f'{width}x{height}',
            '-framerate', str(fps),
            '-i', 'pipe:0',  # stdin
            '-c:v', 'h264_v4l2m2m',  # Raspberry Pi hardware encoder
            '-b:v', bitrate,
            '-preset', 'veryfast',
            '-f', 'rtsp',
            RTSP_OUTPUT,
        ]
    
    def _start_stream(self) -> None:
        """Start the video stream"""

        # Start camera 
        if not self._cam.started:
            self._cam.start()
            print('Camera started')

        # Start FFmpeg subprocess
        if self._ffmpeg_process is None or self._ffmpeg_process.poll() is not None:
            self._ffmpeg_process = subprocess.Popen(
                self._get_ffmpeg_command(),
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f'FFmpeg streaming to {RTSP_OUTPUT}')

        set_indicator_led() # Indicate stream is active

    def _pause_stream(self) -> None:
        """Pause the video stream (idle mode)"""
        
        # Shutdown ffmpeg process gracefully
        if self._ffmpeg_process and self._ffmpeg_process.stdin:
            try:
                self._ffmpeg_process.stdin.close()
            except Exception:
                pass
            try:
                self._ffmpeg_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._ffmpeg_process.kill()
                self._ffmpeg_process.wait()
            self._ffmpeg_process = None
            print("FFmpeg encoding process stopped")

        # Stop camera capture
        if self._cam.started:
            self._cam.stop()
            print('Camera stopped')

        clear_indicator_led() # Indicate stream is paused

    def _end_stream(self) -> None:
        """End the video stream and clean up resources"""
        self._pause_stream()

        # Close camera to release resource
        try:
            self._cam.close()
        except RuntimeError as e:
            # picamera2 tries to close non-existent preview window (headless) and throws exception, ignore this
            if str(e) == 'Unable to stop preview.':
                pass
            else:
                raise
        print('Camera closed')

    def _check_viewers(self) -> None:
        """Updates active viewer count and idles the stream if zero, checks on a regular interval"""

        # Check MediaMTX stats endpoint for active clients
        try:
            resp = requests.get(MEDIA_MTX_API_URL, timeout=1)
            if resp.status_code == 200:
                print(resp.json())
                self.users_active = len(resp.json().get('items', [])[0].get('readers', []))
            else:
                print(f'ERROR: MediaMTX api endpoint returned status {resp.status_code}')
        except Exception as e:
            print(f'ERROR: Failed to reach MediaMTX to check active viewers: {e}')

        # Set status
        if self.users_active:
            set_indicator_led()
            self._idle = False
            self._wake_event.set() # Wake capture thread if it was idle
        else:
            clear_indicator_led()
            self._idle = True

        # Schedule the next check (recurring timer)
        if not self._shutdown:
            user_monitor_thread = threading.Timer(ACTIVE_USER_CHECK_INTERVAL, self._check_viewers)
            user_monitor_thread.daemon = True # Ensure thread closes when main script exits
            user_monitor_thread.start()

    def _capture_loop(self) -> None:
        """Main capture thread: Picamera2 -> OpenCV -> FFmpeg -> MediaMTX"""
        try:
            while self._cam.is_open:

                # Check for stop signal
                if self._shutdown:
                    break

                # Wait for active clients
                if self._idle:
                    self._pause_stream()
                    self._wake_event.wait()
                    if self._shutdown:
                        break
                    self._start_stream()
                    self._wake_event.clear()
                    self._idle = False

                # Capture frame
                frame = self._cam.capture_array()
                if frame is None:
                    print('ERROR: Failed to read frame from camera')
                    time.sleep(0.1)
                    continue
                
                # Draw overlays
                #if get_crosshair():
                #    self._draw_crosshair(frame)
                
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
            print('Capture thread stopped')

    def stop(self) -> None:
        """Stop capture thread and end video stream"""
        self._shutdown = True
        self._wake_event.set() # Wake thread if it's paused
        self._capture_thread.join()
        self._end_stream()





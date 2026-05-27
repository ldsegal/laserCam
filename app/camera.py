
import time
import threading
import subprocess
from picamera2 import Picamera2
from app.overlays import imageProcessor
from app.gpio import gpio


CAM_INDEX = 0       # Camera device index
CAM_WIDTH = 1640    # Camera capture width
CAM_HEIGHT = 922    # Camera capture height
CAM_FPS = 30        # Camera capture frames per second
BITRATE = "2M"      # FFmpeg encoding bitrate
RTSP_OUTPUT = "rtsp://localhost:8554/laserCam"  # Stream output URL
MEDIA_MTX_API_URL = "http://localhost:9997/v3/paths/list" # MediaMTX stats endpoint for monitoring active users


class _VideoStream:
    """
    Improved camera pipeline:
    - Captures frames with Picamera2
    - Overlays & frame processing with OpenCV
    - Pipes to FFmpeg with H.264 hardware encoding (Raspberry Pi)
    - Streams RTSP to MediaMTX for WebRTC conversion
    """
    def __init__(self) -> None:
        """Video stream initialization"""
        self._cam = Picamera2()                # Picamera2 instance
        self._idle = True                      # Flag: is camera capture currently paused
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
        print('Camera configured, ready to start...')

        # Start background camera capture thread
        self._capture_thread = threading.Thread(target=self._capture_loop)
        self._capture_thread.start()

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

        gpio.set_indicator_led(True) # Indicate stream is active

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

        gpio.set_indicator_led(False) # Indicate stream is paused

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

    def _capture_loop(self) -> None:
        """Main capture thread: Picamera2 -> OpenCV -> FFmpeg -> MediaMTX"""
        try:
            while self._cam.is_open and not self._shutdown:

                # Wait for active clients
                if self._idle:
                    self._pause_stream()
                    self._wake_event.wait()
                    if self._shutdown:
                        break
                    self._start_stream()
                    self._wake_event.clear()

                # Capture frame
                frame = self._cam.capture_array()
                if frame is None:
                    print('ERROR: Failed to read frame from camera')
                    time.sleep(0.1)
                    continue
                
                # Draw overlays
                imageProcessor.draw_overlays(frame)
                
                # Send frame to FFmpeg stdin
                try:
                    assert self._ffmpeg_process and self._ffmpeg_process.stdin
                    self._ffmpeg_process.stdin.write(frame.tobytes())
                except (BrokenPipeError, OSError):
                    if not self._shutdown:
                        print('Error writing frame: FFmpeg process disconnected')
                    break

                # Yield CPU time
                time.sleep(0.001)
                
        finally:
            print('Capture thread stopped')

    def is_idle(self) -> bool:
        """Is the stream currently idle (paused)"""
        return self._idle

    def start(self) -> None:
        """Start the stream"""
        self._idle = False
        self._wake_event.set()

    def idle(self) -> None:
        """Pause the stream (idle mode)"""
        self._idle = True

    def close(self) -> None:
        """Stop capture thread and end video stream"""
        self._shutdown = True
        self._wake_event.set() # Wake thread if it's paused
        self._capture_thread.join()
        self._end_stream()

# Singleton VideoStream instance
stream = _VideoStream()

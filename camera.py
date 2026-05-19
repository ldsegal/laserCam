
import time
import threading
import cv2
from gpio import set_indicator_led, clear_indicator_led
from state_data import get_crosshair

INACTIVE_TIMEOUT = 5  # Pause capture if no client accesses for N seconds
CAMERA_INDEX = 0      # Camera device index
FRAME_ENCODE_QUALITY = 90  # JPEG quality (1-100)


class Camera:
    """
    Singleton manager for camera stream.
    - Runs one background thread that captures frames continuously
    - Pauses capture if no clients request frames for INACTIVE_TIMEOUT seconds
    - Resumes capture when client reconnects
    - Broadcasts latest frame to all connected clients (no queuing)
    """
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def __new__(cls, *args, **kwargs) -> 'Camera':
        """Get or create singleton instance"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Camera manager initialization"""
        if self._initialized:
            return  # Already initialized
        self._current_frame = b''              # Latest captured JPEG frame (bytes)
        self._last_client_access = time.time() # Timestamp of last get_frame() call
        self._idle = False                     # Flag: is camera capture currently paused
        self._wake_event = threading.Event()   # Event to wake capture thread from idle

        # Start background camera capture thread
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()
        self._initialized = True

    @staticmethod
    def _draw_crosshair(frame):
        """Draw crosshair marker on frame"""
        height, width, _ = frame.shape
        cv2.drawMarker(frame, (width // 2, height // 2), (0, 0, 255), cv2.MARKER_CROSS, 20, 2)

    def _capture_loop(self):
        """
        Main background camera thread loop
        """
        camera = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2) # Open camera
        if camera is not None:
            print('Camera thread started...')
            while camera.isOpened():

                # Wait for active clients
                if self._idle:
                    self._wake_event.wait()
                    self._wake_event.clear()
                    self._idle = False
                    set_indicator_led()
                    print('Camera capture resumed')

                # Capture and encode frame
                ret, frame = camera.read()
                if not ret:
                    print('ERROR: Failed to read frame from camera')
                    time.sleep(0.1)
                    continue
                
                # Draw overlays
                if get_crosshair():
                    self._draw_crosshair(frame)
                
                # Encode to JPEG
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, FRAME_ENCODE_QUALITY])
                if not ret:
                    print('ERROR: Failed to encode frame')
                    continue
                
                # Store frame for clients
                self._current_frame = buffer.tobytes()

                # Check for inactivity timeout
                if time.time() - self._last_client_access > INACTIVE_TIMEOUT:
                    self._idle = True
                    clear_indicator_led()
                    print('Camera capture paused due to inactivity')

                # Yield CPU time
                time.sleep(0.001)
                
            # Cleanup on shutdown
            if camera:
                camera.release()
            clear_indicator_led()
        else:
            print('ERROR: Could not open camera device')

    def get_frame(self):
        """
        Get current camera frame for a client
        """
        self._last_client_access = time.time()
        if self._idle:
            self._wake_event.set()  # Wake capture thread if idle
        return self._current_frame

    def stop(self):
        """Stop capture thread and cleanup"""
        if self._capture_thread:
            self._capture_thread.join(timeout=5)




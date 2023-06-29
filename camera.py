# Camera classes to enable video streaming to multiple clients
# Based on https://github.com/miguelgrinberg/flask-video-streaming/blob/master/base_camera.py
import time
import threading
import cv2


# An event-like class to signal all active clients when a new frame is available
class CameraEvent():
    
    def __init__(self):
        self.events = {}

    # Invoked from each client's thread to wait for next frame
    def wait(self):
        ident = threading.get_ident()
        if ident not in self.events:
            self.events[ident] = [threading.Event(), time.time()] # New client, add their event & timestamp
        return self.events[ident][0].wait() # Wait until this client's event is set

    # Invoked by the camera thread when a new frame is available
    def set(self):
        now = time.time()
        remove = None

        for ident, event in self.events.items():
            if not event[0].isSet():
                event[0].set() # Set this client's event
                event[1] = now # Update this client's last timestamp
            else:
                # Client did not read a previous frame, after 5 secs assume client is gone and remove
                if now - event[1] > 5:
                    remove = ident
        if remove:
            del self.events[remove]

    # Invoked from each client's thread after a frame is read
    def clear(self):
        self.events[threading.get_ident()][0].clear()


# Class to handle camera background thread and supply image frames
class Camera():
    thread = None # Camera background thread to get frames
    frame = None # Current frame
    last_access = 0 # Time of last client access
    event = CameraEvent()

    # Start camera background thread if not running
    def __init__(self):
        if Camera.thread is None:
            Camera.last_acess = time.time()
            Camera.thread = threading.Thread(target=self._thread)
            Camera.thread.start()
            Camera.event.wait() # Wait until first frame is available

    # Return the current camera frame
    def get_frame(self):
        Camera.last_access = time.time()
        Camera.event.wait()
        Camera.event.clear()
        return Camera.frame

    # Generates new frames from the camera
    @staticmethod
    def frames():
        camera = cv2.VideoCapture(0, cv2.CAP_V4L2)
        if not camera.isOpened():
            raise RuntimeError('Could not open camera')

        while True:
            yield camera.read()[1]

    # Camera background thread
    @classmethod
    def _thread(cls):
        print('Starting camera thread')
        frames_itr = cls.frames()
        for frame in frames_itr:
            Camera.frame = frame # Get the current frame
            Camera.event.set() # Signal clients a new frame is ready
            time.sleep(0)

            # Stop the thread if no clients request frames for 10 secs
            if time.time() - Camera.last_access > 10:
                frames_itr.close()
                print('Stopping camera thread due to inactivity')
                break
        Camera.thread = None



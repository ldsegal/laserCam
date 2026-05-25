import cv2
import numpy as np

class _ImageProcessor():
    """
    Class to handle image processing tasks and overlay drawing on video frames using OpenCV
    """
    def __init__(self):
        # State vars
        self._crosshair_enabled = False

    def enable_crosshair(self, enable: bool) -> None:
        """Enable or disable crosshair overlay"""
        self._crosshair_enabled = enable

    def draw_overlays(self, frame: np.ndarray) -> None:
        """Draw any enabled overlays on the given video frame"""
        if self._crosshair_enabled:
            self._draw_crosshair(frame)

    @staticmethod
    def _draw_crosshair(frame: np.ndarray) -> None:
        """Draw crosshair marker on frame"""
        height, width, _ = frame.shape
        cv2.drawMarker(frame, (width // 2, height // 2), (255, 0, 0), cv2.MARKER_CROSS, 40, 4)

# Singleton ImageProcessor instance
imageProcessor = _ImageProcessor()
"""One background reader owns the camera; consumers receive copied frames."""
from abc import ABC, abstractmethod
import platform
import threading
import time

import cv2


class CameraUnavailable(RuntimeError):
    pass


class CameraSource(ABC):
    @abstractmethod
    def get_latest_frame(self): ...

    def jpeg(self, quality=92):
        ok, encoded = cv2.imencode('.jpg', self.get_latest_frame(), [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            raise CameraUnavailable('Could not encode camera frame.')
        return encoded.tobytes()


class OpenCVCamera(CameraSource):
    def __init__(self, index=0, width=1280, height=720):
        self.index, self.width, self.height = index, width, height
        self._lock = threading.Lock()
        self._lifecycle = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._frame = None
        self._updated = 0.0
        self._error = 'Camera has not started.'

    def start(self):
        with self._lifecycle:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._capture, daemon=True)
            self._thread.start()

    def _capture(self):
        cap = None
        try:
            backend = cv2.CAP_AVFOUNDATION if platform.system() == 'Darwin' else cv2.CAP_ANY
            cap = cv2.VideoCapture(self.index, backend)
            if not cap.isOpened():
                raise CameraUnavailable(f'Camera {self.index} could not open. Check device index and macOS camera permission for your terminal.')
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok or frame is None or frame.size == 0:
                    raise CameraUnavailable('Camera disconnected or returned no frame. Reconnect it and retry.')
                with self._lock:
                    self._frame, self._updated, self._error = frame, time.monotonic(), None
                self._stop.wait(1 / 30)
        except Exception as exc:
            with self._lock:
                self._error = str(exc)
                self._frame = None
        finally:
            if cap is not None:
                cap.release()

    def get_latest_frame(self):
        with self._lock:
            if self._frame is None or time.monotonic() - self._updated > 3:
                raise CameraUnavailable(self._error or 'Camera frame is stale. Reconnect the camera.')
            return self._frame.copy()

    def status(self):
        with self._lock:
            available = self._frame is not None and time.monotonic() - self._updated <= 3
            return {'available': available, 'index': self.index,
                    'width': int(self._frame.shape[1]) if available else self.width,
                    'height': int(self._frame.shape[0]) if available else self.height,
                    'error': None if available else self._error or 'Waiting for a fresh camera frame.'}

    def stop(self):
        with self._lifecycle:
            self._stop.set()
            if self._thread:
                self._thread.join(timeout=5)
                if self._thread.is_alive():
                    raise CameraUnavailable('Camera reader is still stopping. Restart the backend before reconnecting.')
            with self._lock:
                self._frame = None
                self._error = 'Camera is stopped.'

    def reconnect(self, index):
        self.stop()
        self.index = index
        self.start()

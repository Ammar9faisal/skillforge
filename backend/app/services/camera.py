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

    def jpeg(self, quality=92, max_width=None):
        frame = self.get_latest_frame()
        if max_width is not None and frame.shape[1] > max_width:
            height = max(1, round(frame.shape[0] * max_width / frame.shape[1]))
            frame = cv2.resize(frame, (max_width, height), interpolation=cv2.INTER_AREA)
        ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
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
            with self._lock:
                self._error = 'Waiting for the camera’s first frame.'
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
            # AVFoundation / virtual cameras can briefly miss a read during
            # startup or delivery. A single miss is not a disconnection.
            deadline = time.monotonic() + 5
            while not self._stop.is_set():
                ok, frame = cap.read()
                now = time.monotonic()
                if not ok or frame is None or frame.size == 0:
                    if now >= deadline:
                        raise CameraUnavailable('Camera returned no fresh frames for several seconds. Check the device and reconnect it.')
                    self._stop.wait(0.05)
                    continue
                deadline = now + 3
                with self._lock:
                    self._frame, self._updated, self._error = frame, now, None
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

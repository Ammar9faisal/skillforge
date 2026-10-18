"""Select one camera source for preview, Teach and Verify. No implicit fallback."""
import threading

from .camera import CameraSource, CameraUnavailable


class CameraRouter(CameraSource):
    def __init__(self, webcam, whatsapp, source='webcam'):
        self.webcam, self.whatsapp = webcam, whatsapp
        self.source = source
        self.lock = threading.RLock()
        self._revision = 0

    @property
    def source_revision(self):
        with self.lock:
            return self._revision, self.whatsapp.revision if self.source == 'whatsapp' else 0

    def start(self):
        with self.lock:
            if self.source == 'webcam':
                self.webcam.start()

    def stop(self):
        with self.lock:
            self.webcam.stop()

    def select(self, source, index=None):
        with self.lock:
            if source not in ('webcam', 'whatsapp'):
                raise CameraUnavailable('Unknown camera source.')
            if source == 'whatsapp':
                if self.source == 'webcam':
                    self.webcam.stop()
                self.source = source
            else:
                if self.source != source or index is not None:
                    self.webcam.reconnect(self.webcam.index if index is None else index)
                self.source = source
            self._revision += 1
            return self.status()

    def reconnect(self, index):
        return self.select('webcam', index)

    def get_latest_frame(self):
        with self.lock:
            return (self.webcam if self.source == 'webcam' else self.whatsapp).get_latest_frame()

    def status(self):
        with self.lock:
            status = (self.webcam if self.source == 'webcam' else self.whatsapp).status()
            return {**status, 'source': self.source, 'source_revision': self.source_revision,
                    'whatsapp_available': self.whatsapp.status()['available']}

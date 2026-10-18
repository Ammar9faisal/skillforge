"""Bounded local JPEG bridge. Only the latest fresh capture is held in memory."""
import math
import secrets
import threading
import time
from uuid import uuid4

import cv2
import numpy as np

from .camera import CameraSource, CameraUnavailable


class BridgeError(RuntimeError):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def jpeg_dimensions(data):
    # Inspect SOF before decoding: a small compressed body must not allocate a huge image.
    if not data.startswith(b'\xff\xd8') or not data.endswith(b'\xff\xd9'):
        raise BridgeError('Expected a complete JPEG image.', 422)
    offset = 2
    while offset < len(data):
        if data[offset] != 0xff:
            break
        while offset < len(data) and data[offset] == 0xff:
            offset += 1
        if offset >= len(data):
            break
        marker = data[offset]
        offset += 1
        if marker in (0xd8, 0xd9, 0x01) or 0xd0 <= marker <= 0xd7:
            continue
        if offset + 2 > len(data):
            break
        length = int.from_bytes(data[offset:offset + 2], 'big')
        if length < 2 or offset + length > len(data):
            break
        if marker in (0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf):
            if length < 8:
                break
            height = int.from_bytes(data[offset + 3:offset + 5], 'big')
            width = int.from_bytes(data[offset + 5:offset + 7], 'big')
            if min(width, height) < 2 or max(width, height) > 4096 or width * height > 8_000_000:
                raise BridgeError('JPEG dimensions exceed the 4096-pixel / 8-megapixel limit.', 413)
            return width, height
        if marker == 0xda:
            break
        offset += length
    raise BridgeError('JPEG header is invalid.', 422)


class ReceivedCamera(CameraSource):
    MAX_BYTES = 4 * 1024 * 1024

    def __init__(self):
        self.lock = threading.RLock()
        self._token = None
        self._frame = None
        self._updated = 0.0
        self._sequence = 0
        self._deadline = 0.0
        self._metadata = None
        self._error = 'Start the native WhatsApp helper and select its video-call window.'
        self.revision = 0

    def start_bridge(self, window_id, crop, fps):
        with self.lock:
            if self._token and time.monotonic() < self._deadline:
                raise BridgeError('A WhatsApp helper is already sending frames. Stop it before starting another.', 409)
            self._token = secrets.token_urlsafe(32)
            self._frame = None
            self._sequence = 0
            self._updated = 0.0
            self._ttl = max(3.0, 3.0 / fps)
            self._deadline = time.monotonic() + max(10.0, self._ttl)
            self._metadata = {'window_id': window_id, 'crop': list(crop), 'fps': fps, 'bridge_id': uuid4().hex}
            self._error = 'Waiting for the native helper’s first frame.'
            self.revision += 1
            return {'upload_token': self._token, 'max_frame_bytes': self.MAX_BYTES, 'stale_after_seconds': self._ttl}

    def _authorize(self, token):
        if not token or not self._token or not secrets.compare_digest(token, self._token):
            raise BridgeError('Native capture session is invalid. Restart the helper.', 401)

    def receive(self, jpeg, token, sequence, captured_at):
        if len(jpeg) > self.MAX_BYTES:
            raise BridgeError('JPEG exceeds the 4 MB frame limit.', 413)
        with self.lock:
            self._authorize(token)
            if sequence <= self._sequence:
                raise BridgeError('Duplicate or out-of-order frame rejected.', 409)
            age = time.time() - captured_at
            if not math.isfinite(age) or age < -1 or age > 3:
                raise BridgeError('Capture timestamp is stale or in the future. Capture a new frame.', 409)
            dimensions = jpeg_dimensions(jpeg)
            frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None or (frame.shape[1], frame.shape[0]) != dimensions:
                raise BridgeError('JPEG could not be decoded.', 422)
            self._frame = frame
            self._sequence = sequence
            self._updated = time.monotonic() - max(0, age)
            self._deadline = self._updated + self._ttl
            self._error = None
            return {'accepted': True, 'sequence': sequence, 'width': dimensions[0], 'height': dimensions[1]}

    def stop_bridge(self, token, reason='Native helper stopped. Restart it to resume WhatsApp capture.'):
        with self.lock:
            self._authorize(token)
            self._token = None
            self._frame = None
            self._error = reason
            self.revision += 1

    def get_latest_frame(self):
        with self.lock:
            if self._frame is None or time.monotonic() >= self._deadline:
                raise CameraUnavailable(self._error or 'WhatsApp frames are stale. Check the call and restart the native helper.')
            return self._frame.copy()

    def status(self):
        with self.lock:
            available = self._frame is not None and time.monotonic() < self._deadline
            return {'available': available, 'source': 'whatsapp', 'index': None,
                    'width': int(self._frame.shape[1]) if self._frame is not None else 0,
                    'height': int(self._frame.shape[0]) if self._frame is not None else 0,
                    'error': None if available else self._error or 'WhatsApp frames are stale. Check the call and restart the native helper.',
                    'frame_age_seconds': round(max(0, time.monotonic() - self._updated), 2) if self._updated else None,
                    'received_frames': self._sequence, 'bridge': self._metadata}

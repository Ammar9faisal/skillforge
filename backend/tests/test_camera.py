import asyncio
import cv2
from unittest.mock import patch
import numpy as np
import pytest
from fastapi.testclient import TestClient
from app.services.camera import CameraUnavailable, OpenCVCamera
from app.main import app, camera, stream


def test_no_frame_is_never_reported_as_available():
    source = OpenCVCamera()
    assert source.status()['available'] is False
    with pytest.raises(CameraUnavailable):
        source.jpeg()


def test_camera_open_failure_is_explicit():
    source = OpenCVCamera(20)
    with patch('app.services.camera.cv2.VideoCapture') as capture:
        capture.return_value.isOpened.return_value = False
        source._capture()
    assert not source.status()['available']
    assert 'could not open' in source.status()['error']
    capture.return_value.release.assert_called_once()


def test_missing_camera_frame_returns_503():
    client = TestClient(app)
    with patch.object(camera, 'get_latest_frame', side_effect=CameraUnavailable('No camera frame')):
        assert client.get('/api/camera/frame').status_code == 503
        assert client.get('/api/camera/frame?preview=true').status_code == 503
        assert client.get('/api/camera/stream').status_code == 503


def test_jpeg_uses_frame_source():
    source = OpenCVCamera()
    with patch.object(source, 'get_latest_frame', return_value=np.zeros((20, 20, 3), dtype=np.uint8)):
        assert source.jpeg().startswith(b'\xff\xd8')


def test_stream_parts_include_exact_jpeg_length():
    jpeg = b'\xff\xd8sample\xff\xd9'

    async def first_part():
        with patch.object(camera, 'jpeg', return_value=jpeg):
            response = stream()
            part = await anext(response.body_iterator)
            await response.body_iterator.aclose()
            return part

    header, body = asyncio.run(first_part()).split(b'\r\n\r\n', 1)
    assert header.startswith(b'--frame\r\nContent-Type: image/jpeg\r\n')
    assert f'Content-Length: {len(jpeg)}'.encode() in header
    assert body == jpeg + b'\r\n'


def test_invalid_device_index_is_rejected():
    client = TestClient(app)
    assert client.post('/api/camera/reconnect', json={'index': -1}).status_code == 422
    assert client.get('/api/health').json()['status'] == 'ok'


def test_lifespan_releases_camera():
    with patch.object(camera, 'start') as start, patch.object(camera, 'stop') as stop:
        with TestClient(app) as client:
            assert client.get('/api/health').status_code == 200
            start.assert_called_once()
        stop.assert_called_once()


def test_temporary_missed_camera_read_recovers():
    source = OpenCVCamera(1)
    frame = np.full((20, 30, 3), 140, dtype=np.uint8)
    with patch('app.services.camera.cv2.VideoCapture') as capture, patch('app.services.camera.time.monotonic', return_value=10):
        cap = capture.return_value
        cap.isOpened.return_value = True
        # Use a callable sequence so the successful read ends the test loop.
        reads = iter([(False, None), (True, frame)])
        def read():
            result = next(reads)
            if result[0]: source._stop.set()
            return result
        cap.read.side_effect = read
        source._capture()
        assert source.status()['available']
        assert source.get_latest_frame().mean() == 140
        assert cap.read.call_count == 2
        cap.release.assert_called_once()


def test_camera_startup_without_frames_times_out():
    source = OpenCVCamera(1)
    with patch('app.services.camera.cv2.VideoCapture') as capture, patch('app.services.camera.time.monotonic', side_effect=[10, 16]):
        cap = capture.return_value
        cap.isOpened.return_value = True
        cap.read.return_value = (False, None)
        source._capture()
    assert not source.status()['available']
    assert 'no fresh frames' in source.status()['error']
    cap.release.assert_called_once()


def test_prolonged_camera_dropout_invalidates_previous_frame():
    source = OpenCVCamera(1)
    frame = np.zeros((20, 30, 3), dtype=np.uint8)
    with patch('app.services.camera.cv2.VideoCapture') as capture, patch('app.services.camera.time.monotonic', side_effect=[10, 10, 14]):
        cap = capture.return_value
        cap.isOpened.return_value = True
        cap.read.side_effect = [(True, frame), (False, None)]
        source._capture()
    assert not source.status()['available']
    with pytest.raises(CameraUnavailable): source.jpeg()
    cap.release.assert_called_once()


@pytest.mark.parametrize('width,height,expected', [(1920, 1080, (540, 960)), (1200, 1800, (1440, 960)), (640, 480, (480, 640))])
def test_preview_is_smaller_without_changing_capture_resolution(width, height, expected):
    original = np.full((height, width, 3), 140, dtype=np.uint8)
    with patch.object(camera, 'get_latest_frame', return_value=original):
        client = TestClient(app)
        preview = client.get('/api/camera/frame?preview=true')
        full = client.get('/api/camera/frame')
    assert preview.status_code == full.status_code == 200
    small = cv2.imdecode(np.frombuffer(preview.content, np.uint8), cv2.IMREAD_COLOR)
    large = cv2.imdecode(np.frombuffer(full.content, np.uint8), cv2.IMREAD_COLOR)
    assert small.shape[:2] == expected
    assert large.shape[:2] == original.shape[:2] == (height, width)
    assert np.all(original == 140)
    assert preview.headers['cache-control'] == 'no-store'

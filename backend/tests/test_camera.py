import asyncio
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

import time
from unittest.mock import patch
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.camera import CameraUnavailable
from app.services.received_camera import BridgeError, ReceivedCamera, jpeg_dimensions

@pytest.fixture
def bridge(monkeypatch):
    source = ReceivedCamera(); monkeypatch.setattr(app.state, 'whatsapp', source)
    client = TestClient(app, client=('127.0.0.1', 50000))
    _, encoded = cv2.imencode('.jpg', np.full((60, 40, 3), 100, dtype=np.uint8))
    opened = client.post('/api/camera/whatsapp/start', json={'window_id': 123, 'crop': [0.1,0.1,0.8,0.8], 'fps': 2})
    assert opened.status_code == 200
    return source, client, encoded.tobytes(), opened.json()['upload_token']

def upload(bridge, **overrides):
    _, client, jpeg, token = bridge
    headers = {'Content-Type':'image/jpeg', 'Authorization':f'Bearer {token}', 'X-Sequence':'1', 'X-Captured-At':str(time.time()), **overrides}
    return client.post('/api/camera/whatsapp/frame', content=jpeg, headers=headers)

def test_jpeg_reaches_common_source_without_disk(bridge):
    source, _, _, _ = bridge
    assert not source.status()['available']
    assert upload(bridge).status_code == 200
    assert source.status()['available']
    assert jpeg_dimensions(source.jpeg()) == (40,60)
    frame = source.get_latest_frame(); frame[:] = 0
    assert source.get_latest_frame().mean() > 90

def test_stop_invalidates_frame_and_token(bridge):
    source, client, _, token = bridge; upload(bridge)
    assert client.post('/api/camera/whatsapp/stop', headers={'Authorization':f'Bearer {token}'}).status_code == 204
    assert not source.status()['available']
    with pytest.raises(CameraUnavailable): source.jpeg()
    assert upload(bridge).status_code == 401

def test_stale_frames_are_never_used(bridge):
    source, _, _, _ = bridge; upload(bridge)
    with patch('app.services.received_camera.time.monotonic', return_value=time.monotonic()+4):
        assert not source.status()['available']
        with pytest.raises(CameraUnavailable, match='stale'): source.jpeg()

@pytest.mark.parametrize('headers,code', [({'Authorization':'Bearer invalid'},401), ({'X-Captured-At':'nan'},409), ({'X-Captured-At':'0'},409), ({'X-Captured-At':str(time.time()+1000)},409), ({'X-Sequence':'0'},422), ({'Content-Type':'image/png'},415), ({'Origin':'http://localhost:3000'},403)])
def test_invalid_uploads_do_not_establish_availability(bridge, headers, code):
    assert upload(bridge, **headers).status_code == code
    assert not bridge[0].status()['available']

def test_duplicate_and_reordered_frames_rejected(bridge):
    assert upload(bridge).status_code == 200
    assert upload(bridge).status_code == 409
    assert upload(bridge, **{'X-Sequence':'3'}).status_code == 200
    assert upload(bridge, **{'X-Sequence':'2'}).status_code == 409

def test_concurrent_helper_rejected_until_stale(bridge):
    _, client, _, _ = bridge
    body = {'window_id':124, 'crop':[0,0,1,1], 'fps':2}
    assert client.post('/api/camera/whatsapp/start', json=body).status_code == 409
    with patch('app.services.received_camera.time.monotonic', return_value=time.monotonic()+16):
        assert client.post('/api/camera/whatsapp/start', json=body).status_code == 200
    assert upload(bridge).status_code == 401

@pytest.mark.parametrize('body', [{'window_id':0,'crop':[0,0,1,1]}, {'window_id':1,'crop':[0,0,2,1]}, {'window_id':1,'crop':[0,0,0,1]}, {'window_id':1,'crop':[0,0,1,1],'fps':100}, {'window_id':1,'crop':[0,0,1]}])
def test_start_metadata_validation(body):
    client = TestClient(app, client=('127.0.0.1',50000))
    assert client.post('/api/camera/whatsapp/start',json=body).status_code == 422

def test_remote_ingress_rejected():
    client = TestClient(app, client=('192.0.2.1',50000))
    assert client.post('/api/camera/whatsapp/start',json={'window_id':1,'crop':[0,0,1,1]}).status_code == 403

def test_oversized_or_invalid_jpeg_rejected_before_decode(bridge):
    source, _, _, token = bridge
    with patch('app.services.received_camera.cv2.imdecode') as decode:
        for data in [b'invalid', b'x'*(source.MAX_BYTES+1), b'\xff\xd8\xff\xc0\x00\x0b\x08\xff\xff\xff\xff\x01\x01\x11\x00\xff\xd9']:
            with pytest.raises(BridgeError): source.receive(data,token,1,time.time())
        decode.assert_not_called()
    assert not source.status()['available']

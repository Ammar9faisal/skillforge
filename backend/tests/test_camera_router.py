import time
from unittest.mock import Mock
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.camera import CameraUnavailable
from app.services.camera_router import CameraRouter
from app.services.received_camera import ReceivedCamera


def test_selected_source_freshness_and_usb(monkeypatch):
    webcam = Mock(index=0)
    webcam.get_latest_frame.return_value = np.full((40, 60, 3), 30, np.uint8)
    webcam.status.return_value = {'available': True, 'index': 0}
    incoming = ReceivedCamera()
    router = CameraRouter(webcam, incoming)
    monkeypatch.setattr(app.state, 'camera', router)
    client = TestClient(app)
    assert router.get_latest_frame().mean() == 30
    before = router.source_revision
    assert client.post('/api/camera/source', json={'source': 'whatsapp'}).json()['source'] == 'whatsapp'
    assert router.source_revision != before
    webcam.stop.assert_called_once()
    with pytest.raises(CameraUnavailable): router.jpeg()
    before = router.source_revision
    lease = incoming.start_bridge(123, (0, 0, 1, 1), 2)
    _, jpeg = cv2.imencode('.jpg', np.full((40, 60, 3), 180, np.uint8))
    incoming.receive(jpeg.tobytes(), lease['upload_token'], 1, time.time())
    assert router.source_revision != before
    assert router.get_latest_frame().mean() == 180
    incoming._deadline -= 5
    with pytest.raises(CameraUnavailable): router.jpeg()
    router.select('webcam', 0)
    webcam.reconnect.assert_called_once_with(0)
    assert router.get_latest_frame().mean() == 30
    for body in ({'source': 'unknown'}, {'source': 'webcam', 'index': -1}, {'source': 'webcam', 'index': True}):
        assert client.post('/api/camera/source', json=body).status_code == 422

@pytest.mark.parametrize('selected', ['webcam', 'whatsapp'])
def test_teach_persists_selected_source(tmp_path, monkeypatch, selected):
    from app.services.storage import TaskStore
    webcam = Mock(index=0)
    webcam.get_latest_frame.return_value = np.full((40, 60, 3), 30, np.uint8)
    incoming = ReceivedCamera()
    lease = incoming.start_bridge(123, (0, 0, 1, 1), 2)
    _, jpeg = cv2.imencode('.jpg', np.full((40, 60, 3), 180, np.uint8))
    incoming.receive(jpeg.tobytes(), lease['upload_token'], 1, time.time())
    store = TaskStore(tmp_path / 'tasks')
    task = store.create('Source validation')
    monkeypatch.setattr(app.state, 'camera', CameraRouter(webcam, incoming, selected))
    monkeypatch.setattr(app.state, 'store', store)
    client = TestClient(app)
    response = client.post(f'/api/tasks/{task.id}/steps', json={'note': ''})
    assert response.status_code == 201
    cp = response.json()['checkpoints'][0]
    image = store.image(task.id, cp['id'])
    assert cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_COLOR).mean() == (180 if selected == 'whatsapp' else 30)

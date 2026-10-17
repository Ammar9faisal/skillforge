from unittest.mock import Mock
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.camera import CameraUnavailable
from app.services.storage import TaskStore


@pytest.fixture
def workflow(tmp_path, monkeypatch):
    store = TaskStore(tmp_path / 'tasks')
    source = Mock()
    _, encoded = cv2.imencode('.jpg', np.zeros((40, 60, 3), dtype=np.uint8))
    source.jpeg.return_value = encoded.tobytes()
    monkeypatch.setattr(app.state, 'store', store)
    monkeypatch.setattr(app.state, 'camera', source)
    return TestClient(app), store, source


def create(client):
    response = client.post('/api/tasks', json={'title': '  Colour assembly  '})
    assert response.status_code == 201
    assert response.json()['title'] == 'Colour assembly'
    return response.json()['id']


def capture(client, task_id, note=''):
    response = client.post(f'/api/tasks/{task_id}/steps', json={'note': note})
    assert response.status_code == 201, response.text
    return response.json()


def test_task_creation_and_validation(workflow):
    client, store, _ = workflow
    task_id = create(client)
    assert store.get(task_id).checkpoints == []
    assert client.get('/api/tasks').json()[0]['id'] == task_id
    for title in ['', '  ', 'x' * 161]:
        assert client.post('/api/tasks', json={'title': title}).status_code == 422
    assert client.post('/api/tasks', json={'title': 'a', 'path': '/tmp/a'}).status_code == 422


def test_three_checkpoints_survive_new_store_and_order(workflow):
    client, store, _ = workflow
    task_id = create(client)
    for n in range(3):
        task = capture(client, task_id, f'Step {n + 1}')
    assert [c['position'] for c in task['checkpoints']] == [1, 2, 3]
    restored = TaskStore(store.root).get(task_id)
    assert [c.note for c in restored.checkpoints] == ['Step 1', 'Step 2', 'Step 3']
    for checkpoint in restored.checkpoints:
        assert store.image(task_id, checkpoint.id).startswith(b'\xff\xd8')
    assert len(list((store.root / task_id).glob('*.jpg'))) == 3


def test_delete_renumbers_without_changing_ids(workflow):
    client, store, _ = workflow
    task_id = create(client)
    for _ in range(3):
        before = capture(client, task_id)
    middle = before['checkpoints'][1]
    response = client.delete(f'/api/tasks/{task_id}/steps/{middle["id"]}')
    after = response.json()['checkpoints']
    assert [c['position'] for c in after] == [1, 2]
    assert [c['id'] for c in after] == [before['checkpoints'][0]['id'], before['checkpoints'][2]['id']]
    assert not (store.root / task_id / middle['reference_image']).exists()
    assert client.get(f'/api/tasks/{task_id}/steps/{middle["id"]}/image').status_code == 404
    assert capture(client, task_id)['checkpoints'][-1]['position'] == 3


def test_retake_preserves_identity_and_replaces_file(workflow):
    client, store, source = workflow
    task_id = create(client)
    checkpoint = capture(client, task_id, 'Original')['checkpoints'][0]
    _, new_image = cv2.imencode('.jpg', np.full((40, 60, 3), 255, dtype=np.uint8))
    source.jpeg.return_value = new_image.tobytes()
    response = client.put(f'/api/tasks/{task_id}/steps/{checkpoint["id"]}', json={'note': 'Retaken'})
    updated = response.json()['checkpoints'][0]
    assert updated['id'] == checkpoint['id']
    assert updated['position'] == 1
    assert updated['note'] == 'Retaken'
    assert updated['reference_image'] != checkpoint['reference_image']
    assert not (store.root / task_id / checkpoint['reference_image']).exists()
    assert client.get(f'/api/tasks/{task_id}/steps/{checkpoint["id"]}/image').content == new_image.tobytes()


def test_title_and_note_updates_persist(workflow):
    client, store, _ = workflow
    task_id = create(client)
    checkpoint = capture(client, task_id)['checkpoints'][0]
    assert client.patch(f'/api/tasks/{task_id}', json={'title': 'New title'}).status_code == 200
    assert client.patch(f'/api/tasks/{task_id}/steps/{checkpoint["id"]}', json={'note': ' Blue beside red '}).status_code == 200
    saved = TaskStore(store.root).get(task_id)
    assert saved.title == 'New title'
    assert saved.checkpoints[0].note == 'Blue beside red'


def test_missing_and_invalid_frames_do_not_mutate_saved_task(workflow):
    client, store, source = workflow
    task_id = create(client)
    checkpoint = capture(client, task_id)['checkpoints'][0]
    source.jpeg.side_effect = CameraUnavailable('Camera disconnected')
    assert client.post(f'/api/tasks/{task_id}/steps', json={}).status_code == 503
    assert client.put(f'/api/tasks/{task_id}/steps/{checkpoint["id"]}', json={}).status_code == 503
    source.jpeg.side_effect = None
    source.jpeg.return_value = b'corrupted image'
    assert client.post(f'/api/tasks/{task_id}/steps', json={}).status_code == 503
    saved = store.get(task_id)
    assert len(saved.checkpoints) == 1
    assert saved.checkpoints[0].reference_image == checkpoint['reference_image']
    assert len(list((store.root / task_id).glob('*.jpg'))) == 1


def test_missing_reference_and_unknown_ids_are_clear(workflow):
    client, store, _ = workflow
    task_id = create(client)
    checkpoint = capture(client, task_id)['checkpoints'][0]
    (store.root / task_id / checkpoint['reference_image']).unlink()
    assert client.get(f'/api/tasks/{task_id}/steps/{checkpoint["id"]}/image').status_code == 404
    assert client.delete(f'/api/tasks/{task_id}/steps/unknown').status_code == 404
    assert client.get('/api/tasks/invalid-id').status_code == 404
    assert client.get(f'/api/tasks/{"a" * 32}').status_code == 404


def test_delete_task_removes_images_and_metadata(workflow):
    client, store, _ = workflow
    task_id = create(client)
    capture(client, task_id)
    assert client.delete(f'/api/tasks/{task_id}').status_code == 204
    assert not (store.root / task_id).exists()
    assert client.get('/api/tasks').json() == []


def test_atomic_write_failure_keeps_previous_metadata(workflow, monkeypatch):
    client, store, _ = workflow
    task_id = create(client)
    capture(client, task_id)
    def fail_save(task):
        raise OSError('Disk full')
    monkeypatch.setattr(store, '_save', fail_save)
    response = client.post(f'/api/tasks/{task_id}/steps', json={})
    assert response.status_code == 500
    assert len(store.get(task_id).checkpoints) == 1
    assert len(list((store.root / task_id).glob('*.jpg'))) == 1


def test_local_frontend_can_preflight_task_mutations(workflow):
    client, _, _ = workflow
    for origin in ['http://localhost:3000', 'http://127.0.0.1:3000']:
        response = client.options('/api/tasks/example', headers={
            'Origin': origin, 'Access-Control-Request-Method': 'PATCH',
            'Access-Control-Request-Headers': 'content-type',
        })
        assert response.status_code == 200
        assert response.headers['access-control-allow-origin'] == origin
    response = client.options('/api/tasks', headers={
        'Origin': 'https://untrusted.example', 'Access-Control-Request-Method': 'POST',
    })
    assert 'access-control-allow-origin' not in response.headers

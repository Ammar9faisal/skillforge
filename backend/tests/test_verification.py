import base64
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
import cv2
import httpx
import numpy as np
from fastapi.testclient import TestClient
from google.genai import errors
from pydantic import SecretStr
import pytest
from app.config import Settings
from app.main import app
from app.models import SavedTutorial
from app.services.camera import CameraUnavailable
from app.services.gemini import GeminiService
from app.services.storage import TaskStore
from app.services.verification import VerificationService

@pytest.fixture
def v(tmp_path, monkeypatch):
    store = TaskStore(tmp_path / 'tasks')
    _, ref = cv2.imencode('.jpg', np.zeros((40, 60, 3), dtype=np.uint8))
    _, live = cv2.imencode('.jpg', np.full((40, 60, 3), 180, dtype=np.uint8))
    task = store.create('Assembly')
    for _ in range(2): task = store.capture(task.id, ref.tobytes())
    tutorial = SavedTutorial(steps=[{'step_id': c.position, 'title': f'Step {c.position}', 'instruction': 'Place two pieces beside each other.', 'reference_image': c.reference_image, 'verification_criteria': ['Two pieces are beside each other.'], 'safety_notes': []} for c in task.checkpoints], model='test')
    task = store.save_tutorial(task.id, tutorial, task.updated_at)
    sdk = MagicMock(); sdk.__enter__.return_value = sdk
    sdk.models.get.return_value = SimpleNamespace(supported_actions=['generateContent'])
    output = {'status': 'PASS', 'expected': 'Pieces beside each other.', 'observed': 'Both pieces are visibly beside each other.', 'feedback': 'The visible state matches.', 'confidence': 'high'}
    sdk.models.generate_content.return_value = SimpleNamespace(text=json.dumps(output))
    factory = Mock(return_value=sdk)
    gemini = GeminiService(Settings(_env_file=None, gemini_model='test-model', gemini_api_key=SecretStr('test-key')), factory)
    camera = Mock(); camera.jpeg.return_value = live.tobytes()
    service = VerificationService()
    for name, value in [('store', store), ('camera', camera), ('gemini', gemini), ('verification', service)]: monkeypatch.setattr(app.state, name, value)
    client = TestClient(app); prefix = f'/api/tasks/{task.id}'
    body = {'tutorial_version': task.tutorial.generated_at.isoformat()}
    session = client.post(prefix + '/sessions', json=body).json()
    return SimpleNamespace(store=store, task=task, sdk=sdk, factory=factory, gemini=gemini, camera=camera, service=service, client=client, prefix=prefix, session=session, output=output, reference=ref.tobytes(), learner=live.tobytes(), body=body)

def verify(v, step=1):
    return v.client.post(v.prefix + '/verify', json={'session_id': v.session['session_id'], 'step_id': step})

def test_pass_sends_exact_images_and_advances(v):
    response = verify(v); assert response.status_code == 200, response.text
    data = response.json(); assert data['completed_step_ids'] == [1] and data['active_step_id'] == 2
    result = data['last_result']
    for key, jpeg in [('learner', v.learner), ('reference', v.reference)]: assert base64.b64decode(result[key + '_data_url'].split(',')[1]) == jpeg
    args = v.sdk.models.generate_content.call_args.kwargs
    assert [p.inline_data.data for p in args['contents'][0].parts if p.inline_data] == [v.reference, v.learner]
    assert args['config'].response_json_schema['properties']['status']['enum'] == ['PASS', 'FAIL', 'UNCERTAIN']
    assert v.factory.call_args.kwargs['http_options'].retry_options.attempts == 1
    assert v.store.get(v.task.id).tutorial == v.task.tutorial

@pytest.mark.parametrize('status', ['FAIL', 'UNCERTAIN'])
def test_nonpass_preserves_step_and_feedback(v, status):
    v.sdk.models.generate_content.return_value.text = json.dumps({**v.output, 'status': status})
    data = verify(v).json()
    assert data['active_step_id'] == 1 and data['completed_step_ids'] == []
    assert data['last_result']['status'] == status and data['last_result']['feedback'] == v.output['feedback']

def test_low_confidence_pass_is_uncertain(v):
    v.sdk.models.generate_content.return_value.text = json.dumps({**v.output, 'confidence': 'low'})
    data = verify(v).json(); assert data['last_result']['status'] == 'UNCERTAIN' and data['completed_step_ids'] == []

def test_resume_reset_and_completion(v):
    assert verify(v).status_code == 200
    data = v.client.post(v.prefix + '/sessions', json={**v.body, 'session_id': v.session['session_id']}).json()
    assert data['resumed'] and data['completed_step_ids'] == [1]
    done = verify(v, 2).json(); assert done['complete'] and done['active_step_id'] is None and done['completed_step_ids'] == [1, 2]
    assert verify(v, 2).status_code == 409
    reset = v.client.post(v.prefix + f'/sessions/{v.session["session_id"]}/reset').json()
    assert reset['active_step_id'] == 1 and reset['last_result'] is None and reset['completed_step_ids'] == []

@pytest.mark.parametrize('body', [{'step_id': 2}, {'step_id': 99}, {'step_id': True}, {'step_id': '1'}, {'step_id': 1, 'status': 'PASS'}])
def test_cannot_skip_or_inject_status(v, body):
    response = v.client.post(v.prefix + '/verify', json={'session_id': v.session['session_id'], **body})
    assert response.status_code in (409, 422); v.factory.assert_not_called()

def test_unknown_session_rejected(v):
    assert v.client.post(v.prefix + '/verify', json={'session_id': 'a'*32, 'step_id': 1}).status_code == 409
    v.factory.assert_not_called()

@pytest.mark.parametrize('problem', ['camera', 'invalid_camera', 'missing_reference', 'no_tutorial', 'missing_key'])
def test_missing_inputs_do_not_call_google(v, problem):
    if problem == 'camera': v.camera.jpeg.side_effect = CameraUnavailable('Camera unavailable')
    elif problem == 'invalid_camera': v.camera.jpeg.return_value = b'invalid'
    elif problem == 'missing_reference': (v.store.root / v.task.id / v.task.checkpoints[0].reference_image).unlink()
    elif problem == 'no_tutorial': v.store.update_note(v.task.id, v.task.checkpoints[0].id, 'Changed')
    else: v.gemini.settings.gemini_api_key = SecretStr('')
    assert verify(v).status_code in (404, 409, 503); v.factory.assert_not_called()
    state = v.service.sessions[v.session['session_id']]; assert not state['busy'] and state['completed'] == []

def test_invalid_output_retries_once_then_preserves_progress(v):
    v.sdk.models.generate_content.return_value.text = '{"status":"PASS"}'
    assert verify(v).status_code == 502 and v.sdk.models.generate_content.call_count == 2
    assert v.service.sessions[v.session['session_id']]['completed'] == []
    v.sdk.models.generate_content.side_effect = [SimpleNamespace(text='bad'), SimpleNamespace(text=json.dumps(v.output))]
    assert verify(v).json()['completed_step_ids'] == [1]

@pytest.mark.parametrize('error,code', [(httpx.ReadTimeout('secret'), 504), (errors.ServerError(503, {'error': {'message': 'secret'}}), 503), (errors.ClientError(429, {'error': {'message': 'secret'}}), 429)])
def test_errors_are_not_fake_assessments(v, error, code):
    v.sdk.models.generate_content.side_effect = error
    response = verify(v); assert response.status_code == code and 'secret' not in response.text
    assert v.service.sessions[v.session['session_id']]['last'] is None

@pytest.mark.parametrize('change', ['reset', 'task'])
def test_concurrency_and_stale_results(v, change):
    started, release = Event(), Event()
    def delayed(**kwargs):
        started.set(); assert release.wait(5)
        return SimpleNamespace(text=json.dumps(v.output))
    v.sdk.models.generate_content.side_effect = delayed
    with ThreadPoolExecutor() as pool:
        pending = pool.submit(verify, v); assert started.wait(5)
        assert verify(v).status_code == 409
        if change == 'reset': v.client.post(v.prefix + f'/sessions/{v.session["session_id"]}/reset')
        else: v.store.update_note(v.task.id, v.task.checkpoints[0].id, 'Changed')
        release.set(); assert pending.result().status_code == 409
    assert v.service.sessions[v.session['session_id']]['completed'] == []

def test_backend_restart_cannot_restore_browser_completion(v):
    verify(v); v.service.sessions.clear()
    data = v.client.post(v.prefix + '/sessions', json={**v.body, 'session_id': v.session['session_id']}).json()
    assert not data['resumed'] and data['completed_step_ids'] == [] and data['session_id'] != v.session['session_id']

def test_idle_expiration_rejects_verification(v):
    v.service.sessions[v.session['session_id']]['touched'] -= 1801
    assert verify(v).status_code == 409
    v.factory.assert_not_called()

def test_old_tutorial_version_cannot_open_session(v):
    data = v.client.post(v.prefix + '/sessions', json={'tutorial_version': '2020-01-01T00:00:00Z'})
    assert data.status_code == 409

def test_failed_retry_preserves_previous_real_feedback(v):
    v.sdk.models.generate_content.return_value.text = json.dumps({**v.output, 'status': 'FAIL'})
    first = verify(v).json()['last_result']
    v.sdk.models.generate_content.side_effect = httpx.ReadTimeout('private')
    assert verify(v).status_code == 504
    state = v.service.sessions[v.session['session_id']]
    assert state['last'] == {**first, 'assessed_at': state['last']['assessed_at']}
    assert state['completed'] == []

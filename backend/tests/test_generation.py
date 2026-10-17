import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import cv2
from fastapi.testclient import TestClient
from google import genai
from google.genai import errors
import httpx
import numpy as np
from pydantic import SecretStr
import pytest

from app.config import Settings
from app.main import app
from app.services.gemini import GeminiError, GeminiService
from app.services.storage import TaskStore


@pytest.fixture
def generation(tmp_path, monkeypatch):
    store = TaskStore(tmp_path / 'tasks')
    _, jpeg = cv2.imencode('.jpg', np.zeros((40, 60, 3), dtype=np.uint8))
    task = store.create('Colour assembly')
    for i in range(3):
        task = store.capture(task.id, jpeg.tobytes(), f'Note {i + 1}')
    sdk = MagicMock()
    sdk.__enter__.return_value = sdk
    sdk.models.get.return_value = SimpleNamespace(supported_actions=['generateContent'])
    factory = Mock(return_value=sdk)
    settings = Settings(_env_file=None, gemini_api_key=SecretStr('test-only-key'), gemini_model='test-model')
    service = GeminiService(settings, factory)
    output = {'steps': [{'step_id': c.position, 'title': f'Step {c.position}',
        'instruction': 'Place the visible component beside the reference component.',
        'reference_image': c.reference_image, 'verification_criteria': ['Components are visibly beside each other'],
        'safety_notes': []} for c in task.checkpoints]}
    sdk.models.generate_content.return_value = SimpleNamespace(text=json.dumps(output))
    monkeypatch.setattr(app.state, 'store', store)
    monkeypatch.setattr(app.state, 'gemini', service)
    source = Mock()
    source.jpeg.side_effect = AssertionError('Generation must use saved references, not the live camera')
    monkeypatch.setattr(app.state, 'camera', source)
    return SimpleNamespace(store=store, task=task, sdk=sdk, factory=factory, service=service,
                           output=output, client=TestClient(app), jpeg=jpeg.tobytes())


def generate(g):
    return g.client.post(f'/api/tasks/{g.task.id}/generate')


def test_generation_sends_all_ordered_images_and_saves_valid_tutorial(generation):
    g = generation
    response = generate(g)
    assert response.status_code == 200, response.text
    result = response.json()['tutorial']
    assert result['model'] == 'test-model'
    assert len(result['steps']) == 3
    restored = TaskStore(g.store.root).get(g.task.id)
    assert restored.tutorial.steps[1].reference_image == g.task.checkpoints[1].reference_image
    g.sdk.models.get.assert_called_once_with(model='test-model')
    kwargs = g.sdk.models.generate_content.call_args.kwargs
    parts = kwargs['contents'][0].parts
    metadata = json.loads(parts[0].text)
    assert [c['instructor_note'] for c in metadata['checkpoints']] == ['Note 1', 'Note 2', 'Note 3']
    assert [part.inline_data.data for part in parts if part.inline_data] == [g.jpeg] * 3
    assert kwargs['config'].response_mime_type == 'application/json'
    assert g.factory.call_args.kwargs['http_options'].retry_options.attempts == 1
    assert 'test-only-key' not in response.text


@pytest.mark.parametrize('field,value', [('gemini_api_key', SecretStr('')), ('gemini_model', '')])
def test_missing_configuration_never_calls_google(generation, field, value):
    g = generation
    setattr(g.service.settings, field, value)
    response = generate(g)
    assert response.status_code == 503
    assert 'backend/.env' in response.json()['detail']
    g.factory.assert_not_called()
    assert g.store.get(g.task.id).tutorial is None


def test_no_default_model_is_assumed(monkeypatch):
    monkeypatch.delenv('GEMINI_MODEL', raising=False)
    assert Settings(_env_file=None).gemini_model == ''


def test_one_checkpoint_is_rejected_before_google(generation):
    g = generation
    task = g.store.create('Too few')
    g.store.capture(task.id, g.jpeg)
    response = g.client.post(f'/api/tasks/{task.id}/generate')
    assert response.status_code == 409
    g.factory.assert_not_called()


@pytest.mark.parametrize('corrupted', [False, True])
def test_missing_or_corrupt_reference_is_rejected_before_google(generation, corrupted):
    g = generation
    path = g.store.root / g.task.id / g.task.checkpoints[1].reference_image
    if corrupted:
        path.write_bytes(b'not a jpeg')
    else:
        path.unlink()
    response = generate(g)
    assert response.status_code == 409
    assert 'checkpoint 2' in response.json()['detail']
    g.factory.assert_not_called()


def test_malformed_response_has_one_controlled_retry(generation):
    g = generation
    g.sdk.models.generate_content.side_effect = [SimpleNamespace(text='invalid json'), SimpleNamespace(text=json.dumps(g.output))]
    assert generate(g).status_code == 200
    assert g.sdk.models.generate_content.call_count == 2
    retry_parts = g.sdk.models.generate_content.call_args.kwargs['contents'][0].parts
    assert 'Previous output failed validation' in retry_parts[-1].text


@pytest.mark.parametrize('bad_output', ['{}', 'not-json', '', '{"steps": []}'])
def test_invalid_output_twice_never_saves_a_tutorial(generation, bad_output):
    g = generation
    g.sdk.models.generate_content.return_value = SimpleNamespace(text=bad_output)
    response = generate(g)
    assert response.status_code == 502
    assert 'twice' in response.json()['detail']
    assert g.sdk.models.generate_content.call_count == 2
    assert g.store.get(g.task.id).tutorial is None


def test_fabricated_reference_mapping_is_rejected(generation):
    g = generation
    g.output['steps'][0]['reference_image'] = g.output['steps'][1]['reference_image']
    g.sdk.models.generate_content.return_value = SimpleNamespace(text=json.dumps(g.output))
    assert generate(g).status_code == 502
    assert g.store.get(g.task.id).tutorial is None


@pytest.mark.parametrize('code,expected', [(400, 502), (401, 503), (403, 503), (404, 503), (429, 429), (500, 502), (503, 503), (504, 504)])
def test_model_access_error_is_actionable_and_sanitized(generation, code, expected):
    g = generation
    g.sdk.models.get.side_effect = errors.APIError(code, {'error': {'message': 'private test-only-key detail'}})
    response = generate(g)
    assert response.status_code == expected
    assert 'private' not in response.text
    assert 'test-only-key' not in response.text
    g.sdk.models.generate_content.assert_not_called()


def test_inference_timeout_is_not_retried(generation):
    g = generation
    g.sdk.models.generate_content.side_effect = httpx.ReadTimeout('secret request context')
    response = generate(g)
    assert response.status_code == 504
    assert 'secret' not in response.text
    assert g.sdk.models.generate_content.call_count == 1


def test_failed_regeneration_preserves_previous_tutorial(generation):
    g = generation
    assert generate(g).status_code == 200
    old = g.store.get(g.task.id).tutorial
    g.sdk.models.generate_content.return_value = SimpleNamespace(text='invalid')
    assert generate(g).status_code == 502
    assert g.store.get(g.task.id).tutorial == old


@pytest.mark.parametrize('edit', ['title', 'note', 'retake', 'capture', 'delete'])
def test_edits_invalidate_the_generated_tutorial(generation, edit):
    g = generation
    assert generate(g).status_code == 200
    if edit == 'title':
        g.store.rename(g.task.id, 'Changed')
    elif edit == 'note':
        g.store.update_note(g.task.id, g.task.checkpoints[0].id, 'Changed')
    elif edit == 'retake':
        g.store.capture(g.task.id, g.jpeg, checkpoint_id=g.task.checkpoints[0].id)
    elif edit == 'capture':
        g.store.capture(g.task.id, g.jpeg)
    else:
        g.store.delete_checkpoint(g.task.id, g.task.checkpoints[0].id)
    assert g.store.get(g.task.id).tutorial is None


def test_duplicate_generation_and_edits_during_inference_are_safe(generation):
    g = generation
    entered, release = Event(), Event()
    def wait_for_edit(**kwargs):
        entered.set()
        assert release.wait(timeout=5)
        return SimpleNamespace(text=json.dumps(g.output))
    g.sdk.models.generate_content.side_effect = wait_for_edit
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(generate, g)
        try:
            assert entered.wait(timeout=5)
            assert generate(g).status_code == 409
            g.store.update_note(g.task.id, g.task.checkpoints[0].id, 'Changed during request')
        finally:
            release.set()
        response = future.result(timeout=5)
    assert response.status_code == 409
    assert 'changed during generation' in response.json()['detail']
    assert g.store.get(g.task.id).tutorial is None
    assert generate(g).status_code == 200


def test_connection_check_is_explicit_about_compatibility(generation):
    response = generation.client.post('/api/gemini/check')
    assert response.status_code == 200
    assert response.json()['accessible'] is True
    generation.sdk.models.generate_content.assert_not_called()


def test_sdk_serializes_real_image_and_schema_request(generation):
    """Exercise the installed SDK with a fake HTTP transport, not live inference."""
    g = generation
    seen = []
    def transport(request):
        seen.append(request)
        if request.method == 'GET':
            return httpx.Response(200, json={'name': 'models/test-model', 'supportedGenerationMethods': ['generateContent']})
        body = json.loads(request.content)
        assert len([p for p in body['contents'][0]['parts'] if 'inlineData' in p]) == 3
        assert body['generationConfig']['responseMimeType'] == 'application/json'
        schema = body['generationConfig']['responseJsonSchema']
        assert 'additionalProperties' not in schema
        assert set(schema['properties']['steps']['items']['properties']) == set(g.output['steps'][0])
        return httpx.Response(200, json={'candidates': [{'content': {'role': 'model', 'parts': [{'text': json.dumps(g.output)}]}, 'finishReason': 'STOP'}]})
    def factory(**kwargs):
        kwargs['http_options'].httpx_client = httpx.Client(transport=httpx.MockTransport(transport))
        return genai.Client(**kwargs)
    g.service.client_factory = factory
    assert generate(g).status_code == 200
    assert [r.method for r in seen] == ['GET', 'POST']


def test_model_without_generate_content_is_rejected(generation):
    g = generation
    g.sdk.models.get.return_value = SimpleNamespace(supported_actions=['embedContent'])
    assert generate(g).status_code == 503
    g.sdk.models.generate_content.assert_not_called()


def test_invalid_api_key_is_distinguished_from_bad_image_request(generation):
    g = generation
    g.sdk.models.get.side_effect = errors.APIError(400, {'error': {
        'message': 'API key not valid', 'details': [{'reason': 'API_KEY_INVALID'}]}})
    response = generate(g)
    assert response.status_code == 503
    assert 'API key' in response.json()['detail']


def test_inference_rate_limit_does_not_retry_or_save(generation):
    g = generation
    g.sdk.models.generate_content.side_effect = errors.APIError(429, {'error': {'message': 'Quota exceeded'}})
    assert generate(g).status_code == 429
    assert g.sdk.models.generate_content.call_count == 1
    assert g.store.get(g.task.id).tutorial is None


def test_network_failure_is_actionable_without_leaking_request(generation):
    g = generation
    g.sdk.models.get.side_effect = httpx.ConnectError('secret network detail')
    response = generate(g)
    assert response.status_code == 502
    assert 'secret' not in response.text
    assert 'connection' in response.json()['detail']


@pytest.mark.parametrize('field,value', [('step_id', 999), ('title', 'x' * 161), ('verification_criteria', []), ('unexpected', 'extra')])
def test_strict_local_validation_survives_portable_provider_schema(generation, field, value):
    g = generation
    g.output['steps'][0][field] = value
    g.sdk.models.generate_content.return_value = SimpleNamespace(text=json.dumps(g.output))
    assert generate(g).status_code == 502
    assert g.sdk.models.generate_content.call_count == 2
    assert g.store.get(g.task.id).tutorial is None


def test_configured_thinking_level_is_sent_without_changing_model(generation):
    g = generation
    g.service.settings.gemini_thinking_level = 'low'
    assert generate(g).status_code == 200
    kwargs = g.sdk.models.generate_content.call_args.kwargs
    assert kwargs['model'] == 'test-model'
    assert kwargs['config'].thinking_config.thinking_level.value == 'LOW'


def test_inference_high_demand_error_is_explicit_and_not_retried(generation):
    g = generation
    g.sdk.models.generate_content.side_effect = errors.APIError(503, {'error': {'message': 'This model is currently experiencing high demand.'}})
    response = generate(g)
    assert response.status_code == 503
    assert 'high demand' in response.json()['detail']
    assert 'No new tutorial was saved' in response.json()['detail']
    assert g.sdk.models.generate_content.call_count == 1
    assert g.store.get(g.task.id).tutorial is None

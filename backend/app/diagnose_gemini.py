"""One bounded live diagnostic per invocation; never changes saved task data.

From backend/: .venv/bin/python -m app.diagnose_gemini TASK_ID --stage plain
Intentional reference images are sent to Google. No credentials/images/AI text
are printed; output contains timings, finish reasons and token usage only.
"""
import argparse
import json
import time

from google.genai import errors, types
import httpx

from .config import Settings
from .services.gemini import GeminiError, GeminiService, api_error
from .services.storage import StorageError, TaskStore


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task_id')
    parser.add_argument('--stage', choices=['plain', 'json'], default='plain')
    parser.add_argument('--model', help='Override the model for this diagnostic only; does not edit .env.')
    parser.add_argument('--timeout', type=int, default=30, choices=range(5, 121), metavar='5-120')
    args = parser.parse_args()
    settings = Settings()
    if args.model:
        settings.gemini_model = args.model
    service = GeminiService(settings)
    started = time.monotonic()
    try:
        _, images = TaskStore(settings.data_dir).generation_snapshot(args.task_id)
        key, model = service.configuration()
        parts = [types.Part.from_text(text='These images are chronological completed states. Describe the visible state in each image briefly and in order. Do not infer hidden properties.')]
        parts.extend(types.Part.from_bytes(data=jpeg, mime_type='image/jpeg') for jpeg in images)
        config = types.GenerateContentConfig(max_output_tokens=2048,
            thinking_config=types.ThinkingConfig(thinking_level=settings.gemini_thinking_level.upper()) if settings.gemini_thinking_level else None,
            http_options=types.HttpOptions(timeout=args.timeout * 1000))
        if args.stage == 'json':
            config.response_mime_type = 'application/json'
            config.response_json_schema = {'type': 'object', 'properties': {
                'states': {'type': 'array', 'items': {'type': 'string'}}}, 'required': ['states']}
        print(json.dumps({'stage': args.stage, 'model': model, 'image_count': len(images),
                          'jpeg_bytes': sum(map(len, images))}), flush=True)
        with service._client(key) as client:
            response = client.models.generate_content(model=model,
                contents=[types.Content(role='user', parts=parts)], config=config)
        text = response.text or ''
        valid = bool(text)
        if args.stage == 'json':
            try:
                states = json.loads(text)['states']
                valid = isinstance(states, list) and len(states) == len(images) and all(isinstance(state, str) and state.strip() for state in states)
            except (ValueError, KeyError, TypeError):
                valid = False
        print(json.dumps({'elapsed_seconds': round(time.monotonic() - started, 2),
            'valid_response': valid, 'finish_reasons': [str(c.finish_reason) for c in response.candidates or []],
            'usage': response.usage_metadata.model_dump(exclude_none=True) if response.usage_metadata else None}), flush=True)
        return 0 if valid else 1
    except errors.APIError as exc:
        error = api_error(exc)
        print(json.dumps({'elapsed_seconds': round(time.monotonic() - started, 2),
                          'provider_status': exc.code, 'error': str(error)}), flush=True)
    except (GeminiError, StorageError) as exc:
        print(json.dumps({'error': str(exc)}), flush=True)
    except httpx.RequestError as exc:
        print(json.dumps({'elapsed_seconds': round(time.monotonic() - started, 2),
                          'network_error': type(exc).__name__}), flush=True)
    return 1


if __name__ == '__main__':
    raise SystemExit(run())

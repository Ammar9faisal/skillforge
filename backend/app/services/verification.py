"""Single-process learning sessions; progress is established only by real assessments.

Sessions expire after 30 minutes idle and are reset on backend restart. Only the
latest image pair is retained in memory, never written to task storage.
"""
import base64
from threading import RLock
from time import monotonic
from uuid import uuid4

from fastapi import HTTPException

from ..models import timestamp
from .camera import CameraUnavailable


class VerificationService:
    def __init__(self):
        self.sessions = {}
        self.lock = RLock()

    @staticmethod
    def _task(store, task_id):
        task = store.get(task_id)
        if not task.tutorial:
            raise HTTPException(409, 'Generate a tutorial before starting a learning session.')
        return task

    def _lookup(self, task_id, session_id, task):
        state = self.sessions.get(session_id)
        if state and not state['busy'] and monotonic() - state['touched'] >= 1800:
            self.sessions.pop(session_id)
            state = None
        if not state or state['task_id'] != task_id:
            raise HTTPException(409, 'Learning session expired. Start a new session; no progress was restored from browser data.')
        if state['version'] != task.tutorial.generated_at:
            raise HTTPException(409, 'Tutorial changed. Refresh saved data and start a new learning session.')
        state['touched'] = monotonic()
        return state

    @staticmethod
    def _view(state, task):
        ids = [step.step_id for step in task.tutorial.steps]
        done = state['completed']
        return {'session_id': state['id'], 'tutorial_version': state['version'],
                'completed_step_ids': list(done), 'active_step_id': next((i for i in ids if i not in done), None),
                'total': len(ids), 'complete': len(done) == len(ids), 'last_result': state['last'],
                'busy': state['busy']}

    def open(self, store, task_id, body):
        with self.lock:
            task = self._task(store, task_id)
            if body.tutorial_version != task.tutorial.generated_at:
                raise HTTPException(409, 'Tutorial changed. Refresh saved data before practicing.')
            now = monotonic()
            self.sessions = {k: s for k, s in self.sessions.items() if s['busy'] or now - s['touched'] < 1800}
            state = self.sessions.get(body.session_id)
            resumed = state is not None and state['task_id'] == task_id and state['version'] == task.tutorial.generated_at
            if not resumed:
                if len(self.sessions) >= 32:
                    idle = [s for s in self.sessions.values() if not s['busy']]
                    if not idle:
                        raise HTTPException(503, 'All local learning sessions are busy. Try again shortly.')
                    self.sessions.pop(min(idle, key=lambda s: s['touched'])['id'])
                sid = uuid4().hex
                state = {'id': sid, 'task_id': task_id, 'version': task.tutorial.generated_at,
                         'completed': [], 'last': None, 'busy': False, 'revision': 0, 'touched': now}
                self.sessions[sid] = state
            state['touched'] = now
            return {**self._view(state, task), 'resumed': resumed}

    def reset(self, store, task_id, session_id):
        with self.lock:
            task = self._task(store, task_id)
            state = self._lookup(task_id, session_id, task)
            state['revision'] += 1
            state['completed'] = []
            state['last'] = None
            # An in-flight request may finish, but its old revision cannot commit.
            return self._view(state, task)

    def verify(self, store, camera, gemini, task_id, body):
        with self.lock:
            task = self._task(store, task_id)
            state = self._lookup(task_id, body.session_id, task)
            if state['busy']:
                raise HTTPException(409, 'Verification is already running. Wait for the result before retrying.')
            active = self._view(state, task)['active_step_id']
            if active != body.step_id:
                raise HTTPException(409, 'Only the current unverified step can be assessed. Refresh the learning session.')
            step = next(s for s in task.tutorial.steps if s.step_id == active)
            checkpoint = next((c for c in task.checkpoints if c.reference_image == step.reference_image), None)
            if not checkpoint:
                raise HTTPException(409, 'Reference checkpoint is missing. Regenerate this tutorial.')
            reference = store.image(task_id, checkpoint.id)
            revision = state['revision']
            state['busy'] = True
        try:
            try:
                source_revision = getattr(camera, 'source_revision', None)
                learner = camera.jpeg()
            except CameraUnavailable as exc:
                raise HTTPException(503, str(exc)) from exc
            store.validate_jpeg(learner)
            if len(reference) + len(learner) > 12 * 1024 * 1024:
                raise HTTPException(413, 'Images are too large. Reduce camera resolution before verifying.')
            result, model = gemini.verify_images(step, reference, learner)
            with self.lock, store.lock:
                if isinstance(source_revision, tuple) and camera.source_revision != source_revision:
                    raise HTTPException(409, 'Camera source changed during verification. Result discarded; verify again.')
                current = self._task(store, task_id)
                if current.updated_at != task.updated_at or state['revision'] != revision:
                    raise HTTPException(409, 'Task or session changed during verification. Result discarded; no progress changed.')
                assessment = {**result.model_dump(), 'step_id': active, 'model': model,
                              'assessed_at': timestamp(), 'reference_image': step.reference_image,
                              'reference_data_url': 'data:image/jpeg;base64,' + base64.b64encode(reference).decode('ascii'),
                              'learner_data_url': 'data:image/jpeg;base64,' + base64.b64encode(learner).decode('ascii')}
                state['last'] = assessment
                if result.status == 'PASS':
                    state['completed'].append(active)
                state['busy'] = False
                state['touched'] = monotonic()
                return self._view(state, current)
        finally:
            with self.lock:
                state['busy'] = False

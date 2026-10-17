from fastapi import APIRouter, HTTPException, Request, Response

from ..models import CheckpointInput, CreateTask, Task, SessionInput, VerifyInput
from ..services.camera import CameraUnavailable

router = APIRouter(prefix='/api/tasks', tags=['tasks'])


@router.post('', response_model=Task, status_code=201)
def create_task(body: CreateTask, request: Request):
    return request.app.state.store.create(body.title)


@router.get('', response_model=list[Task])
def list_tasks(request: Request):
    return request.app.state.store.list()


@router.get('/{task_id}', response_model=Task)
def get_task(task_id: str, request: Request):
    return request.app.state.store.get(task_id)


@router.post('/{task_id}/generate', response_model=Task)
def generate_tutorial(task_id: str, request: Request):
    return request.app.state.gemini.generate(request.app.state.store, task_id)


@router.post('/{task_id}/sessions')
def open_session(task_id: str, body: SessionInput, request: Request):
    return request.app.state.verification.open(request.app.state.store, task_id, body)


@router.post('/{task_id}/sessions/{session_id}/reset')
def reset_session(task_id: str, session_id: str, request: Request):
    return request.app.state.verification.reset(request.app.state.store, task_id, session_id)


@router.post('/{task_id}/verify')
def verify_step(task_id: str, body: VerifyInput, request: Request):
    state = request.app.state
    return state.verification.verify(state.store, state.camera, state.gemini, task_id, body)


@router.patch('/{task_id}', response_model=Task)
def rename_task(task_id: str, body: CreateTask, request: Request):
    return request.app.state.store.rename(task_id, body.title)


@router.delete('/{task_id}', status_code=204)
def delete_task(task_id: str, request: Request):
    request.app.state.store.delete(task_id)
    return Response(status_code=204)


def capture(request, task_id, note, checkpoint_id=None):
    # Check task existence before touching the camera.
    request.app.state.store.get(task_id)
    try:
        jpeg = request.app.state.camera.jpeg()
    except CameraUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    return request.app.state.store.capture(task_id, jpeg, note, checkpoint_id)


@router.post('/{task_id}/steps', response_model=Task, status_code=201)
def capture_checkpoint(task_id: str, body: CheckpointInput, request: Request):
    return capture(request, task_id, body.note)


@router.put('/{task_id}/steps/{checkpoint_id}', response_model=Task)
def retake_checkpoint(task_id: str, checkpoint_id: str, body: CheckpointInput, request: Request):
    return capture(request, task_id, body.note, checkpoint_id)


@router.patch('/{task_id}/steps/{checkpoint_id}', response_model=Task)
def update_note(task_id: str, checkpoint_id: str, body: CheckpointInput, request: Request):
    return request.app.state.store.update_note(task_id, checkpoint_id, body.note)


@router.delete('/{task_id}/steps/{checkpoint_id}', response_model=Task)
def delete_checkpoint(task_id: str, checkpoint_id: str, request: Request):
    return request.app.state.store.delete_checkpoint(task_id, checkpoint_id)


@router.get('/{task_id}/steps/{checkpoint_id}/image')
def reference_image(task_id: str, checkpoint_id: str, request: Request):
    return Response(request.app.state.store.image(task_id, checkpoint_id), media_type='image/jpeg', headers={'Cache-Control': 'no-store'})

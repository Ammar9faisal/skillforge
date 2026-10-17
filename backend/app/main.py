from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from .config import Settings
from .services.camera import CameraUnavailable, OpenCVCamera
from .services.storage import StorageError, TaskStore
from .services.gemini import GeminiError, GeminiService
from .services.verification import VerificationService
from .routes.tasks import router as tasks_router

settings = Settings()
camera = OpenCVCamera(settings.camera_index, settings.camera_width, settings.camera_height)


@asynccontextmanager
async def lifespan(app):
    camera.start()
    try:
        yield
    finally:
        camera.stop()


app = FastAPI(title='SkillForge', lifespan=lifespan)
app.state.camera = camera
app.state.store = TaskStore(settings.data_dir)
app.state.gemini = GeminiService(settings)
app.state.verification = VerificationService()
app.include_router(tasks_router)
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin, 'http://127.0.0.1:3000'], allow_methods=['GET', 'POST', 'PATCH', 'PUT', 'DELETE'], allow_headers=['Content-Type'])


@app.exception_handler(StorageError)
async def storage_error(request, exc):
    return JSONResponse(status_code=exc.status_code, content={'detail': str(exc)})


@app.exception_handler(GeminiError)
async def gemini_error(request, exc):
    return JSONResponse(status_code=exc.status_code, content={'detail': str(exc)})


@app.exception_handler(OSError)
async def disk_error(request, exc):
    return JSONResponse(status_code=500, content={'detail': 'Local storage operation failed. Check free disk space and directory permissions.'})


@app.get('/api/health')
def health():
    return {'status': 'ok', 'camera': camera.status(), 'milestone': 5}


@app.post('/api/gemini/check')
def check_gemini():
    return app.state.gemini.check()


@app.get('/api/camera/status')
def camera_status():
    return camera.status()


class CameraSelection(BaseModel):
    index: int = Field(ge=0, le=20)


@app.post('/api/camera/reconnect')
def reconnect(selection: CameraSelection):
    try:
        camera.reconnect(selection.index)
    except CameraUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    return camera.status()


@app.get('/api/camera/frame')
def frame():
    try:
        return Response(camera.jpeg(), media_type='image/jpeg', headers={'Cache-Control': 'no-store'})
    except CameraUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get('/api/camera/stream')
def stream():
    try:
        first = camera.jpeg()
    except CameraUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc

    async def frames():
        jpeg = first
        while True:
            yield (b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '
                   + str(len(jpeg)).encode('ascii') + b'\r\n\r\n' + jpeg + b'\r\n')
            await asyncio.sleep(1 / 15)
            try:
                jpeg = camera.jpeg(85)
            except CameraUnavailable:
                break

    return StreamingResponse(frames(), media_type='multipart/x-mixed-replace; boundary=frame', headers={'Cache-Control': 'no-store'})

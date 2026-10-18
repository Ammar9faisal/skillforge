"""Local-only native frame ingress, separate from user task/image persistence."""
import math
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import Field, model_validator

from ..models import InputModel
from ..services.received_camera import ReceivedCamera
from ..services.camera import CameraUnavailable

router = APIRouter(prefix='/api/camera', tags=['camera sources'])


class BridgeStart(InputModel):
    window_id: int = Field(strict=True, ge=1, le=2**32 - 1)
    crop: tuple[float, float, float, float]
    fps: float = Field(default=2, ge=0.2, le=10, allow_inf_nan=False)

    @model_validator(mode='after')
    def valid_crop(self):
        x, y, width, height = self.crop
        if not all(math.isfinite(v) for v in self.crop) or min(x, y) < 0 or min(width, height) <= 0 or x + width > 1.000001 or y + height > 1.000001:
            raise ValueError('Crop must be normalized x,y,width,height within the window.')
        return self


def local_helper(request):
    if not request.client or request.client.host not in ('127.0.0.1', '::1') or request.headers.get('origin'):
        raise HTTPException(403, 'Native capture ingress accepts local helper requests only, without a browser Origin.')


def token(authorization):
    return authorization.removeprefix('Bearer ') if authorization and authorization.startswith('Bearer ') else ''


@router.post('/whatsapp/start')
def start_bridge(body: BridgeStart, request: Request):
    local_helper(request)
    from fastapi.responses import JSONResponse
    return JSONResponse(request.app.state.whatsapp.start_bridge(body.window_id, body.crop, body.fps), headers={'Cache-Control': 'no-store'})


@router.post('/whatsapp/frame')
async def receive_frame(request: Request, authorization: str | None = Header(default=None),
                        x_sequence: int = Header(ge=1), x_captured_at: float = Header()):
    local_helper(request)
    if request.headers.get('content-type', '').split(';')[0] != 'image/jpeg':
        raise HTTPException(415, 'Use Content-Type: image/jpeg.')
    # Bound streamed/chunked bodies as well as requests with Content-Length.
    jpeg = bytearray()
    async for chunk in request.stream():
        jpeg.extend(chunk)
        if len(jpeg) > ReceivedCamera.MAX_BYTES:
            raise HTTPException(413, 'JPEG exceeds the 4 MB frame limit.')
    return request.app.state.whatsapp.receive(bytes(jpeg), token(authorization), x_sequence, x_captured_at)


@router.post('/whatsapp/stop', status_code=204)
def stop_bridge(request: Request, authorization: str | None = Header(default=None)):
    local_helper(request)
    request.app.state.whatsapp.stop_bridge(token(authorization))
    return Response(status_code=204)


class SourceSelection(InputModel):
    source: Literal['webcam', 'whatsapp']
    index: int | None = Field(default=None, strict=True, ge=0, le=20)


@router.post('/source')
def select_source(body: SourceSelection, request: Request):
    try:
        return request.app.state.camera.select(body.source, body.index)
    except CameraUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@router.get('/whatsapp/status')
def whatsapp_status(request: Request):
    return request.app.state.whatsapp.status()

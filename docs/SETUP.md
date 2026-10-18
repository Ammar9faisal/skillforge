# SkillForge — setup and presenter quick start

## Requirements

- macOS for the tested camera setup; the optional window helper requires macOS 14+ and Swift/Xcode Command Line Tools.
- Python 3.11+, Node.js 20.9+ and npm.
- A camera exposed to macOS. GoPro Webcam must be installed/running for the tested GoPro path.
- A Google API key with access to an image-capable Gemini model supporting structured output. Inference requires internet access.

Run commands from the repository root unless a block says otherwise. Never overwrite an existing `.env` containing your key.

## First-time installation

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
if [ ! -f backend/.env ]; then cp backend/.env.example backend/.env; fi
cd frontend
npm ci
```

Edit `backend/.env` locally. Set `GEMINI_API_KEY` and `GEMINI_MODEL`. The environment example includes the model and thinking setting used in prior project validation; model access can vary. Keep keys out of frontend variables, recordings and Git. Do not paste them into chat.

The main settings are:

| Setting | Purpose |
| --- | --- |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Backend-only credentials and explicit model selection. No silent model fallback. |
| `GEMINI_TIMEOUT_SECONDS` | Per-request timeout, default 120 seconds. Whole UI actions may take longer due to metadata checks/validation retry. |
| `GEMINI_THINKING_LEVEL` | Optional model-dependent setting. Remove if unsupported by your selected model. |
| `CAMERA_SOURCE` | Startup source: `webcam` by default, or `whatsapp`. |
| `CAMERA_INDEX` | Webcam startup device, default 0. Indexes depend on connected devices. |
| `CAMERA_WIDTH` / `CAMERA_HEIGHT` | Requested dimensions; actual camera output can differ. |
| `DATA_DIR` | Optional local task storage override. Default `backend/data/tasks`. |
| `FRONTEND_ORIGIN` | Allowed frontend origin; local defaults support port 3000. |

Restart the backend after changing settings. Existing saved task data is not bundled for a fresh clone because `backend/data/` is ignored by Git.

## Run the app

Terminal 1, from the repository root:

```sh
cd backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --timeout-graceful-shutdown 3
```

Terminal 2, from the repository root:

```sh
cd frontend
npm run dev
```

Open **http://localhost:3000**. Run one backend worker without reload so one process owns the camera. If a port is occupied, check the existing server before starting another. Ctrl+C in each terminal stops that server; close preview tabs first when convenient.

The backend must launch from `backend/` to find its `.env`. If needed, copy `frontend/.env.example` to `frontend/.env.local` only when that file does not already exist; `NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000`. Restart Next.js after changing it. Keep both servers bound to loopback; this app has no authentication for public deployment.

## Choose a camera

For webcam/GoPro, allow Camera access for the launching terminal/IDE in macOS Privacy & Security. In Teach or Learn select **USB Webcam**, enter the device index and click **Reconnect**. Wait for the actual image. Current tested mapping: 0 built-in, 1 HERO9 Black, 2 OBS Virtual Camera. It is not a fixed mapping; FFmpeg’s numbers can differ from OpenCV’s.

The GoPro may take a few seconds to start. Brief missed reads recover; frames older than three seconds remain unavailable and sustained dropouts stop capture. If no image appears, check the GoPro utility preview and connection, then reconnect. One successful frame does not establish long-term reliability.

For Ray-Bans, connect the WhatsApp video call yourself and follow [the native helper instructions](../native/macos-camera/README.md). In terminal 3, from the root:

```sh
./native/macos-camera/run.sh permission --request
./native/macos-camera/run.sh stream --select --crop 0.273,0.055,0.454,0.852 --fps 2
```

Grant Screen Recording permission as macOS requests. Select the call window and choose **WhatsApp Ray-Bans** in SkillForge. The crop matches the tested call layout; inspect a snapshot and adjust for yours. Keep the call size fixed. Reopened windows need a new selection. The helper does not control WhatsApp or use its internal APIs. This path is distinct from GoPro and does not need to run for USB capture.

## First complete workflow

1. Create a skill, choose a camera and capture three to five visibly different completed states. Two checkpoints is the minimum for generation.
2. Save title/notes, acknowledge the image disclosure and select **Generate tutorial**. This sends the saved images, title and notes to Google. Review the output before using it.
3. Start learning, acknowledge verification’s image disclosure, and frame the active completed state. **Verify step** sends that learner still and its matching reference to Google.
4. Inspect feedback and the exact image pair. Only PASS advances. FAIL/UNCERTAIN keep the active step. Browsing another reference does not complete a step.
5. Refresh to resume a valid session. Reset clears learning progress without editing the tutorial. Backend restart, session expiry or eviction starts learning progress over; saved demonstrations/tutorials remain.

Local preview and tutorial browsing make no inference requests. Intentional checkpoints are saved locally; the latest learner comparison pair is held in backend memory. Neither model feedback nor generated safety notes certify hidden function or physical safety.

## Quick diagnostics

- Backend: open `http://127.0.0.1:8000/api/health`. An OK service can still report an unavailable camera.
- Selected source: open `http://127.0.0.1:8000/api/camera/status`.
- Current JPEG: open `http://127.0.0.1:8000/api/camera/frame`; refresh for a new still.
- **Check Gemini connection** checks model metadata access only; actual image generation is a separate check.
- API quota/high-demand/timeout: show the error, preserve progress and retry intentionally later. No automatic alternate model is selected.
- Tutorial cleared after an edit: regenerate from the updated checkpoints. Preserve the prepared demo by editing a separate task.
- Never delete user skills or reset macOS permissions globally as a troubleshooting shortcut.

## Automated checks

Backend, from root:

```sh
backend/.venv/bin/python -m pytest -q backend/tests
```

Frontend, from root:

```sh
cd frontend
npm test
npm run typecheck
npm run build
```

Stop the frontend dev server before the production build because both use `.next`. Start it again afterward. Native helper checks, from root: `./native/macos-camera/test.sh` and `./native/macos-camera/run.sh build`.

These checks cannot replace a physical camera/demo rehearsal. [PLAN.md](../PLAN.md) records completed validation; milestone 7’s two full physical runs and backup recording are still outstanding. For the presentation use [DEMO_SCRIPT.md](DEMO_SCRIPT.md); [PITCH.md](PITCH.md) and [DEVPOST.md](DEVPOST.md) contain the judging/submission drafts.

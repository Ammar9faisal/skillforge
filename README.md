# SkillForge

**Show it once. Learn it anywhere.** A physical skills learning project for Hack the Valley 11.

## Current state

Milestones 1–6 are implemented and verified. Milestone 8’s demo script, pitch, Devpost draft and setup guide are prepared. Milestone 7 remains open: two complete physical runs, extended recovery checks and a backup recording. The saved PS5 Controller Disassembly demonstration has four real AI-generated steps. Camera support includes webcam/GoPro and the optional WhatsApp Ray-Ban window bridge; see PLAN.md for bounded test evidence and limitations.

## Presentation and submission

- [90-second demo script and fallback cues](docs/DEMO_SCRIPT.md)
- [Pitch, impact framing and judge Q&A](docs/PITCH.md)
- [Devpost draft and missing submission fields](docs/DEVPOST.md)
- [Setup, daily launch and camera troubleshooting](docs/SETUP.md)

The Devpost draft is not published. Team names, public repository and a real demo-video link still need to be supplied. No backup recording or public deployment is claimed.

## Setup (macOS, Python 3.11+, Node 20.9+)

Terminal 1, from the repository root:

```sh
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
if [ ! -f backend/.env ]; then cp backend/.env.example backend/.env; fi
cd backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --timeout-graceful-shutdown 3
```

Run exactly one backend worker, without reload: one process must own the camera. Allow camera access for the terminal/IDE in **System Settings → Privacy & Security → Camera**, then restart the backend if necessary.

The graceful shutdown timeout prevents an open MJPEG preview from delaying server exit indefinitely. Close live-preview tabs before stopping the server when possible.

Terminal 2:

```sh
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000. Device 0 is the default; select 1 and Reconnect to try an external USB camera. Camera selection applies to this backend session. Set `CAMERA_INDEX` in `backend/.env` for persistent selection. Disconnect errors appear in the interface; reconnect manually after reconnecting hardware. Frames older than three seconds are rejected.

The built-in camera was verified at index 0. With the GoPro attached, HERO9 Black was verified at OpenCV index 1. Actual camera resolutions may differ from the requested resolution. The interface reports the actual dimensions.

The backend reads `.env` from its working directory, so launch it from `backend/`. Frontend API override: copy `frontend/.env.example` to `frontend/.env.local`. Backend CORS allows `http://localhost:3000` and `http://127.0.0.1:3000`; adjust `FRONTEND_ORIGIN` if needed. Keep development servers bound to loopback.

Copy the environment example only on first setup; do not overwrite an existing `.env` containing your key.

## Checks

```sh
cd backend
.venv/bin/pytest -q
```

```sh
cd frontend
npm test
npm run typecheck
npm run build
```

Automated camera tests mock hardware; they do not prove the USB camera works.

The build script uses Next.js's webpack compiler: Turbopack could not open its internal compiler port in this environment.

## Teach Mode

Select **Create new skill**, enter a title, then capture a checkpoint after each completed physical step. Notes are optional. Select **Save note** or the title save icon to persist edits; unsaved text is not retained after navigation. Retake replaces a checkpoint with the current camera image, keeping its ID and timeline position. Delete removes the selected checkpoint and renumbers subsequent positions. Capture, retake, note changes, and title changes update local metadata immediately.

Images and JSON metadata live under `backend/data/tasks/<server-generated-id>/`, which is excluded from Git. Override `DATA_DIR` in `backend/.env` if needed. Tasks are reopened through a stable URL such as `/?task=<id>`. The dashboard counts only actual saved records and checkpoints and labels generated tutorials separately from drafts. Maximum 24 checkpoints per skill.

The dashboard's delete control removes an entire skill and its images after confirmation. Deleted images cannot be recovered through the app. Reference images can be inspected at full size by clicking their thumbnails.

## Gemini tutorial generation

Install the updated backend dependencies, then set these in `backend/.env`:

```dotenv
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-3.6-flash
GEMINI_TIMEOUT_SECONDS=120
GEMINI_THINKING_LEVEL=low
```

Keep the key in the backend environment and out of chat, screenshots, and Git. Restart FastAPI after changing settings. `gemini-3.6-flash` was verified with the configured key and the real four-checkpoint demonstration on October 17, 2026. Gemini 3.8 Flash returned an explicit high-demand 503 even for a plain four-image request, so the user authorized testing another Flash model. No model is assumed when `GEMINI_MODEL` is missing, no automatic model substitution occurs, and access is checked again before every generation request.

In Teach Mode, capture at least two checkpoints (prefer three to five). Save any title or note edits. Select **Check Gemini connection** to verify model metadata access without uploading images. This does not yet prove image or structured-output compatibility. Check the disclosure beside the Generate button, then select **Generate tutorial**. All saved checkpoint images, notes, and the title are sent in chronological order to Google's API. The camera does not need to remain connected during generation.

The generated tutorial appears below the task builder, with reference images, instructions, visual verification criteria, and safety notes. It is stored inside `task.json`, including model name and generation time, and survives refresh/restart. Review its claims against the reference images before use. The first checkpoint has no preceding empty-state reference, so the prompt explicitly forbids inventing unseen setup actions.

Changing a checkpoint image, note, or title invalidates the old tutorial. Generation runs against an immutable snapshot; concurrent edits cause a 409 response instead of saving an outdated result. Concurrent generation of the same task is rejected. Failed regeneration preserves an existing tutorial if the source task has not changed.

The service uses the [official Google GenAI SDK](https://googleapis.github.io/python-genai/) with native JSON structured outputs and inline JPEG parts. A portable structural schema is derived from Pydantic; strict ranges, lengths, extra-field checks and filename constraints are validated locally. This avoids provider rejection of unsupported schema constraints. The request uses the SDK's public `response_mime_type` and `response_json_schema` configuration. A transport test checks the exact outgoing format, and an actual app request validated the complete integration. All reference images must exist and decode successfully. Results must contain exactly one step per checkpoint, with matching ordered IDs and reference names. Invalid output gets at most one controlled retry with validation feedback; API errors are not automatically retried. Errors for missing configuration, unavailable models, rate limits, timeouts, connection failures, and invalid output are shown explicitly.

Each Google request times out after `GEMINI_TIMEOUT_SECONDS` (5–120 seconds). A generation action includes a metadata check and at most two inference calls. The frontend waits up to 380 seconds. The verified four-image Gemini 3.6 Flash tutorial took 18.3 seconds; future latency can vary. Prepare a saved tutorial before a timed demo when needed. Google high-demand 503 responses are shown explicitly and are not automatically retried. Total JPEG input is limited to 12 MiB to leave room for request encoding and metadata. No hardcoded fallback tutorials are used.

`GEMINI_THINKING_LEVEL=low` uses a [Gemini thinking setting](https://ai.google.dev/gemini-api/docs/thinking). It was validated with Gemini 3.6 Flash and can be omitted to use the model default. Check compatibility before setting it for another model; no alternate model is selected automatically.

## Isolating Gemini errors

Run one bounded request at a time from `backend/` using an existing task ID. These commands send that task’s intentional reference images to Google but do not modify the task or save a tutorial:

```sh
.venv/bin/python -m app.diagnose_gemini TASK_ID --stage plain
.venv/bin/python -m app.diagnose_gemini TASK_ID --stage json
```

Use `--model MODEL_ID` for a diagnostic-only model override, or `--timeout 60` to change its default 30-second timeout. The command prints the image count, JPEG byte count, elapsed time, provider status or finish reason, and actual token usage when available. It does not print keys, image bytes, or AI response text. A metadata-only connection check cannot prove model generation capacity.

Measured on October 17, 2026 using the same four images (782,949 total JPEG bytes):

| Request | Model | Result |
| --- | --- | --- |
| Plain description | Gemini 3.8 Flash | 503 high demand after 35.5 seconds |
| Plain description | Gemini 3.6 Flash | Valid response in 14.2 seconds |
| Minimal structured JSON | Gemini 3.6 Flash | Valid response in 6.8 seconds |
| Full tutorial through the application | Gemini 3.6 Flash | HTTP 200, four validated steps saved in 18.3 seconds |

These measurements establish the latest 3.8 failure as provider overload independent of tutorial formatting. Earlier schema-format errors were separate integration defects; they do not explain every historical timeout.

## Manual milestone 3 checklist

- Set the backend key and model, restart FastAPI, and run **Check Gemini connection**.
- Capture three actual physical states with visible changes and meaningful notes.
- Confirm generation is disabled with fewer than two checkpoints, unsaved edits, or unchecked image disclosure.
- Generate and inspect one real instruction and reference per checkpoint, including visual criteria and any uncertainty notes.
- Refresh and restart the backend; confirm the saved generated tutorial remains.
- Change a checkpoint note or retake an image; confirm the old tutorial clears and can be regenerated.
- Test a missing key/model or unavailable model in a disposable environment: verify a clear error, with no fabricated tutorial.
- Verify the tutorial describes only visible changes, and never claims hidden electrical or functional correctness.

## Learn Mode

Select **Learn a skill** on the dashboard, **Learn mode** in navigation, or **Start learning** beneath a generated tutorial. The learning library lists only skills with generated tutorials. Directly opening a draft explains how to generate its tutorial in Teach Mode.

The Learn workspace presents the live camera, the selected instruction and instructor reference image, visual criteria and any safety notes, plus all ordered steps in a timeline. Use **Previous reference**, **Next reference**, or a timeline node to inspect each state. Open the reference at full size with its external-link icon. A preview of a future step is explicitly labeled; **Return to current step** brings you back to the active step.

Browsing does not complete a step. **Verify step** captures the current camera frame and compares it with that step’s instructor reference using Gemini. Only a validated PASS advances the active step. FAIL preserves the active step and shows an observable mismatch and correction. UNCERTAIN preserves the active step and asks for a better view or human inspection. A low-confidence PASS is conservatively treated as UNCERTAIN. API failures are displayed as errors, never invented assessments.

The browser stores the selected reference position and an opaque server session ID, separately for each skill. Verified progress and the latest assessment are held by the backend, never trusted from browser storage. Sessions expire after 30 minutes idle, on backend restart, or when evicted from the 32-session local limit. Expired sessions reopen at zero with an explicit notice. Refreshing restores that position. Regenerating a tutorial resets the session to its first step, and invalid/corrupt browser data resets safely. **Reset session** clears backend progress and feedback and returns to step 1 without editing the tutorial or reference images. Browser storage failures show a notice and allow navigation in memory. Browsing a saved tutorial makes no Gemini requests, captures no learner stills, and incurs no inference cost.

## Visual verification (Milestone 5)

In Learn Mode, frame the current completed state, acknowledge the image disclosure, and click **Verify step**. The live feed continues while the captured still is assessed. Do not move to the next physical state until PASS. Feedback is labeled with its assessed step, model, time and qualitative confidence; the exact instructor and learner images sent to Gemini appear side by side. This is a visible-state assessment, not proof of hidden physical, mechanical or electrical correctness.

The backend enforces sequential progress and rejects skipped steps, duplicate submissions, missing/invalid images and stale results after a task edit or reset. Malformed output gets at most one validation retry; SDK network retries are disabled. Refreshing during a request reconnects to the session and polls for completion. If a network request is interrupted, refresh the learning session to reconcile progress before retrying. Browsing alone makes no AI requests.

API additions:

- `POST /api/tasks/{task_id}/sessions` with `{ "tutorial_version": "GENERATED_AT", "session_id": "OPTIONAL_EXISTING_ID" }` creates or resumes a session.
- `POST /api/tasks/{task_id}/verify` with `{ "session_id": "ID", "step_id": 1 }` captures a real current frame, assesses it and returns authoritative session progress and the latest result.
- `POST /api/tasks/{task_id}/sessions/{session_id}/reset` clears progress and feedback. Results already in flight are discarded.

Manual milestone 5 checklist:

- Open a generated tutorial and confirm Verify is disabled until the disclosure is acknowledged.
- Preview a future step and confirm it cannot be verified or marked complete.
- Show a clearly incorrect completed state; verify FAIL, expected/observed/correction text, the exact image pair and unchanged progress.
- Hide the required components or use a view that prevents assessment; verify UNCERTAIN and unchanged progress.
- Match the reference visibly; verify PASS, one-step advancement and the completed timeline label.
- Refresh; confirm the server’s actual progress and last feedback return. Finish all steps; confirm completion without advancing beyond the last step.
- Reset; confirm zero progress and cleared feedback, with instructor data unchanged.
- Test unavailable camera, missing reference, provider timeout/quota and invalid output: explicit errors, no fabricated assessment or progress.
- Restart the backend; confirm the session restarts at zero with an explanation.

## Visual polish (Milestone 6)

Learn Mode prioritizes the active instruction and Verify action, with readable criteria and references beneath. Wide screens retain the three-section workspace and a sticky timeline; narrower layouts stack sections and preserve navigation. Completed steps use checkmarks, active steps have a subtle pulse, and previews remain explicitly labeled. The live camera HUD uses a restrained scan sweep and a contrasting status strip; this decoration does not imply AI analysis of the continuous stream.

Verification feedback spans the workspace with distinct status icons, text and colors, expected/observed evidence, and a highlighted next action. **Inspect images** opens a larger comparison of the exact submitted image pair. It stacks the images on narrow screens and supports a labeled Close control and Escape. The learner image is explicitly labeled as a captured still. Session opening, assessment and reset show different loading messages. Motion is disabled for `prefers-reduced-motion: reduce`, and keyboard focus remains visible.

Manual polish checks:

- Review Dashboard, Teach and Learn navigation; the current page is indicated accessibly.
- Review Learn Mode at laptop widths and a narrow phone viewport; controls, long titles, criteria, timeline and feedback should wrap without clipping.
- Run a real verification; confirm the feedback names its assessed step and progress follows the backend result.
- Open Inspect images, compare A/B labels and image content, close with the button and Escape, and confirm focus returns to the invoking control.
- Confirm privacy disclosure, offline hints, preview hints, and session/reset/assessment loading labels remain explicit.
- Enable the operating system’s reduced-motion preference and confirm HUD, active-step and feedback animations stop.

## Manual milestone 4 checklist

- Open the learning library and select a generated tutorial.
- Confirm the tutorial title, live camera, current instruction, correct reference image and criteria are shown.
- Select Next reference: the text and image change, the panel says Preview, and verified progress stays zero.
- Refresh: the selected preview returns while the active step remains step 1.
- Select a later step in the timeline; confirm its own instruction/reference appear.
- At the first and last references, confirm the out-of-range navigation buttons are disabled.
- Select Return to current step or Reset session and confirm step 1 returns without altering the saved tutorial.
- Open a draft through a Learn URL; confirm the app explains that generation is required.
- Confirm Verify step is disabled for previewed steps, an offline camera, or before image disclosure is acknowledged.
- Test with the backend/camera unavailable: errors remain explicit; saved text can still be read if already loaded.

## Manual milestone 2 checklist

- Create a skill from the dashboard and confirm its editable title appears in Teach Mode.
- Capture three completed states; confirm the timeline has three ordered thumbnails.
- Add and save instructor notes, edit and save the title, then refresh the page.
- Stop and restart the backend; reopen the skill and confirm the title, notes, and all three images remain.
- Retake the middle checkpoint; confirm its thumbnail changes and its position stays second.
- Delete the middle checkpoint; confirm the remaining positions become 1 and 2.
- Capture another checkpoint; confirm it becomes position 3.
- Disconnect or stop the camera; capture and retake should become unavailable and produce explicit API errors if requested directly.
- Visit the dashboard; check counts against the saved task data.
- Delete a disposable test skill and confirm its directory and images are removed.
- Stop the backend; refresh saved data and confirm a visible error rather than fabricated records.

## Manual milestone 1 checklist

- Start both servers; health responds at http://localhost:8000/api/health.
- Confirm live preview shows the actual workspace, moving your hand to verify freshness.
- Confirm status shows actual resolution and active camera.
- Try the USB device index; confirm the intended camera is used.
- Disconnect camera: offline message appears, stale frames cannot be captured.
- Reconnect hardware and click Reconnect: live preview recovers.
- Stop backend: frontend displays backend unavailable.
- Restart backend and frontend; preview recovers.

## API

- `GET /api/health`: service health and camera status.
- `GET /api/camera/status`: camera availability, selected device and resolution.
- `GET /api/camera/stream`: MJPEG; 503 when no valid frame exists.
- `GET /api/camera/frame`: current JPEG, for intentional diagnostics; no disk write.
- `POST /api/camera/reconnect` with `{"index":0}`: release current device and start selected input.
- `POST /api/gemini/check`: check configured model metadata access without sending images.
- `POST /api/tasks` with `{"title":"Colour assembly"}`: create a draft task.
- `GET /api/tasks`: list saved tasks with their checkpoints.
- `GET /api/tasks/{task_id}`: retrieve metadata and ordered checkpoints.
- `POST /api/tasks/{task_id}/generate`: send ordered reference images to Gemini and return updated task metadata with the validated tutorial. No request body required.
- `PATCH /api/tasks/{task_id}` with `{"title":"Updated title"}`: rename.
- `DELETE /api/tasks/{task_id}`: remove the task and all captured images.
- `POST /api/tasks/{task_id}/steps` with `{"note":"Optional note"}`: capture a new checkpoint; returns updated task metadata.
- `PUT /api/tasks/{task_id}/steps/{checkpoint_id}` with `{"note":"Optional note"}`: retake with the current frame; returns updated task metadata.
- `PATCH /api/tasks/{task_id}/steps/{checkpoint_id}` with `{"note":"Updated note"}`: save note.
- `DELETE /api/tasks/{task_id}/steps/{checkpoint_id}`: remove and renumber checkpoints.
- `GET /api/tasks/{task_id}/steps/{checkpoint_id}/image`: controlled reference JPEG endpoint. The client never supplies a filesystem path.

Checkpoint IDs are stable server-generated strings; display positions are sequential numbers. Metadata uses atomic file replacement. This is a single-process MVP: do not point multiple backend processes at the same storage directory.

The camera abstraction lives in `backend/app/services/camera.py`. Downstream services will consume normalized frames without webcam-specific logic. Only the capture thread opens the hardware. A future wearable camera adapter is planned, not implemented.

## Privacy

Preview stays local; continuous video is not recorded. Tutorial generation sends intentional saved reference images, title, and instructor notes to Google's Gemini API after the interface disclosure is acknowledged. Verification sends one intentionally captured learner frame and its instructor reference to Google after the disclosure is acknowledged. The exact pair and latest assessment remain in backend memory for the learning session; learner frames are not written to disk. Only the latest pair is retained, and reset clears it. Use consenting participants. Credentials belong only in backend environment variables. Raw image contents, raw AI responses, and credentials are not logged by the application.


## WhatsApp Ray-Bans camera

The native macOS ScreenCaptureKit helper forwards a configurable crop of the incoming call video at 2 FPS. It supports explicit window selection and runs without foregrounding WhatsApp. Start the backend, then run from the repository root:

```sh
./native/macos-camera/run.sh stream --select --crop 0.273,0.055,0.454,0.852 --fps 2
```

Select **WhatsApp Ray-Bans** under **Source** in Teach or Learn. USB Webcam and camera 0 remain available. The crop above matches the tested call layout; inspect a snapshot before using another layout. See [native setup, crop, preview and recovery instructions](native/macos-camera/README.md) and [validation record](native/macos-camera/PLAN.md). The overlap test was skipped at the user’s request.

### GoPro webcam troubleshooting

A GoPro exposed through the GoPro Webcam utility uses the existing USB Webcam source. FFmpeg and OpenCV may enumerate devices in different orders; do not assume a number from FFmpeg is SkillForge’s index. On the tested Mac, OpenCV index 0 was FaceTime HD, 1 was HERO9 Black, and 2 was OBS Virtual Camera. These numbers can change with attached devices.

GoPro / AVFoundation can occasionally return an empty read during startup or otherwise successful streaming. SkillForge waits up to five seconds for initial video and tolerates brief missed reads thereafter. Existing frames still expire after three seconds, and a sustained dropout stops the reader with an explicit error. Restart the backend after updating this code, then reconnect the selected device.

### Live preview frame rate

The browser uses serial, uncached JPEG requests rather than a long-lived multipart stream, following Safari painting failures during rehearsal. USB webcam / GoPro preview targets 15 FPS; WhatsApp Ray-Ban preview remains at 2 FPS. Preview requests use `/api/camera/frame?preview=true`, capped at 960 pixels wide with JPEG quality 80 to reduce encoding and transfer work. Requests never overlap; slower encoding, networking, camera delivery or browser rendering reduces the achieved rate. Failed requests back off for one second.

Teach, Verify and the normal `/api/camera/frame` endpoint retain full capture resolution and JPEG quality 92. The MJPEG endpoint remains available for other clients. Restart both backend and frontend after this change; production frontend users must rebuild before `npm run start`. The 15 FPS value is a target, not a measured hardware guarantee.

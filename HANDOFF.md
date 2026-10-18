# SkillForge — Copilot handoff

Last updated October 18, 2026. Continue the existing application; do not scaffold a replacement.

## Objective and current milestone

SkillForge turns camera checkpoints of a physical demonstration into a Gemini tutorial, then compares a learner's camera image with each instructor reference. Stack: Next.js App Router, React, TypeScript, Tailwind, Lucide; FastAPI, OpenCV, Pydantic, official google-genai SDK; local JSON/JPEG task storage. Localhost hackathon MVP, no auth/cloud/database required.

Milestones 1–6 are implemented and verified. Read PLAN.md for the evidence and README.md for startup, API behavior and manual checklists. Milestone 8’s documentation pack is now prepared; milestone 7 (demo reliability) remains next. Work one milestone at a time and report what was implemented, tested, remaining and blocked.

## Workspace and startup

Workspace: `/Users/ammarfaisal/Desktop/skillforge` on macOS, zsh. The workspace is a Git repository with existing uncommitted work. Preserve existing work and user data.

Backend terminal:

```sh
cd /Users/ammarfaisal/Desktop/skillforge/backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --timeout-graceful-shutdown 3
```

Frontend terminal:

```sh
cd /Users/ammarfaisal/Desktop/skillforge/frontend
npm run dev
```

Frontend: http://localhost:3000 ; backend: http://localhost:8000 . Check whether servers already run before starting duplicates. Exactly one backend process should own the camera. Existing scripts use webpack because Turbopack encountered a local compiler-port failure.

Read `frontend/AGENTS.md` and relevant bundled Next documentation under `frontend/node_modules/next/dist/docs/` before frontend edits. Installed Next is 16.4.2; do not assume older conventions.

## Configuration and saved demonstration

- Credentials are already configured in `backend/.env`. Never print the file or expose its key.
- `GEMINI_MODEL=gemini-3.6-flash`, timeout 120 seconds, thinking level low.
- Webcam remains the default source. Current tested mapping: **0** built-in, **1** HERO9 Black, **2** OBS Virtual Camera. Indexes can change; do not assume FFmpeg’s order matches OpenCV. Preserve the user’s existing startup settings.
- Gemini 3.8 Flash repeatedly returned explicit provider high-demand 503 errors. User authorized testing another Flash model; 3.6 Flash succeeded. No silent model fallback.
- Current saved skill: **PS5 Controller Disassembly**, ID `99c74657b9fd4b6197edbf1ab064fa80`, four real images and four Gemini-generated steps. User explicitly approved using all four images.
- Learn URL: http://localhost:3000/?mode=learn&task=99c74657b9fd4b6197edbf1ab064fa80
- Tutorial: inspect assembled controller; position top edge toward camera; remove L1/R1 caps; remove lower front trim. Do not replace generated content with canned steps.
- Task JSON/JPEGs live in `backend/data/tasks/<task_id>/`. The older Wallet Phone task mentioned in historical logs is no longer present. Do not recreate it or delete current data.

## Architecture and important files

- `backend/app/main.py`: app lifecycle, single camera owner, camera/status/frame/MJPEG endpoints, shared services, error handlers.
- `backend/app/config.py`: environment settings with SecretStr credentials.
- `backend/app/models.py`: task/tutorial and strict verification/session request models.
- `backend/app/routes/tasks.py`: task CRUD, capture, generation, session and verification routes.
- `backend/app/services/storage.py`: validated image paths, JPEG checks, atomic task persistence, generation snapshots, tutorial invalidation on source edits.
- `backend/app/services/gemini.py`: real SDK requests, portable JSON schema projection, strict local validation, sanitized provider errors; `verify_images` compares the exact two supplied JPEGs.
- `backend/app/services/verification.py`: authoritative in-memory learning sessions, sequential progress, duplicate/stale request guards, reset, expiry and latest exact image pair.
- `frontend/app/page.tsx`: dashboard/Teach/Learn query-based navigation and task loading.
- `frontend/components/learn-mode.tsx`: session resume, preview navigation, disclosure, Verify action, progress/reset/completion.
- `frontend/components/verification-result.tsx`: PASS/FAIL/UNCERTAIN feedback plus exact submitted image pair.
- `frontend/components/camera-panel.tsx`: shared live preview/status/reconnect.
- `frontend/lib/api.ts`: API helpers and types. Verification permits up to 260 seconds for a bounded provider request plus one malformed-output retry.
- `frontend/lib/learning-session.ts`: browser reference browsing only; never establishes verified completion.
- `frontend/app/globals.css`: responsive dark/cyan HUD styling.

## Milestone 5 behavior and constraints

`POST /api/tasks/{task_id}/sessions` accepts `tutorial_version` (saved tutorial generated_at), plus optional existing `session_id`. Returns server progress, current step, completion, busy and latest assessment.

`POST /api/tasks/{task_id}/verify` accepts `{ "session_id": "...", "step_id": 1 }`. Captures a fresh real camera JPEG, retrieves the matching saved reference and criteria, calls Gemini and validates its result. Only PASS advances one step. FAIL/UNCERTAIN preserve the active step. Low-confidence PASS becomes UNCERTAIN. Unknown or skipped steps, duplicate requests, missing/invalid inputs and stale results are rejected. Failures never become fake AI assessments. One controlled malformed-output retry; SDK network retries disabled.

`POST /api/tasks/{task_id}/sessions/{session_id}/reset` clears progress and feedback, increments the session revision so in-flight old results cannot commit, and leaves instructor data intact.

Browser storage holds only reference browsing position and an opaque server session ID. Server sessions are in process memory: 30-minute idle expiry, maximum 32 sessions, oldest idle eviction. Restart resets progress and the UI explains that the old session expired. Latest reference/learner pair is kept only in memory; learner stills are not written to disk. Refresh resumes progress and feedback; refreshing during verification polls until completion.

The backend stopped during the interrupted turn and was restarted while completing this handoff. Consequently the earlier successful live session (1/4) has reset to zero. Saved instructor tutorial/images remain intact. That historical check found camera 0 unavailable; later GoPro validation supersedes it (see follow-ups below). Query current camera status rather than treating a historical health check as live state.

Image submission is intentional and disclosed in the UI. Browsing and camera preview do not call Gemini. Results are visible-state assessments, not proof of hidden mechanical/electrical correctness. No numerical confidence percentages.

## Verification already performed

- 84 backend tests passed, 8 frontend session tests passed, TypeScript check passed.
- Production build passed again after the interruption.
- Real Gemini 3.6 Flash comparisons: assembled reference vs identical image => PASS (3.36 s); front trim removed vs assembled => FAIL (4.42 s), naming detached trim; top-only view vs front inspection => UNCERTAIN (5.44 s), asking for a front view. These were explicitly recorded-image diagnostics, not substituted live camera inputs.
- Actual Safari Verify action with user-positioned assembled controller and camera 0 => real PASS, advanced step 1 to step 2, 1/4 timeline, exact submitted image pair displayed. Refresh restored real progress/feedback. Future-step preview kept step 2 active and disabled Verify.
- Complete progression/reset and race handling are automated-test verified. Two consecutive complete physical runs are still milestone 7 work; do not claim those have happened.
- Existing Starlette/httpx test-client deprecation warning remains, tests pass.
- Safari previously showed an empty MJPEG panel; intrinsic image sizing (`position: relative; height: auto`) fixed rendering during milestone 4. Preserve that sizing and multipart Content-Length headers. Check actual preview if changing camera CSS.

Run checks from the correct subdirectory:

```sh
cd /Users/ammarfaisal/Desktop/skillforge/backend
.venv/bin/python -m pytest -q
```

```sh
cd /Users/ammarfaisal/Desktop/skillforge/frontend
npm test
npm run typecheck
npm run build
```

## Next work

Milestone 6 is complete: compact learner workspace, prominent Verify action, readable feedback across the workspace, exact A/B evidence with an enlarged native dialog, responsive stacking, labeled outcomes/checkmarks, subtle camera/active-step animations, reduced-motion support, keyboard focus, and distinct session/assessment/reset loading labels. A fresh real live-camera UNCERTAIN result was displayed and inspected; progress remained zero. Safari checks covered laptop/narrow viewports, comparison images and dialog controls. See PLAN.md for validation. Continue with milestone 7; avoid broad rewrites or unnecessary dependencies.

Milestone 7: two full physical instructor-to-learner runs, restart/reconnect/error recovery checks, backup demo recording and critical fixes. Coordinate physical controller positioning with the user; never fabricate visual outcomes or substitute saved images for the production camera.

Milestone 8 is prepared: see the documentation pack below for the timed demo, pitch/Q&A, Devpost draft and setup guide. Publishing/sending submissions is separate from drafting.

Never expose credentials, silently switch models, mark completion through browser flags, advance on uncertainty, record continuous video, delete user demonstrations, or claim untested reliability. Keep the existing teach → generate → learn → verify loop working throughout.

## Native Ray-Bans camera extension

`native/macos-camera/run.sh` builds/signs the Swift ScreenCaptureKit helper; continuous forwarding uses a single persistent SCStream (`WindowFrameStream.swift`), while snapshots use SCScreenshotManager; see its README and PLAN. No WhatsApp UI control: user requested CLI-only work and skipped the overlap test. Crop tested: `0.273,0.055,0.454,0.852`; select the actual call window each time. IDs change, and resizing stops capture.

`ReceivedCamera` holds only the latest fresh JPEG-decoded frame with runtime upload lease, size/dimension/sequence/timestamp bounds. `CameraRouter` routes preview, Teach and Verify; USB remains the startup default, optionally `CAMERA_SOURCE=whatsapp`. POST `/api/camera/source` selects webcam or whatsapp. Native ingress lives at `/api/camera/whatsapp/start|frame|stop`, with read-only `/status`. Helpers accept loopback destinations only and reject redirects. Verify discards results after source/bridge changes.

Real forwarding, preview, Teach capture and USB 0 switching passed. Verify selected-source content was tested with mocked Gemini (no additional live model request). 110 backend / 8 frontend / 36 Swift checks and production build passed. ScreenCaptureKit failure stops capture; staleness prevents fallback or frozen backend frame reuse. This cannot detect a remote video frozen inside WhatsApp.

Persistent-stream follow-up: 250 real frames at 2 FPS over more than two minutes stayed fresh; graceful SIGTERM invalidated the frame and returned HTTP 503, then a helper restart restored capture. Repeated-screenshot errors described in native PLAN occurred before switching continuous forwarding to SCStream.

GoPro follow-up: HERO9 Black is OpenCV index 1 on this device configuration. One failed AVFoundation read previously terminated the camera thread; fixed with bounded initial/ongoing retries while preserving three-second freshness. 113 backend tests pass. Restarted backend and verified 30 seconds of app-level live polling: 27 fresh JPEG responses, zero failures after startup, 1920 × 1080. GoPro source left selected; prior reports that camera 1 was disabled predate the GoPro connection.

## Milestone 8 documentation pack

Prepared `docs/DEMO_SCRIPT.md`, `docs/PITCH.md`, `docs/DEVPOST.md` and `docs/SETUP.md`, linked from README. The 90-second script explicitly uses saved checkpoints and a prepared real tutorial, with live assessments and branches that never promise a particular AI result. Devpost remains an unpublished draft with team/repo/video fields to supply; there is no public deployment or recorded backup yet. This work did not call Gemini, change application code, capture new images or mutate saved skills. Milestone 8 is checked in PLAN; milestone 7 still requires two complete physical runs and the backup recording. Do not claim an end-to-end rehearsal, measured educational impact, direct Meta SDK integration or uninterrupted background camera reliability.

Preview FPS follow-up: serial JPEG preview now targets 15 FPS for USB/GoPro and 2 FPS for WhatsApp, using `/api/camera/frame?preview=true` (960-pixel maximum width, quality 80). Full-resolution checkpoint/Verify inputs remain unchanged. Request latency is included in each frame interval; failures back off for one second. 116 backend tests / eight frontend tests and typecheck pass. Restart/rebuild is needed to load the change; do not report measured 15 FPS without a live check.

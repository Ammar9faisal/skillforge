# SkillForge — Copilot handoff

Last updated October 17, 2026. Continue the existing application; do not scaffold a replacement.

## Objective and current milestone

SkillForge turns camera checkpoints of a physical demonstration into a Gemini tutorial, then compares a learner's camera image with each instructor reference. Stack: Next.js App Router, React, TypeScript, Tailwind, Lucide; FastAPI, OpenCV, Pydantic, official google-genai SDK; local JSON/JPEG task storage. Localhost hackathon MVP, no auth/cloud/database required.

Milestones 1–6 are implemented and verified. Read PLAN.md for the evidence and README.md for startup, API behavior and manual checklists. Next is milestone 7 (demo reliability), followed by milestone 8 (pitch). Work one milestone at a time and report what was implemented, tested, remaining and blocked.

## Workspace and startup

Workspace: `/Users/ammarfaisal/Desktop/skillforge` on macOS, zsh. The workspace was not a Git repository at last inspection. Preserve existing work and user data.

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
- User explicitly selected camera **0**; camera 1 is disabled. Keep `CAMERA_INDEX=0`.
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

The backend stopped during the interrupted turn and was restarted while completing this handoff. Consequently the earlier successful live session (1/4) has reset to zero. Saved instructor tutorial/images remain intact. The final health check reports backend status OK but camera 0 currently unavailable (no frame); reconnect camera 0 in the app when the device is available. Do not switch to disabled camera 1.

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

Milestone 8: concise 60–90-second demo script, pitch, honest limitations, Devpost draft and final setup docs. Publishing/sending submissions is separate from drafting.

Never expose credentials, silently switch models, mark completion through browser flags, advance on uncertainty, record continuous video, delete user demonstrations, or claim untested reliability. Keep the existing teach → generate → learn → verify loop working throughout.

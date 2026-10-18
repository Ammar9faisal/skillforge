# SkillForge implementation plan

Implement and test one milestone at a time. Never simulate live AI results.

- [x] 1. Foundation: FastAPI, Next.js, configurable single-owner camera, MJPEG, status, reconnect, setup. Gate: verify a real camera frame and live preview before Gemini work.
- [x] 2. Teach: persistent tasks, ordered checkpoints, notes, delete and retake.
- [x] 3. Generate: configured accessible Gemini model, validated structured tutorial, controlled retry.
- [x] 4. Learn: tutorial selection, reference, session progress and reset.
- [x] 5. Verify: real image comparison, PASS/FAIL/UNCERTAIN, advance only on PASS.
- [x] 6. Polish: responsive HUD, comparison, accessible loading and errors.
- [ ] 7. Reliability: focused automated tests, two real end-to-end runs, backup demo.
- [ ] 8. Pitch: honest limitations, demo script, Devpost draft and setup documentation.

## Verification log

### Milestone 1 — verified October 17, 2026

- Real JPEG retrieved from camera device 1. Safari reported an active MJPEG preview and actual frame dimensions. Device 0 failed explicitly.
- Backend camera tests, TypeScript checks, production build, and frontend HTTP 200 passed.
- Turbopack failed to open an internal compiler port; webpack build succeeds and is configured in package scripts.
- Browser screenshot capture returned a blank image; visual layout inspection remains limited. Native browser accessibility checks succeeded.
- No physical USB device identity or unplug/replug test has been independently confirmed.

### Milestone 2 — verified October 17, 2026

- Implemented dashboard, saved skill library, task creation/title editing, checkpoint timeline, notes, retake, checkpoint deletion, and full task deletion.
- Local JSON and JPEG storage; stable IDs, sequential positions, controlled image endpoints, atomic metadata writes and clear storage/camera errors.
- 16 automated tests pass. Production build and TypeScript check pass.
- Created a disposable task through Safari, captured three actual camera checkpoints, refreshed, and confirmed all three returned.
- Real API checks passed for image serving, title and note updates, retake replacement, checkpoint deletion and renumbering, and subsequent capture.
- Restarted FastAPI; all three images and saved notes remained available. Safari showed the restored timeline and notes.
- Edited and saved an instructor note through Safari; confirmed the saved value through the API.
- Removed only the disposable test task and its images after validation.
- No blockers for Milestone 2. Next: Milestone 3, real Gemini tutorial generation with configured credentials and an accessible model. Generate and Learn controls clearly indicate their future milestones.

### Milestone 3 — verified October 17, 2026

- Official `google-genai` SDK sends ordered inline JPEGs, title and notes with native JSON structured output. A portable schema is derived from Pydantic; strict local validation enforces exact step counts, reference mapping, lengths, ranges and extra-field rejection.
- Added model access checks, sanitized errors, bounded timeouts and one controlled invalid-output retry. High-demand 503 errors are now explicit, with no automatic API retries.
- Tutorials save atomically with model and generation timestamp. Duplicate requests are rejected; concurrent source edits prevent stale saves; later source edits invalidate the tutorial.
- Generate/Regenerate controls include image disclosure, unsaved-edit protection, loading/errors, tutorial cards and saved-library status.
- Isolated the four-image plain request: Gemini 3.8 Flash returned Google's explicit high-demand 503 after 35.5 seconds. This request had no tutorial prompt or JSON schema.
- User authorized another available Gemini Flash model. Gemini 3.6 Flash metadata access succeeded, the identical plain-image request succeeded in 14.2 seconds, and a minimal JSON request succeeded in 6.8 seconds.
- Simplified production requests to the SDK's public `response_mime_type` and `response_json_schema` fields, removing the custom response-format workaround.
- Configured Gemini 3.6 Flash explicitly in backend/.env and environment examples. The key was preserved and no silent fallback was added.
- The actual application generation endpoint returned HTTP 200 in 18.3 seconds, generated four real Wallet Phone steps and saved them. Checked instructions and criteria against all four references.
- Safari displayed all four generated cards and reference links after refresh. Restarted FastAPI, fetched the task and all JPEGs, and confirmed the generated tutorial exactly matched the pre-restart version.
- All four original checkpoints and the real generated tutorial remain saved. No fake AI responses were used outside automated tests.
- 57 automated tests pass, including native SDK request serialization, failure paths, strict output validation, tutorial persistence, invalidation, and stale/duplicate request handling. Existing frontend production build and TypeScript checks pass; no frontend source changed in this repair.
- Added a read-only diagnostic command: `python -m app.diagnose_gemini TASK_ID --stage plain|json [--model MODEL_ID]`. It reports request timings and token usage without printing credentials, image bytes or AI text.
- No blockers for Milestone 3. Next: Milestone 4, guided Learn Mode with current step, reference image, progress and reset. PASS/FAIL/UNCERTAIN verification remains Milestone 5.

### Milestone 4 — verified October 17, 2026

- Added a tutorial library and Start learning links from the dashboard and generated tutorial. Drafts direct learners to generate a tutorial first.
- Learn Mode displays the live camera, generated instruction, matching instructor reference, criteria, safety notes and ordered timeline in a responsive three-section workspace.
- Previous/next reference navigation and timeline selection clearly distinguish previews from the active step. Verified progress remains zero until real verification is implemented; no manual or time-based completion exists.
- Per-task browser sessions preserve browsing position across refresh, reject corrupt or obsolete state, and reset when the tutorial is regenerated. Reset returns to the first reference without changing saved instructor data.
- Safari checks with the real four-step Wallet Phone tutorial confirmed navigation, refresh persistence, reset, first/last navigation boundaries and disabled verification.
- User specified camera 0 because camera 1 is disabled. Confirmed camera 0's actual 1280 × 720 stream both directly and embedded in Learn Mode. Fixed Safari's empty preview by using intrinsic image sizing; added explicit JPEG lengths to multipart stream frames.
- Eight frontend session tests, 58 backend tests, TypeScript checks and the production build pass. One existing Starlette test-client deprecation warning remains.
- Learn Mode makes no Gemini requests and captures no learner stills. Verification is explicitly unavailable until Milestone 5.
- Updated README with Learn Mode behavior and a manual checklist. No blockers for Milestone 4. Next: real PASS/FAIL/UNCERTAIN comparison and advancement only on PASS.

### Milestone 5 — verified October 17, 2026

- Added real Gemini comparison of one saved instructor reference and one intentionally captured learner frame, with native structured output and strict PASS/FAIL/UNCERTAIN and qualitative-confidence validation. One malformed-output retry; no automatic network retries or invented assessment on API failure. Low-confidence PASS is conservatively downgraded to UNCERTAIN.
- Backend sessions enforce ordered verification and advance exactly once only on PASS. FAIL/UNCERTAIN retain the step and feedback. Missing/invalid inputs, skipped steps, duplicate requests, expired sessions, and task/session changes during requests are rejected without progress.
- Learn Mode includes image disclosure, loading/errors, color-coded feedback, expected/observed/correction text, model/time/step labels and the exact two images submitted. PASS advances the instruction and timeline; final PASS produces completion. Previewing steps cannot establish progress.
- Refresh resumes server progress and feedback using an opaque ID; in-flight sessions poll until finished. Reset clears progress and feedback without editing instructor data. Sessions are local process memory, expire after 30 minutes idle, and are bounded to 32 entries. Backend restart/eviction/expiry explicitly starts at zero. Only the latest learner/reference pair remains in memory; no learner images are written to disk.
- Real Gemini 3.6 Flash controlled-image checks using the saved controller photos: assembled versus identical assembled reference returned PASS in 3.36 seconds; missing front trim returned FAIL in 4.42 seconds with a specific correction; top-only view returned UNCERTAIN in 5.44 seconds because the front controls were obscured. These diagnostic comparisons did not alter session progress.
- User positioned the assembled controller for camera 0. Safari's actual Verify step captured the live camera and returned PASS, advanced step 1 to step 2, and displayed 1/4 verified with the exact image pair. Refresh restored progress and the real last assessment. Step 4 preview kept step 2 active and disabled Verify. The user's live session was left at step 2.
- 84 backend tests and 8 frontend session tests pass, alongside TypeScript checks and production build. Tests cover complete progression/reset/resume, all three outcomes, low confidence, invalid output/retry, missing camera/reference/key, timeout/quota/503 sanitization, duplicate/in-flight reset/task changes, expiry, and client status/step injection. Existing Starlette test-client deprecation warning remains.
- README documents routes, privacy, temporary session storage, error recovery and the manual verification checklist. No blockers for Milestone 5. Next: Milestone 6 visual polish; two complete consecutive physical runs and backup recording remain Milestone 7.

### Handoff follow-up — October 17, 2026

- Added HANDOFF.md for Copilot with architecture, configuration (no secrets), startup/check commands, verification evidence and remaining milestones.
- The backend had stopped during the interrupted turn; restarted it. In-memory learning progress reset as designed. Saved controller references and tutorial remain intact.

### Milestone 6 — verified October 17, 2026

- Refined the learner workspace with compact heading/navigation, a prominent Verify action before the reference, larger instruction/criteria text, clearer session details and a sticky wide-screen timeline. Narrow layouts wrap navigation, stack panels and preserve usable controls.
- Feedback now spans the workspace and distinguishes PASS/FAIL/UNCERTAIN using icons, text and color. Expected and observed evidence are separated; the suggested next action is highlighted. Step/model/time/confidence and visual-only limitations remain explicit.
- Added Inspect images: a native modal with the exact A/B evidence, larger side-by-side images on wide screens, stacked images on narrow screens, a named Close control, focus handling and native Escape dismissal.
- Added restrained live-camera sweep, active-step pulse, verified checkmarks and feedback entrance. These animations do not imply continuous inference. Reduced-motion styles suppress animations/transitions. Preserved Safari's intrinsic camera-image sizing and the existing backend protocol.
- Distinguished session opening, verification and reset loading labels; offline, missing disclosure and preview-disabled states explain the next action. Added semantic current-page navigation and visible keyboard focus.
- Safari reviewed the saved controller tutorial at laptop and 390-pixel narrow viewports. A fresh real camera/Gemini verification returned UNCERTAIN because the controller was absent, showed the specific feedback and exact image pair, and kept step 1 active at 0/4. Enlarged comparison displayed both real images; Escape dismissal was verified at laptop size and the named Close control at narrow size. No fake assessments were introduced.
- 84 backend tests and 8 frontend tests pass. TypeScript and production build pass. No backend behavior or dependencies changed. Existing Starlette test-client deprecation warning remains.
- Updated README and Copilot handoff. No blockers for Milestone 6. Next: Milestone 7, two complete physical runs, restart/reconnect/error checks and a backup demo recording; those reliability checks are still outstanding.

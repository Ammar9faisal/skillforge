# Native WhatsApp camera milestones

- [x] 1. Compile Swift CLI and enumerate actual WhatsApp windows.
- [x] 2. Capture and inspect real incoming video; configure its crop.
- [ ] 3. Deliberate overlap test — **SKIPPED at the user’s explicit request**. Not claimed as validated.
- [x] 4. Forward cropped JPEGs to FastAPI at configurable rate, default 2 FPS.
- [x] 5. Integrate common camera source, selector, preview, Teach and Verify; test USB regression.

## Validation — October 18, 2026

- Swift 6.4 / macOS 27.0.1, targeting macOS 14+. Stable locally built and ad-hoc signed binary; no paid membership or iOS application.
- Screen Recording denial was explicit; after the user enabled permission, enumeration succeeded. Initial AppKit initialization issue was fixed without bringing WhatsApp to the foreground.
- Inspected real incoming portrait video from the call window, distinct from main chat. Normalized top-left crop `0.273,0.055,0.454,0.852` excludes sidebars, controls and self-preview for the tested layout. Window IDs change when calls reopen.
- Initial real forwarding accepted at least 190 cropped frames at about 2 FPS. A subsequent ScreenCaptureKit capture failure stopped the helper and invalidated its feed.
- Integrated live test: selected WhatsApp source, fetched valid 728 × 1095 JPEG from the common preview endpoint, captured one real Teach checkpoint in a disposable task, then deleted only that test task. Bridge status showed fresh frames, initially 38 accepted and 0.5-second age.
- Switched to real USB camera 0: available at 1280 × 720, JPEG endpoint HTTP 200. Switched back to WhatsApp successfully with 83 accepted frames and 0.1-second age.
- Automated Verify tests check actual selected-source JPEG content and rejection of results when the source changes during a request. No extra live Gemini requests were made for this camera integration.
- 110 backend tests, 8 frontend tests, TypeScript check and production build pass. 36 Swift option/crop/destination checks pass. Existing Starlette test-client deprecation warning remains.
- No WhatsApp UI automation used for forwarding/integration. Deliberate overlap behavior remains untested by user choice. Frozen remote video cannot be detected from successful window captures alone.

- A later run accepted 123 frames before another ScreenCaptureKit failure. The selected call window still existed but was reported off-screen. Restarting only the helper against that same window succeeded and resumed uploads; no WhatsApp UI control was used. Treat capture errors as recoverable with an explicit helper restart, not as proof of uninterrupted background reliability.

- Replaced repeated screenshot capture in continuous mode with a persistent SCStream, bounded queue depth and only the latest complete pixel buffer. Snapshot mode stays separate for crop inspection. Inspected the resulting real incoming-video crop through the common frame endpoint.

- Persistent SCStream stability test accepted 250 real frames at 2 FPS over more than two minutes with fresh timestamps. Explicit SIGTERM exited cleanly, invalidated the lease/frame, and made the common frame endpoint return HTTP 503. Restarted the helper successfully afterward. This is a bounded live test, not a long-duration reliability claim.

## Frame 409 follow-up

The user reported a generic HTTP 409 during frame upload. Runtime bridge status showed 268 accepted sequence positions before shutdown; the previous error message did not retain the specific rejection reason, so the original cause cannot be confirmed. Code inspection identified a race between the helper’s three-second age allowance and the backend’s three-second arrival deadline. The helper now selects frames under 1.5 seconds old, waits briefly for fresh callbacks, discards/replaces timestamp-rejected frames without changing their timestamps, and bounds consecutive rejected uploads to five. Sequence/lease/size errors report specific allowlisted messages and remain fatal. No backend freshness limit was relaxed.

40 native checks and compilation pass; 22 targeted backend camera tests pass. Live revalidation could not run because native enumeration found no WhatsApp windows. Reopen the call and restart the helper to complete that check. No WhatsApp UI control used.

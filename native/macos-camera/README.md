# Native WhatsApp window camera for SkillForge

This local macOS CLI uses documented Apple ScreenCaptureKit APIs. It does not access WhatsApp internals, require an iOS app, or require a paid Apple Developer membership. macOS 14+ and Xcode Command Line Tools (or Xcode) are required. The current Mac has Swift 6.4 and macOS 27.0.1.

Compilation, real incoming-video capture/crop, live 2 FPS forwarding, preview, Teach capture and USB switching are verified. Verify source routing has automated coverage. The deliberate overlap test was skipped at your request; see [PLAN.md](PLAN.md).

## Run from the VS Code integrated terminal

If Swift is unavailable, install Apple’s free Command Line Tools with `xcode-select --install`, then reopen the terminal.

From the SkillForge repository root:

```sh
./native/macos-camera/run.sh build
./native/macos-camera/run.sh permission --request
./native/macos-camera/run.sh list
```

`run.sh` compiles only when a source file changes, keeps the binary at a stable path under `.build/`, and signs it ad hoc. No certificate, Apple account, package dependency or Xcode project is needed. Do not run the helper as root.

macOS requires Screen Recording permission. In **System Settings → Privacy & Security → Screen & System Audio Recording** (or **Screen Recording** on older macOS), enable the helper or launching application identified by macOS. This may be VS Code, Terminal, or the app hosting the coding agent. If macOS requests a restart, reopen that app and run the command again. Rebuilding an ad-hoc binary can require renewed permission. The CLI reports missing permission and exits; it never returns a fabricated frame.

## Select the call window explicitly

Keep the WhatsApp call connected and its incoming video rendering. `list` prints WhatsApp window IDs, titles, dimensions and visibility. It includes covered/off-screen windows, rather than only foreground windows. Use `list --all` only when you need to diagnose ownership of other windows; it prints metadata, not screenshots.

When there is more than one WhatsApp window, use its listed ID:

```sh
./native/macos-camera/run.sh snapshot --window-id 12345 --output /tmp/rayban-window.jpg
```

Replace `12345` with the actual call-window ID. Alternatively use `snapshot --select --output /tmp/rayban-window.jpg` to choose by number in the terminal. The helper refuses to guess between multiple windows and never silently switches to a different window if the chosen one closes. Window IDs can change when the call or app is reopened.

A chat window is not a camera feed. Inspect the snapshot and confirm the incoming Ray-Ban video is present before forwarding anything.

## Crop to the incoming video

Crop coordinates are normalized fractions of the captured window, measured **from its top-left corner**: `x,y,width,height`. These are not desktop coordinates, so moving/covering the window does not change the crop. Example:

```sh
./native/macos-camera/run.sh snapshot --window-id 12345 \
  --crop 0.05,0.10,0.90,0.80 --output /tmp/rayban-crop.jpg
```

For the tested 800 × 642 call layout, the incoming portrait video crop was `0.273,0.055,0.454,0.852`. This is layout-specific, not an automatically detected WhatsApp video region. Inspect and adjust it to exclude chat, caller names, call controls, self-preview and letterboxing. The default `0,0,1,1` includes the whole window and should be used only for initial framing. Crop is applied before JPEG resizing. Defaults: max output width 1280 pixels, quality 0.85. Override with `--max-width` and `--quality`. Window layout changes, call controls or aspect-ratio changes can require a new crop.

The helper uses `SCContentFilter(desktopIndependentWindow:)`, not a desktop screenshot. Other windows overlapping WhatsApp should therefore be excluded from captured pixels. The deliberate overlap test was skipped at the user’s request, so this behavior has not been confirmed by that test in this environment. Do not assume minimized, hidden, protected, locked-screen or disconnected video will keep updating: the source application may stop rendering. No audio is captured.

## Forward to SkillForge

Start the existing FastAPI backend from `backend/` and the frontend from `frontend/` as described in the repository README. Use one backend worker, bound to loopback. In a third VS Code terminal, from the repository root:

```sh
./native/macos-camera/run.sh stream --select \
  --crop 0.273,0.055,0.454,0.852 --fps 2 \
  --backend http://127.0.0.1:8000
```

Choose the **video-call window**, not the main chat window. Keep its size fixed after checking the crop. The helper prints the accepted frame count about every five seconds. Leave this terminal running. Ctrl+C stops forwarding and invalidates the backend frame.

In SkillForge Teach or Learn, select **WhatsApp Ray-Bans** under **Source**. Preview, new/retaken Teach checkpoints and Verify now use that source. Choose **USB Webcam** to restore camera 0; existing device-index/reconnect controls remain available. Selection is shared across tabs and lasts until backend restart. Optional `CAMERA_SOURCE=whatsapp` in `backend/.env` changes the startup source; the default remains `webcam`.

To inspect exactly what SkillForge receives, open [the current frame](http://127.0.0.1:8000/api/camera/frame) while WhatsApp Ray-Bans is selected. Refresh for a new JPEG. [Camera status](http://127.0.0.1:8000/api/camera/status) reports the selected source and freshness; [bridge status](http://127.0.0.1:8000/api/camera/whatsapp/status) reports accepted frame count, crop, window ID and frame age. None includes the upload token.

Continuous forwarding uses one persistent `SCStream`, holding only the latest complete pixel buffer; it does not start a new screenshot capture per uploaded frame. Snapshot mode uses `SCScreenshotManager`. The helper sends cropped JPEGs directly to loopback using a short-lived runtime upload token. Remote destinations and HTTP redirects are rejected. The backend accepts native ingress only from loopback without a browser Origin, bounds each JPEG to 4 MB / 8 megapixels / 4096 pixels per dimension, rejects stale timestamps and out-of-order frames, and keeps only the latest decoded frame in memory. At 2 FPS, frames expire after three seconds without a fresh capture (slower configured rates allow three frame intervals, minimum three seconds). Preview does not call Gemini or save continuous video. Intentional Teach checkpoints persist as before; Verify sends the selected learner frame to the configured Gemini service as before.

## Recovery and limitations

- Missing permission: follow the Screen Recording setup above. No fake or fallback frame is returned.
- Reopened/closed call: run `list`, inspect a fresh snapshot and select the new window ID. The helper never switches to the chat window automatically.
- Resized call: forwarding stops; inspect and adjust the crop, then restart. Moving the window does not require a crop change.
- Capture failure: the helper reports the error, attempts to invalidate the lease, and exits. If the backend is unreachable or the helper crashes, backend freshness expiry still prevents reuse of stale frames.
- Delayed frame (HTTP 409 stale timestamp): the helper discards it and continues with a fresh capture, without changing the original timestamp. Five consecutive delayed uploads stop with a specific error; reduce `--max-width` to `960` if the Mac/backend is busy. A call that stops providing fresh frames still becomes unavailable.
- Backend restart or other rejected upload: restart the helper. An active helper lease prevents a second helper from replacing a fresh feed; after an unexpected exit, wait for the lease to expire before restarting (up to ten seconds before the first frame).
- A selected Ray-Ban source never silently falls back to USB. Select USB explicitly if needed. Switching sources or restarting the helper during a Verify request discards its result without advancing progress.
- Capturing a fresh window image cannot prove that the remote video itself is live. WhatsApp may render a frozen frame, call controls, reconnect screen or changed layout. Check preview before capturing or verifying. Hidden/minimized/locked-screen behavior is not guaranteed.

## Tests

```sh
./native/macos-camera/test.sh
```

These tests check option validation, crop coordinates/bounds, window ID handling and bounded rate/quality settings and loopback destination validation without screen access or network. Backend regression tests cover JPEG ingress, freshness, leases, source switching and Verify source routing. Hardware/window capture gates are recorded separately in PLAN.md.

Apple references: [single-window filter](https://developer.apple.com/documentation/screencapturekit/sccontentfilter/init(desktopindependentwindow:)), [single-frame capture](https://developer.apple.com/documentation/screencapturekit/scscreenshotmanager), [occluded-window behavior](https://developer.apple.com/videos/play/wwdc2022/10155/).

# SkillForge — Devpost draft

Draft only; nothing has been published. The sections below are ready to adapt to the submission form. Team and public links need to be supplied before submission.

**Project name:** SkillForge

**Tagline:** Show it once. Learn it anywhere.

**Short description:** Turn hands-on demonstrations into AI tutorials and compare learners’ visible work with instructor references.

## Inspiration

Practical knowledge is often easiest to demonstrate and hardest to explain in writing. A learner watching a tutorial still has to judge whether their own attempt matches. We wanted to make an instructor’s demonstration reusable while giving learners feedback grounded in what a camera can actually see.

## What it does

In Teach Mode, an instructor captures completed physical steps and adds optional notes. Gemini compares the ordered images and produces a tutorial with instructions, references, visual criteria and safety notes for review.

In Learn Mode, a learner sees the instruction, reference and live camera. Clicking Verify captures a still and asks Gemini to compare it with the instructor’s reference. Feedback explains the expected and observed states and suggests a next action. PASS advances one step. FAIL and UNCERTAIN preserve the active step; low-confidence PASS is treated as UNCERTAIN.

The saved demonstration uses four PS5 controller checkpoints. The prototype also supports camera selection, retakes, persistent tutorials and an enlarged view of the exact comparison images. Webcam capture and a tested GoPro provide camera input. An optional macOS helper receives the Ray-Ban view indirectly by capturing a cropped WhatsApp video-call window.

## How we built it

The frontend uses Next.js App Router, React, TypeScript, Tailwind CSS, Lucide and CSS animation. FastAPI serves task, session and camera APIs. OpenCV owns webcam capture and provides JPEG/MJPEG output. Demonstrations and tutorials persist in local JSON/JPEG storage.

The official Google GenAI Python SDK handles image requests. Tutorial output must match the ordered checkpoints and pass local Pydantic validation. Verification is controlled by server sessions; browser-supplied completion flags cannot advance progress. Duplicate requests and stale results are rejected.

The optional Swift helper uses documented ScreenCaptureKit APIs, a selected-window filter, configurable crop and a persistent capture stream. It forwards JPEGs to loopback at a configurable rate, initially 2 FPS. A shared camera abstraction lets Teach and Verify consume either selected source without changing their image workflow.

## Challenges we ran into

Model metadata access did not guarantee successful image inference: provider high-demand errors and structured-output compatibility required separate diagnosis. We kept failures explicit and validated real image requests rather than treating connection checks as proof of working generation.

Camera integration required more than opening a device. Device indexes can differ across tools. GoPro occasionally missed a read during otherwise successful capture, so we added bounded recovery while preserving stale-frame rejection. For the WhatsApp bridge, continuous capture moved from repeated screenshots to one persistent ScreenCaptureKit stream.

## Accomplishments we are proud of

- A working capture → generate → learn → verify path with real Gemini responses.
- Visible feedback for PASS, FAIL and UNCERTAIN, with advancement controlled by the backend.
- Exact instructor/learner image comparison so a user can inspect the evidence behind an assessment.
- Camera source integration without replacing the existing Teach/Verify workflow.
- Automated coverage for progression, invalid model output, session races, camera freshness and temporary camera read failures.

## What we learned

Reliable visual feedback needs explicit boundaries. A clear image can support a visible-state assessment, but it cannot establish hidden function or the technique used to reach that state. Keeping uncertainty and errors visible is part of the product, not just an exception path.

## What’s next

Finish two consecutive physical end-to-end rehearsals and a backup recording, test longer camera sessions, evaluate false positives/negatives on varied tasks and lighting, and study whether learners find the feedback useful. Durable learning progress and deployment/access controls would be later production work.

## Limitations and current validation

This is a local hackathon prototype. It requires network/model access for generation and verification. AI sees captured stills, not a continuous action history. Sessions are temporary backend memory; demonstrations and tutorials persist. The source application can freeze incoming remote video even if window capture succeeds. WhatsApp layout changes can invalidate the chosen crop.

Recorded-image Gemini diagnostics produced PASS, FAIL and UNCERTAIN; individual live-camera assessments have also been tested. Automated tests cover full progress handling. Two full consecutive physical runs remain milestone 7 work. Ray-Ban forwarding passed a 250-frame, 2 FPS bounded test; GoPro passed a 30-second app-level check after recovery fixes. The deliberate WhatsApp overlap test was skipped. No accuracy percentage or improvement in learning outcomes has been established.

## Built with

Python, FastAPI, Uvicorn, OpenCV, Pydantic, Google Gemini API, google-genai, Next.js, React, TypeScript, Tailwind CSS, Lucide, Swift, ScreenCaptureKit, local JSON/JPEG storage.

## Submission fields still to fill

| Field | Value |
| --- | --- |
| Team members and roles | TO ADD |
| Public repository URL | TO ADD — verify it excludes credentials and private demonstration data |
| Demo video URL | TO ADD — record and review a real demonstration first |
| Hosted app URL | No public deployment; runs locally using SETUP.md |
| Requested tracks | Project brief: AI for Social Impact; FDM healthier-working-life framing; Gemini API use. Confirm the actual event’s available options before selecting. |

Do not use a localhost address as a public app link or claim a video, public deployment, award or submission exists before it does.

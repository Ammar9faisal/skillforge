# SkillForge — pitch and judge Q&A

**Show it once. Learn it anywhere.**

## One sentence

SkillForge turns captured checkpoints of a hands-on demonstration into a reusable AI tutorial, then compares a learner’s visible work with the instructor’s references.

## 30-second pitch

Learning a practical skill alone means repeatedly asking, “Does mine look right?” SkillForge gives that question a visual reference. An instructor captures completed steps, Gemini builds a structured tutorial, and a learner practices with a live camera. Each requested assessment explains the expected state, what was observed, and what to change. Only PASS advances; uncertainty stays visible. We want to help students and trainees practice when one-to-one instruction is unavailable.

## Why it matters

- **Social impact:** Reusable demonstrations could extend an instructor’s reach for students, vocational learners and community workshops. This is a proposed benefit; learning outcomes have not been measured.
- **Healthier working life:** Workers could revisit visible task sequences and receive structured feedback during training. SkillForge has not demonstrated injury reduction, ergonomic improvement or suitability for safety-critical work.
- **Gemini contribution:** The official Google GenAI SDK sends ordered checkpoint images for tutorial generation and an instructor/learner image pair for verification. Structured output is validated before saving a tutorial or changing progress.

These framings follow the project brief. They are not claims of prize eligibility, a partnership, or demonstrated real-world impact.

## What is built

Next.js/React presents Teach, Learn, live preview and image comparison. FastAPI owns the camera and task/session APIs. OpenCV provides webcam capture. Local JSON/JPEG files persist demonstrations and generated tutorials. Gemini provides image-based instructions and assessments. USB webcams and the tested GoPro use the same camera path. A native macOS ScreenCaptureKit helper can forward a cropped incoming WhatsApp Ray-Ban call view; this is a video-window bridge, not a direct Meta device integration.

Preview is live; AI assessment is an intentional still-image request. The application does not continuously infer actions from video.

## Judge Q&A

| Question | Answer |
| --- | --- |
| Why not just watch a video? | SkillForge adds a saved visual target, step-specific criteria and feedback on the learner’s actual attempt. We have not measured superiority to video instruction. |
| What prevents false completion? | The backend validates model output and advances only on PASS. FAIL/UNCERTAIN stay on the current step, low-confidence PASS becomes UNCERTAIN, and stale results after task/session/source changes are rejected. The model can still make mistakes. |
| What can it verify? | Visible arrangements supported by the supplied image and criteria. It cannot establish hidden electrical/mechanical correctness, safety, or whether a finished state was reached using the right technique. |
| What happens when the model is unavailable? | The app shows an error and preserves progress. There is no invented result or silent model fallback. Saved tutorials remain available. |
| Is it instant? | No. Generation and verification depend on the configured model, network and demand. Historical measurements are in PLAN.md; they are not latency guarantees. |
| What goes to Google? | Generation sends saved checkpoints, notes and the title. Verification sends the matching reference and an intentionally captured learner still with step context. Local preview does not invoke Gemini. |
| What stays local? | Task JSON, reference JPEGs and tutorials are stored on this Mac. Learning sessions and the latest comparison pair are in backend memory. Local storage does not mean images requested for AI processing stay on-device. |
| Does progress survive restart? | Saved demonstrations/tutorials do. Learning progress does not: sessions expire after 30 minutes idle, eviction, or backend restart. Browser refresh can resume a still-valid server session. |
| Are Ray-Bans natively supported? | The working path captures the incoming WhatsApp call window through documented Apple APIs. It is not an iOS app or direct wearable SDK connection. Window/layout changes require attention; the deliberate overlap test was skipped. |
| How reliable is the GoPro path? | HERO9 Black at index 1 passed a 30-second app-level test at 1920 × 1080 after brief missed-read recovery was fixed. That is a bounded test, not a long-duration guarantee. |
| How much does it cost? | Inference depends on the configured Gemini model, image sizes and request count. Preview/browsing make no inference requests. No fixed cost per tutorial or hackathon total has been established here. |
| What is missing for production? | User validation, extended camera reliability, durable learning sessions, deployment/access controls and evaluation of false positives/negatives. This is a localhost hackathon prototype. |

## Closing line

“An instructor’s demonstration becomes a reference a learner can practice against. Show it once. Learn it anywhere.”

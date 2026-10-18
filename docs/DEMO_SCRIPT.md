# SkillForge — 90-second demo

Tagline: **Show it once. Learn it anywhere.**

Use the saved PS5 Controller Disassembly tutorial. The timed demo shows previously captured checkpoints and a previously generated tutorial, followed by live verification. Say this explicitly. Live generation and two complete physical runs belong in the longer rehearsal; neither is guaranteed to fit this timer.

## Before the timer

1. Follow [SETUP.md](SETUP.md). Confirm the actual camera image, not just an ACTIVE indicator. On the tested configuration, GoPro HERO9 Black is USB Webcam index 1; built-in camera is 0. Device ordering can change.
2. Open the saved tutorial in Teach and Learn in separate tabs. Do not edit its title, notes or checkpoints: edits invalidate the tutorial. Hide terminals containing credentials.
3. Prepare the controller in two observable states for the first step: assembled, and visibly missing its lower front trim. Check the saved first-step criteria before using this example. Keep framing and lighting similar to the reference.
4. Reset the learning session before the presentation, then acknowledge the image disclosure. Reset does not delete the tutorial. Backend restart also resets learning progress.
5. Rehearse an actual mismatch and correction with the selected camera. Responses vary; show the actual result. This script does not establish that rehearsal has happened.
6. Keep an honestly labeled recording ready once milestone 7 produces one. No backup recording is included with this documentation.

## Spoken script and operator cues

| Time | Say | Show / do |
| --- | --- | --- |
| 0–12 s | “A video can show you a practical skill, but it cannot look at your attempt. SkillForge turns an instructor’s demonstration into a visual guide that can assess what a learner does.” | Dashboard, then the saved skill. |
| 12–27 s | “Here are four checkpoints we captured earlier. Gemini compared these completed states and generated instructions, reference images, and visual checks. This tutorial was prepared before the timed demo.” | Teach: checkpoint timeline and real generated tutorial. |
| 27–40 s | “In Learn Mode, the learner sees the instruction, the instructor’s reference, and their own live camera. Verification happens when they request it.” | Learn: active step, live feed, reference. |
| 40–60 s | “I’ve deliberately changed the visible state. Let’s compare it with the reference.” Then describe the result actually returned. | Present the mismatch, click **Verify step**, show expected / observed / feedback. |
| 60–80 s | “Now I’ll correct the arrangement and verify again. Only PASS advances; FAIL or UNCERTAIN keeps the step active.” | Correct the state, verify. On PASS show progress; otherwise show the actual feedback without advancing manually. |
| 80–90 s | “The goal is to make hands-on instruction reusable when an instructor cannot be beside every learner. SkillForge checks visible evidence, not hidden function. Show it once. Learn it anywhere.” | Show **Inspect images** if time permits; finish on the learning workspace. |

About 140 scripted words, plus your description of the actual result; pauses and API latency determine the final duration. Stop narration while the audience reads useful feedback.

## Branches that keep the demonstration honest

- **UNCERTAIN:** “The camera does not provide enough evidence, so progress stays here.” Adjust the view and retry only if time allows.
- **Unexpected PASS or FAIL:** Inspect the submitted images and state what the assessment actually says. Do not claim the intended mistake was detected unless the response supports it.
- **One assessment still pending at 60 seconds:** Show the captured/reference comparison already available, explain that the request is pending, and deliver the closing line. Do not promise a second result before the timer ends.
- **API unavailable:** Show the error and saved tutorial. If a backup recording exists, introduce it as a recording of an earlier real run. Do not present a recording as live inference.
- **Camera offline:** Reconnect the same source or explicitly choose another. Do not substitute a saved image for a live capture.

## Longer technical walkthrough

For the full teach-to-learn workflow, create a separate demonstration with three to five visibly different completed states, save notes, acknowledge the generation disclosure, and generate a real tutorial. Review it, then learn with correct, incorrect and ambiguous views. Keep this outside the 90-second slot unless a rehearsal establishes the timing. Generation latency and verification latency vary.

## Backup recording shot list — not yet recorded

Record the application and physical workspace with consent. Capture Teach checkpoints, a real generation request and result, Learn instructions, mismatch feedback, corrected feedback/progression, and the exact image comparison. Label any cuts and speed changes; do not hide a failed request or imply shortened waits were real-time. Keep credentials and unrelated conversations out of frame. Save the video locally, play it back with audio, and add its real location/link to the submission draft. Recording and two complete physical runs remain milestone 7 work.

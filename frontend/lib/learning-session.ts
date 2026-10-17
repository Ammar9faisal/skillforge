import type { Task } from './api';

export type LearningSession = { tutorialVersion: string; previewStepId: number };
export type ReadyTask = Task & { tutorial: NonNullable<Task['tutorial']> };

export function sessionKey(task: ReadyTask) {
  return `skillforge:learn:${task.id}`;
}
export function newSession(task: ReadyTask): LearningSession {
  return { tutorialVersion: task.tutorial.generated_at, previewStepId: task.tutorial.steps[0].step_id };
}
export function restoreSession(task: ReadyTask, raw: string | null): LearningSession {
  const initial = newSession(task);
  if (!raw) return initial;
  try {
    const saved = JSON.parse(raw);
    if (saved?.tutorialVersion !== initial.tutorialVersion || !task.tutorial.steps.some(step => step.step_id === saved.previewStepId)) return initial;
    // Only browsing position is restored. Client data never establishes a PASS.
    return { tutorialVersion: initial.tutorialVersion, previewStepId: saved.previewStepId };
  } catch { return initial; }
}
export function previewStep(task: ReadyTask, session: LearningSession, stepId: number): LearningSession {
  if (!task.tutorial.steps.some(step => step.step_id === stepId)) return session;
  return { tutorialVersion: task.tutorial.generated_at, previewStepId: stepId };
}
export function learningProgress(task: ReadyTask) {
  // Verified progression arrives with the verification endpoint in Milestone 5.
  return { activeStepId: task.tutorial.steps[0].step_id, verifiedCount: 0, total: task.tutorial.steps.length };
}

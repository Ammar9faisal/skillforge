import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';

// Transpile the pure TypeScript helper with the project's installed compiler.
// Type-only API imports disappear; no browser or extra test dependency is needed.
const source = readFileSync(new URL('../lib/learning-session.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } }).outputText;
const { newSession, restoreSession, previewStep, sessionKey, learningProgress } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
const task = { id: 'skill-a', tutorial: { generated_at: '2026-10-17T19:00:00Z', steps: [{ step_id: 1 }, { step_id: 2 }, { step_id: 3 }] } };

test('browsing future references never advances verified progress', () => {
  const browsed = previewStep(task, newSession(task), 3);
  assert.equal(browsed.previewStepId, 3);
  assert.deepEqual(learningProgress(task), { activeStepId: 1, verifiedCount: 0, total: 3 });
  assert.equal('completedStepIds' in browsed, false);
});
test('valid browsing position survives serialization and refresh', () => {
  const browsed = previewStep(task, newSession(task), 2);
  assert.deepEqual(restoreSession(task, JSON.stringify(browsed)), browsed);
});
test('reset returns to the first reference without changing the tutorial', () => {
  const before = JSON.stringify(task);
  const reset = newSession(task);
  assert.equal(reset.previewStepId, 1);
  assert.equal(JSON.stringify(task), before);
});
test('regenerated tutorials reset the saved position', () => {
  const saved = JSON.stringify(previewStep(task, newSession(task), 3));
  const regenerated = { ...task, tutorial: { ...task.tutorial, generated_at: '2026-10-17T20:00:00Z' } };
  assert.deepEqual(restoreSession(regenerated, saved), newSession(regenerated));
});
test('corrupt, invalid and unknown saved positions recover safely', () => {
  for (const raw of ['not json', 'null', '{}', JSON.stringify({ tutorialVersion: task.tutorial.generated_at, previewStepId: 99 }), JSON.stringify({ tutorialVersion: task.tutorial.generated_at, previewStepId: '2' })]) {
    assert.deepEqual(restoreSession(task, raw), newSession(task));
  }
});
test('client-supplied completion flags cannot establish a PASS', () => {
  const restored = restoreSession(task, JSON.stringify({ ...newSession(task), previewStepId: 2, completedStepIds: [1, 2, 3], status: 'PASS' }));
  assert.deepEqual(restored, { tutorialVersion: task.tutorial.generated_at, previewStepId: 2 });
  assert.equal(learningProgress(task).verifiedCount, 0);
});
test('unknown steps cannot navigate out of the tutorial', () => {
  const current = previewStep(task, newSession(task), 2);
  assert.deepEqual(previewStep(task, current, 100), current);
});
test('different skills keep independent browser sessions', () => {
  assert.notEqual(sessionKey(task), sessionKey({ ...task, id: 'skill-b' }));
});

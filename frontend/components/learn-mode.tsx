'use client';
import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, BookOpen, Camera, Circle, CircleHelp, ExternalLink, ListOrdered, LoaderCircle, RotateCcw, ScanLine, ShieldCheck } from 'lucide-react';
import CameraPanel from './camera-panel';
import VerificationResultPanel from './verification-result';
import { imageUrl, request, ServerSession, Task } from '../lib/api';
import { learningProgress, newSession, previewStep, ReadyTask, restoreSession, sessionKey } from '../lib/learning-session';

export default function LearnMode({ tasks, task, taskId, loading, failed }: { tasks: Task[]; task: Task | null; taskId: string | null; loading: boolean; failed: boolean }) {
  if (loading) return <div className="empty-state panel" role="status"><LoaderCircle className="spin"/> Loading your learning workspace…</div>;
  if (taskId && !task) return <div className="empty-state panel"><BookOpen size={30}/><h2>This skill could not be opened.</h2><p>Refresh saved data or choose another tutorial.</p><a className="button" href="/?mode=learn">Choose a tutorial</a></div>;
  if (task && !task.tutorial) return <div className="empty-state panel"><BookOpen size={30}/><h2>This demonstration needs a tutorial.</h2><p>Open Teach Mode and generate instructions from its saved checkpoints first.</p><a className="button" href={`/?task=${task.id}`}>Open in Teach Mode <ArrowRight size={15}/></a><a href="/?mode=learn" className="text-link">Choose another skill</a></div>;
  if (task?.tutorial) {
    if (!task.tutorial.steps.length) return <div role="alert" className="empty-state panel"><h2>This tutorial has no steps.</h2><a className="button" href={`/?task=${task.id}`}>Regenerate in Teach Mode</a></div>;
    return <LearningWorkspace key={`${task.id}:${task.tutorial.generated_at}`} task={task as ReadyTask}/>;
  }
  if (failed) return <div className="empty-state panel"><h2>Your tutorial library is unavailable.</h2><p>Use Refresh saved data above to reconnect to the backend.</p></div>;
  const ready = tasks.filter(t => t.tutorial && t.tutorial.steps.length > 0);
  return <section><div className="section-heading"><div><div className="eyebrow">YOUR LEARNING LIBRARY</div><h2>Choose a skill to practice</h2></div><span className="library-count">{ready.length} tutorial{ready.length === 1 ? '' : 's'} ready</span></div>{ready.length ? <div className="task-grid">{ready.map(saved => <article className="task-card panel" key={saved.id}><a className="task-cover" href={`/?mode=learn&task=${saved.id}`}>{saved.checkpoints.length ? <img src={imageUrl(saved, saved.checkpoints[0])} alt={`Reference for ${saved.title}`}/> : <BookOpen size={30}/>}<span>TUTORIAL READY</span></a><div className="task-details"><h3><a href={`/?mode=learn&task=${saved.id}`}>{saved.title}</a></h3><p>{saved.tutorial!.steps.length} guided steps · Instructor references</p><a className="button primary start-learning" href={`/?mode=learn&task=${saved.id}`}>Start learning <ArrowRight size={15}/></a></div></article>)}</div> : <div className="empty-state panel"><BookOpen size={30}/><h3>Your next skill starts with a demonstration.</h3><p>Generate a tutorial in Teach Mode, then open it here to practice.</p><a className="button" href="/?mode=teach">Create a skill <ArrowRight size={15}/></a></div>}</section>;
}

function LearningWorkspace({ task }: { task: ReadyTask }) {
  const [session, setSession] = useState(() => newSession(task));
  const [restored, setRestored] = useState(false);
  const [storageError, setStorageError] = useState('');
  const [cameraReady, setCameraReady] = useState(false);
  const [referenceFailed, setReferenceFailed] = useState(false);
  const [announcement, setAnnouncement] = useState('');
  const [server, setServer] = useState<ServerSession | null>(null);
  const [verificationError, setVerificationError] = useState('');
  const [sessionNotice, setSessionNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [consent, setConsent] = useState(false);
  const progress = server ? { activeStepId: server.active_step_id, verifiedCount: server.completed_step_ids.length, total: server.total } : learningProgress(task);
  const complete = server?.complete ?? false;
  const serverKey = `skillforge:verification:${task.id}`;
  useEffect(() => {
    let active = true;
    setServer(null);
    let id: string | null = null;
    try { id = window.localStorage.getItem(serverKey); } catch { /* Server session still works in this window. */ }
    if (id && !/^[0-9a-f]{32}$/.test(id)) id = null;
    request<ServerSession>(`/api/tasks/${task.id}/sessions`, { method: 'POST', body: JSON.stringify({ session_id: id, tutorial_version: task.tutorial.generated_at }) })
      .then(data => {
        if (!active) return;
        setServer(data);
        setSessionNotice(id && !data.resumed ? 'Your previous server session expired or the backend restarted. Verified progress has been reset.' : 'Progress is held by the backend. Sessions expire after 30 minutes idle or a backend restart.');
        try { window.localStorage.setItem(serverKey, data.session_id); } catch { setStorageError('Session cannot be restored after refresh because browser storage is unavailable.'); }
      }).catch(e => { if (active) setVerificationError((e as Error).message); });
    return () => { active = false; };
  }, [task, serverKey]);
  useEffect(() => {
    if (!server?.busy || busy) return;
    let active = true;
    const timer = setTimeout(() => {
      request<ServerSession>(`/api/tasks/${task.id}/sessions`, { method: 'POST', body: JSON.stringify({ session_id: server.session_id, tutorial_version: task.tutorial.generated_at }) })
        .then(data => { if (active) setServer(data); })
        .catch(e => { if (active) setVerificationError((e as Error).message); });
    }, 2000);
    return () => { active = false; clearTimeout(timer); };
  }, [server, task, busy]);
  async function verify() {
    if (!server || lock.current || !consent || isPreview || complete || !cameraReady) return;
    lock.current = true; setBusy(true); setVerificationError('');
    try {
      const data = await request<ServerSession>(`/api/tasks/${task.id}/verify`, { method: 'POST', body: JSON.stringify({ session_id: server.session_id, step_id: step.step_id }) }, 260000);
      setServer(data);
      if (data.last_result?.status === 'PASS' && data.active_step_id !== null) setSession(old => previewStep(task, old, data.active_step_id!));
      setAnnouncement(data.complete ? 'All steps verified. Tutorial complete.' : `Step ${step.step_id}: ${data.last_result?.status}. ${data.last_result?.feedback}`);
    } catch (e) { setVerificationError(`${(e as Error).message} Refresh the page to reconcile backend progress before retrying an interrupted request.`); }
    finally { lock.current = false; setBusy(false); }
  }
  const steps = task.tutorial.steps;
  const currentIndex = Math.max(0, steps.findIndex(step => step.step_id === session.previewStepId));
  const step = steps[currentIndex];
  const reference = task.checkpoints.find(checkpoint => checkpoint.reference_image === step.reference_image);
  const isPreview = !complete && step.step_id !== progress.activeStepId;
  useEffect(() => {
    try { setSession(restoreSession(task, window.localStorage.getItem(sessionKey(task)))); }
    catch { setStorageError('Browser storage is unavailable. You can still browse, but your position will not survive a refresh.'); }
    setRestored(true);
  }, [task]);
  useEffect(() => {
    if (!restored) return;
    try { window.localStorage.setItem(sessionKey(task), JSON.stringify(session)); }
    catch { setStorageError('Your browsing position could not be saved. You can continue in this window.'); }
  }, [task, session, restored]);
  useEffect(() => setReferenceFailed(false), [step.reference_image]);
  function browse(stepId: number) {
    setSession(old => previewStep(task, old, stepId));
    setAnnouncement(`Viewing step ${stepId}. Verified completion has not changed.`);
  }
  async function reset() {
    if (!server || lock.current) return;
    lock.current = true; setBusy(true); setVerificationError('');
    try {
      const data = await request<ServerSession>(`/api/tasks/${task.id}/sessions/${server.session_id}/reset`, { method: 'POST' });
      setServer(data); setSession(newSession(task)); setAnnouncement('Session reset. Verified progress cleared.');
    } catch (e) { setVerificationError((e as Error).message); }
    finally { lock.current = false; setBusy(false); }
  }
  return <div className="learn-workspace"><div className="learn-toolbar"><div><a href="/?mode=learn" className="text-link"><ArrowLeft size={14}/> All tutorials</a><h2>{task.title}</h2><p>{steps.length} steps · Generated by {task.tutorial.model}</p></div><div className="learn-toolbar-actions"><a href={`/?task=${task.id}`} className="text-link">Edit demonstration</a><button disabled={!restored || !server || busy || server.busy} onClick={reset}><RotateCcw size={14}/> Reset session</button></div></div>{storageError && <div className="notice storage-notice" role="status"><CircleHelp size={15}/>{storageError}</div>}{sessionNotice && <p className="session-notice">{sessionNotice}</p>}{verificationError && <div role="alert" className="verification-error panel"><p>{verificationError}</p><button onClick={() => window.location.reload()}>Refresh learning session</button></div>}<div className="sr-only" role="status" aria-live="polite">{announcement}</div><div className="learn-grid"><div className="learn-camera-column"><CameraPanel onAvailability={setCameraReady}/><div className="practice-tip panel"><ShieldCheck size={20}/><div><strong>You control each capture.</strong><p>Match the instructor’s reference in the live view. Browsing stays local. Verify step captures one image and sends it with the instructor reference to Google’s Gemini API.</p></div></div><div className="practice-tip panel"><ScanLine size={20}/><div><strong>{cameraReady ? 'Keep a consistent perspective.' : 'Connect your camera to practice.'}</strong><p>{cameraReady ? 'Use a similar camera angle and lighting, with the whole arrangement visible.' : 'You can browse the tutorial while the camera is offline. Select a device and Reconnect for a live view.'}</p></div></div></div><section className="current-instruction panel" aria-label="Current task"><div className="instruction-top"><span className="eyebrow">{complete ? 'REVIEW' : isPreview ? 'PREVIEW' : 'CURRENT STEP'} · {String(currentIndex + 1).padStart(2, '0')} / {String(steps.length).padStart(2, '0')}</span><BookOpen size={17}/></div><div className="instruction-content"><h3>{step.title}</h3><p className="step-instruction">{step.instruction}</p>{isPreview && <div className="preview-notice">You’re previewing step {step.step_id}. Step {progress.activeStepId} remains active.<button className="text-button" onClick={() => progress.activeStepId !== null && browse(progress.activeStepId)}>Return to current step <ArrowLeft size={12}/></button></div>}<div className="reference-title"><span>INSTRUCTOR REFERENCE</span>{reference && <a href={imageUrl(task, reference)} target="_blank" rel="noreferrer" aria-label="Open instructor reference at full size"><ExternalLink size={13}/></a>}</div><div className="learner-reference">{reference && !referenceFailed ? <img src={imageUrl(task, reference)} alt={`Instructor reference for step ${step.step_id}: ${step.title}`} onError={() => setReferenceFailed(true)}/> : <div role="alert"><Camera size={25}/><p>Reference image unavailable. Retake this checkpoint in Teach Mode and regenerate the tutorial.</p><a className="text-link" href={`/?task=${task.id}`}>Open Teach Mode</a></div>}</div><div className="criteria-heading"><ScanLine size={14}/> What to look for</div><ul className="learn-criteria">{step.verification_criteria.map((criterion, index) => <li key={index}>{criterion}</li>)}</ul>{step.safety_notes.length > 0 && <div className="learn-safety"><strong>Safety & visibility notes</strong><ul>{step.safety_notes.map((note, index) => <li key={index}>{note}</li>)}</ul></div>}<div className="browse-controls"><button disabled={!restored || busy || currentIndex === 0} onClick={() => browse(steps[currentIndex - 1].step_id)}><ArrowLeft size={14}/> Previous reference</button><button disabled={!restored || busy || currentIndex === steps.length - 1} onClick={() => browse(steps[currentIndex + 1].step_id)}>Next reference <ArrowRight size={14}/></button></div></div><div className="verify-controls">{complete ? <div className="completion-banner" role="status"><strong>All {progress.total} steps verified</strong><p>Each step received a visible-evidence PASS. Reset the session to practice again.</p></div> : <><label className="verification-consent"><input type="checkbox" checked={consent} disabled={busy} onChange={e => setConsent(e.target.checked)}/><span>Allow Verify step to send one learner capture and its instructor reference to Google’s Gemini API.</span></label><button disabled={!restored || !server || busy || server.busy || !cameraReady || isPreview || !consent} onClick={verify}>{busy ? <LoaderCircle size={16} className="spin"/> : <ScanLine size={16}/>} {busy ? 'Assessing captured image…' : 'Verify step'}</button><p>{isPreview ? 'Return to the active step to verify. Previewing does not complete a step.' : 'Only PASS advances. FAIL and UNCERTAIN keep this step active.'}</p></>}{server?.last_result && <VerificationResultPanel result={server.last_result}/>}</div></section><section className="learn-timeline panel" aria-label="Skill timeline"><div className="timeline-top"><div className="eyebrow">SKILL TIMELINE</div><ListOrdered size={18}/></div><div className="verified-progress"><strong>{progress.verifiedCount}<span> / {progress.total}</span></strong><p>steps verified</p><div className="progress-track" role="progressbar" aria-label="Verified completion" aria-valuemin={0} aria-valuemax={progress.total} aria-valuenow={progress.verifiedCount}><div style={{ width: `${progress.verifiedCount / progress.total * 100}%` }}/></div><span className="awaiting-verification">{complete ? 'Tutorial complete' : busy ? 'Assessing captured image' : 'Awaiting verification'}</span></div><ol className="learning-nodes">{steps.map((item, index) => <li key={item.step_id}><button disabled={!restored || busy} className={`${item.step_id === step.step_id ? 'viewing' : ''} ${item.step_id === progress.activeStepId ? 'active-step' : ''}`} aria-current={item.step_id === step.step_id ? 'step' : undefined} onClick={() => browse(item.step_id)}><span className="learning-node">{String(index + 1).padStart(2, '0')}</span><span className="node-label"><strong>{item.title}</strong><span>{server?.completed_step_ids.includes(item.step_id) ? 'Verified · PASS' : item.step_id === progress.activeStepId ? 'Active · not verified' : item.step_id === step.step_id ? 'Previewing · not verified' : 'Upcoming'}</span></span><Circle size={11}/></button></li>)}</ol><div className="timeline-legend"><CircleHelp size={15}/><p>Select any step to inspect its reference. Previewing never marks a step complete.</p></div></section></div></div>;
}

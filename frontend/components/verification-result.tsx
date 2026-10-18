'use client';
import { useId, useRef } from 'react';
import { CheckCircle2, Expand, ShieldCheck, TriangleAlert, X, CircleHelp } from 'lucide-react';
import type { VerificationResult } from '../lib/api';

const outcomes = {
  PASS: { Icon: CheckCircle2, title: 'Visible state matched', action: 'Step verified', label: 'Feedback' },
  FAIL: { Icon: TriangleAlert, title: 'Mismatch detected', action: 'Correct and retry', label: 'Suggested correction' },
  UNCERTAIN: { Icon: CircleHelp, title: 'Better view needed', action: 'Adjust the view and retry', label: 'What to do next' },
};

export default function VerificationResultPanel({ result }: { result: VerificationResult }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const { Icon, title, action, label } = outcomes[result.status];
  function images() {
    return <div className="assessment-images">
      <figure><div className="evidence-label"><span>A</span> Instructor reference</div><img src={result.reference_data_url} alt={`Exact instructor image sent for step ${result.step_id}`}/><figcaption>Expected completed state</figcaption></figure>
      <figure><div className="evidence-label"><span>B</span> Learner capture</div><img src={result.learner_data_url} alt={`Exact captured learner image assessed for step ${result.step_id}`}/><figcaption>Still image assessed by Gemini</figcaption></figure>
    </div>;
  }
  return <section key={result.assessed_at} className={`assessment assessment-${result.status.toLowerCase()}`} aria-label="Latest verification result">
    <div className="assessment-heading" role="status">
      <span className="outcome-icon"><Icon size={24}/></span>
      <div><span className="eyebrow">STEP {String(result.step_id).padStart(2, '0')} ASSESSMENT</span><h3><span>{result.status}</span> {title}</h3><p>{action} · {result.confidence} confidence</p></div>
      <button className="evidence-expand" onClick={() => dialog.current?.showModal()}><Expand size={14}/> Inspect images</button>
    </div>
    <dl className="assessment-findings"><div><dt>Expected state</dt><dd>{result.expected}</dd></div><div><dt>Observed evidence</dt><dd>{result.observed}</dd></div><div className="assessment-action"><dt>{label}</dt><dd>{result.feedback}</dd></div></dl>
    {images()}
    <div className="assessment-footnote"><ShieldCheck size={14}/><p>These are the exact two images sent for this assessment. Hidden physical or electrical correctness is unverified.</p><span>{result.model} · {new Date(result.assessed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span></div>
    <dialog ref={dialog} className="evidence-dialog" aria-labelledby={titleId} onClick={event => { if (event.target === event.currentTarget) dialog.current?.close(); }}>
      <div className="evidence-dialog-content"><div className="evidence-dialog-heading"><div><span className="eyebrow">SUBMITTED EVIDENCE</span><h2 id={titleId}>Step {result.step_id} · {title}</h2></div><button autoFocus aria-label="Close image comparison" onClick={() => dialog.current?.close()}><X size={18}/> Close</button></div>{images()}<p className="assessment-meta">{new Date(result.assessed_at).toLocaleString()} · {result.model}. The learner image is a captured still, not the changing live feed.</p></div>
    </dialog>
  </section>;
}

'use client';
import type { VerificationResult } from '../lib/api';
export default function VerificationResultPanel({ result }: { result: VerificationResult }) {
  return <section className={`assessment assessment-${result.status.toLowerCase()}`} aria-label="Latest verification result" aria-live="polite">
    <div className="assessment-heading"><strong>{result.status === 'PASS' ? 'PASS · Visible state matched' : result.status === 'FAIL' ? 'FAIL · Mismatch detected' : 'UNCERTAIN · Better view needed'}</strong><span>Step {result.step_id} · {result.confidence} confidence</span></div>
    <dl><dt>Expected</dt><dd>{result.expected}</dd><dt>Observed</dt><dd>{result.observed}</dd><dt>{result.status === 'PASS' ? 'Feedback' : 'Next action'}</dt><dd>{result.feedback}</dd></dl>
    <div className="assessment-images"><figure><img src={result.reference_data_url} alt={`Exact instructor image sent for step ${result.step_id}`}/><figcaption>Instructor reference · sent to Gemini</figcaption></figure><figure><img src={result.learner_data_url} alt={`Exact captured learner image assessed for step ${result.step_id}`}/><figcaption>Learner capture · sent to Gemini</figcaption></figure></div>
    <p className="assessment-meta">{result.model} · {new Date(result.assessed_at).toLocaleString()} · Visual assessment; hidden physical or electrical correctness is unverified.</p>
  </section>;
}

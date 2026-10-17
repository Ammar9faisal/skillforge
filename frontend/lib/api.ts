export const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
export type Checkpoint = { id: string; position: number; note: string; reference_image: string; created_at: string };
export type TutorialStep = { step_id: number; title: string; instruction: string; reference_image: string; verification_criteria: string[]; safety_notes: string[] };
export type Tutorial = { steps: TutorialStep[]; model: string; generated_at: string };
export type Task = { id: string; title: string; created_at: string; updated_at: string; checkpoints: Checkpoint[]; tutorial: Tutorial | null };
export async function request<T>(path: string, options: RequestInit = {}, timeoutMs = 15000): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API}${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...options.headers }, cache: 'no-store', signal: AbortSignal.timeout(timeoutMs) });
  } catch {
    throw new Error(options.method && options.method !== 'GET'
      ? 'Request interrupted. Refresh saved data before retrying; the change may have been saved.'
      : 'Backend unavailable or request timed out. Check that FastAPI is running on port 8000.');
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${response.status}). Check your input and try again.`);
  }
  return response.status === 204 ? undefined as T : response.json();
}
export function imageUrl(task: Task, checkpoint: Checkpoint) {
  return `${API}/api/tasks/${task.id}/steps/${checkpoint.id}/image?v=${encodeURIComponent(checkpoint.reference_image)}`;
}

export type VerificationResult = {
  status: 'PASS' | 'FAIL' | 'UNCERTAIN'; expected: string; observed: string;
  feedback: string; confidence: 'low' | 'medium' | 'high'; step_id: number;
  model: string; assessed_at: string; reference_image: string;
  reference_data_url: string; learner_data_url: string;
};
export type ServerSession = {
  session_id: string; tutorial_version: string; completed_step_ids: number[];
  active_step_id: number | null; total: number; complete: boolean;
  last_result: VerificationResult | null; busy: boolean; resumed?: boolean;
};

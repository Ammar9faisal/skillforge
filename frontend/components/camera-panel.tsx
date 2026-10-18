'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Camera, Radio, RefreshCw, ScanLine, ShieldCheck } from 'lucide-react';
import { API, request } from '../lib/api';
type Status = { available: boolean; index: number | null; source: 'webcam' | 'whatsapp'; source_revision: [number, number]; width: number; height: number; error: string | null };
// Safari can fail to paint long-lived multipart JPEG streams. Keep preview
// requests bounded and serial; the backend MJPEG endpoint remains available.
function CameraPreview({ revision, fps, onError, onReady }: {
  revision: string; fps: number; onError: () => void; onReady: () => void;
}) {
  const [url, setUrl] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    let currentUrl = '';
    let timer: ReturnType<typeof setTimeout>;
    async function nextFrame() {
      const started = performance.now();
      let failed = false;
      try {
        const response = await fetch(`${API}/api/camera/frame?preview=true`, { cache: 'no-store', signal: controller.signal });
        if (!response.ok) throw new Error('Camera frame unavailable');
        const blob = await response.blob();
        if (!active) return;
        const nextUrl = URL.createObjectURL(blob);
        const previousUrl = currentUrl;
        currentUrl = nextUrl; setUrl(nextUrl);
        if (previousUrl) URL.revokeObjectURL(previousUrl);
      } catch {
        failed = true;
        if (active) onError();
      } finally {
        // Include fetch/encode time in the frame interval, and never overlap
        // requests or build a backlog when the camera/backend is slower.
        const delay = failed ? 1000 : Math.max(0, 1000 / fps - (performance.now() - started));
        if (active) timer = setTimeout(nextFrame, delay);
      }
    }
    setUrl(''); void nextFrame();
    return () => { active = false; controller.abort(); clearTimeout(timer); if (currentUrl) URL.revokeObjectURL(currentUrl); };
  }, [revision, fps, onError]);
  return url ? <img src={url} alt="Live camera view of your physical workspace" onLoad={onReady} onError={onError}/> : null;
}
export default function CameraPanel({ onAvailability }: { onAvailability: (value: boolean) => void }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [connectionError, setConnectionError] = useState('');
  const [streamError, setStreamError] = useState('');
  const [index, setIndex] = useState(0);
  const observedIndex = useRef<number | null>(null);
  const observedRevision = useRef<string | null>(null);
  const [busy, setBusy] = useState(false);
  const locked = useRef(false);
  const [revision, setRevision] = useState(0);
  const previewError = useCallback(() => setStreamError('Live preview interrupted. Check the selected source and reconnect.'), []);
  const previewReady = useCallback(() => setStreamError(''), []);
  useEffect(() => {
    let active = true;
    let polling = false;
    async function poll() {
      if (polling || locked.current) return;
      polling = true;
      try {
        const data = await request<Status>('/api/camera/status');
        if (!active || locked.current) return;
        setStatus(data); setConnectionError(''); onAvailability(data.available);
        if (data.index !== null && data.index !== observedIndex.current) {
          setIndex(data.index); observedIndex.current = data.index;
        }
        const currentRevision = JSON.stringify(data.source_revision);
        if (observedRevision.current !== currentRevision) {
          observedRevision.current = currentRevision;
          setRevision(r => r + 1); setStreamError('');
        }
      } catch (e) { if (active) { setStatus(null); onAvailability(false); setConnectionError((e as Error).message); } }
      finally { polling = false; }
    }
    void poll(); const timer = setInterval(poll, 2000);
    return () => { active = false; clearInterval(timer); onAvailability(false); };
  }, [onAvailability]);
  async function reconnect(source: 'webcam' | 'whatsapp' = status?.source || 'webcam') {
    if (locked.current) return;
    locked.current = true; setBusy(true); onAvailability(false); setStreamError('');
    try {
      const next = await request<Status>('/api/camera/source', { method: 'POST', body: JSON.stringify({ source, ...(source === 'webcam' ? { index } : {}) }) });
      setStatus(next); onAvailability(next.available);
      setRevision(r => r + 1); setConnectionError('');
    } catch (e) { setConnectionError((e as Error).message); }
    finally { locked.current = false; setBusy(false); }
  }
  return <section className={`vision panel ${status?.available ? 'camera-active' : 'camera-offline'}`}><div className="panel-header"><span><ScanLine size={17}/> LIVE VISION</span><span className={status?.available ? 'text-cyan' : ''}>{status?.available ? `ACTIVE · ${status.width} × ${status.height}` : 'OFFLINE'}</span></div><div className="viewport"><div className="camera-sweep" aria-hidden="true"/><div className="corner tl" aria-hidden="true"/><div className="corner tr" aria-hidden="true"/><div className="corner bl" aria-hidden="true"/><div className="corner br" aria-hidden="true"/>{status?.available ? <CameraPreview key={`${status.source}:${revision}`} revision={`${status.source}:${revision}`} fps={status.source === 'whatsapp' ? 2 : 15} onError={previewError} onReady={previewReady}/> : <div className="camera-empty"><div className="camera-icon"><Camera size={32}/></div><h3>Connect your perspective.</h3><p>{connectionError || status?.error || 'Connecting to the camera service…'}</p><span>{status?.source === 'whatsapp' ? 'WHATSAPP RAY-BANS' : 'USB / BUILT-IN CAMERA'}</span></div>}<div className="hud"><span><Radio size={13}/> {status?.available ? 'LIVE FEED' : 'NO SIGNAL'}</span><span>SKILLFORGE VISION ENGINE</span></div></div><div className="camera-controls"><label>Source <select aria-label="Camera source" value={status?.source || 'webcam'} disabled={busy || !status} onChange={e => void reconnect(e.target.value as 'webcam' | 'whatsapp')}><option value="webcam">USB Webcam</option><option value="whatsapp">WhatsApp Ray-Bans</option></select></label></div><div className="camera-controls">{status?.source !== 'whatsapp' && <label>Camera device <input aria-label="Camera device index" type="number" min="0" max="20" disabled={busy} value={index} onChange={e => setIndex(Number(e.target.value))}/></label>}<button disabled={busy || !Number.isInteger(index) || index < 0 || index > 20} onClick={() => void reconnect()}><RefreshCw size={15} className={busy ? 'spin' : ''}/>{busy ? 'Connecting…' : 'Reconnect'}</button></div>{status?.source === 'whatsapp' && <p className="camera-privacy">Run the native capture helper in VS Code and select the call window. Keep its size fixed; restart the helper after reopening or resizing the call.</p>}{(streamError || connectionError) && <p role="alert" className="error">{streamError || connectionError}</p>}<div className="camera-privacy"><ShieldCheck size={15}/><span>Preview stays local. Only intentional checkpoints are saved.</span></div></section>;
}

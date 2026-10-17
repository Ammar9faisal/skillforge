'use client';
import { useEffect, useRef, useState } from 'react';
import { Camera, Radio, RefreshCw, ScanLine, ShieldCheck } from 'lucide-react';
import { API, request } from '../lib/api';
type Status = { available: boolean; index: number; width: number; height: number; error: string | null };
export default function CameraPanel({ onAvailability }: { onAvailability: (value: boolean) => void }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [connectionError, setConnectionError] = useState('');
  const [streamError, setStreamError] = useState('');
  const [index, setIndex] = useState(0);
  const initialized = useRef(false);
  const [busy, setBusy] = useState(false);
  const locked = useRef(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    let polling = false;
    async function poll() {
      if (polling) return;
      polling = true;
      try {
        const data = await request<Status>('/api/camera/status');
        if (!active) return;
        setStatus(data); setConnectionError(''); onAvailability(data.available);
        if (!initialized.current) { setIndex(data.index); initialized.current = true; }
      } catch (e) { if (active) { setStatus(null); onAvailability(false); setConnectionError((e as Error).message); } }
      finally { polling = false; }
    }
    void poll(); const timer = setInterval(poll, 2000);
    return () => { active = false; clearInterval(timer); onAvailability(false); };
  }, [onAvailability]);
  async function reconnect() {
    if (locked.current) return;
    locked.current = true; setBusy(true); setStreamError('');
    try {
      setStatus(await request<Status>('/api/camera/reconnect', { method: 'POST', body: JSON.stringify({ index }) }));
      setRevision(r => r + 1); setConnectionError('');
    } catch (e) { setConnectionError((e as Error).message); }
    finally { locked.current = false; setBusy(false); }
  }
  return <section className="vision panel"><div className="panel-header"><span><ScanLine size={17}/> LIVE VISION</span><span className={status?.available ? 'text-cyan' : ''}>{status?.available ? `ACTIVE · ${status.width} × ${status.height}` : 'OFFLINE'}</span></div><div className="viewport"><div className="corner tl"/><div className="corner tr"/><div className="corner bl"/><div className="corner br"/>{status?.available ? <img key={revision} src={`${API}/api/camera/stream?v=${revision}`} alt="Live camera view of your physical workspace" onError={() => setStreamError('Live stream interrupted. Reconnect the camera.')} /> : <div className="camera-empty"><div className="camera-icon"><Camera size={32}/></div><h3>Connect your perspective.</h3><p>{connectionError || status?.error || 'Connecting to the camera service…'}</p><span>USB CAMERA / BUILT-IN CAMERA</span></div>}<div className="hud"><span><Radio size={13}/> {status?.available ? 'LIVE FEED' : 'NO SIGNAL'}</span><span>SKILLFORGE VISION ENGINE</span></div></div><div className="camera-controls"><label>Camera device <input aria-label="Camera device index" type="number" min="0" max="20" disabled={busy} value={index} onChange={e => setIndex(Number(e.target.value))}/></label><button disabled={busy || !Number.isInteger(index) || index < 0 || index > 20} onClick={reconnect}><RefreshCw size={15} className={busy ? 'spin' : ''}/>{busy ? 'Connecting…' : 'Reconnect'}</button></div>{(streamError || connectionError) && <p role="alert" className="error">{streamError || connectionError}</p>}<div className="camera-privacy"><ShieldCheck size={15}/><span>Preview stays local. Only intentional checkpoints are saved.</span></div></section>;
}

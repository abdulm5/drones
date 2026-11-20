import { useState } from 'react';

export default function VideoPage() {
  const [error, setError] = useState(false);
  return <main className="recording-page">
    <video className="recording" controls autoPlay muted loop playsInline preload="auto"
      aria-label="AgriForce demo recording" onError={() => setError(true)}>
      <source src="/demo.mp4" type="video/mp4" />
      <a href="/demo.mp4">Download the AgriForce recording</a>
    </video>
    <div className="recording-label"><img src="/brand/logo-mark-on-dark.svg" alt="" />
      <span>AgriForce</span><small>DEMO RECORDING</small>
    </div>
    {error && <p className="recording-error">The recording could not load. <a href="/demo.mp4">Open the video directly</a>.</p>}
  </main>;
}

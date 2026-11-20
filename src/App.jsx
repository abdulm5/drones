import { Component, useEffect, useRef, useState } from 'react';
import { Activity, ArrowDownToLine, BatteryMedium, Check, ChevronDown, ChevronLeft, Cloud,
  Crosshair, Download, ExternalLink, Globe2, Layers, LockKeyhole, MapPin, Maximize2,
  Play, Radio, RefreshCw, Satellite, ShieldCheck, Square, TriangleAlert, Wind, X } from 'lucide-react';
import Globe from './Globe.jsx';

class GlobeBoundary extends Component {
  state = { error: null };
  static getDerivedStateFromError(error) { return { error }; }
  componentDidCatch(error) { console.error('Cesium view:', error.message); }
  render() {
    return this.state.error ? <div className="globe-error" role="alert">The globe could not render. {this.state.error.message} Refresh the page to retry. The observation queue and mission checks remain available.</div> : this.props.children;
  }
}

const initialScenario = { low_battery: false, cloud: false, stale: false, exclusion: true };
const fmt = (value, digits = 2) => value == null ? 'MISSING' : Number(value).toFixed(digits);
const shortDate = value => value?.slice(0, 10) || 'Unverified';
const localDate = value => value ? new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Los_Angeles' }).format(new Date(value)) : 'Unverified';
const time = seconds => `${String(Math.floor((seconds || 0) / 60)).padStart(2, '0')}:${String(Math.floor((seconds || 0) % 60)).padStart(2, '0')}`;

async function api(path, body) {
  const response = await fetch(`/api${path}`, body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === 'string' ? error.detail : `Request failed (${response.status})`);
  }
  return response.json();
}

function Lamp({ mode, label }) {
  return <span className={`lamp ${mode === 'LIVE' ? 'go' : 'amber'}`}><i />{label || mode}</span>;
}

function Source({ children, date }) {
  return <div className="source">{children}{date && <span>{shortDate(date)}</span>}</div>;
}

function Metric({ label, value, unit, tone }) {
  return <div className={`metric ${tone || ''}`}><span>{label}</span><strong>{value}<small>{unit}</small></strong></div>;
}

function Toggle({ label, checked, onChange, disabled, hint }) {
  return <label className={`toggle-row ${disabled ? 'disabled' : ''}`} title={hint}>
    <span>{label}{hint && <small>{hint}</small>}</span>
    <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} disabled={disabled} />
    <span className="toggle-switch" aria-hidden="true" />
  </label>;
}

function Logo() {
  return <svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M4 24 16 5l12 19M10 24l6-10 6 10M4 28h24" stroke="currentColor" strokeWidth="2" /><path d="M2 17h8M22 17h8" stroke="currentColor" strokeWidth="2" /></svg>;
}

function Evidence({ packet, scenario, data }) {
  const [expanded, setExpanded] = useState(false);
  return <div className="evidence">
    <div className="section-label">WITHIN-FIELD CONJUNCTION <span>10 m</span></div>
    <div className="spectral-metrics">
      <Metric label="Mean NDVI" value={fmt(packet.ndvi.mean)} />
      <Metric label="Anomaly gap" value={fmt(packet.anomaly_gap, 3)} tone="amber" />
    </div>
    <Source date={packet.scene_datetime}>Sentinel-2 L2A · B04 / B08</Source>
    <div className="distribution" aria-label="NDVI distribution">
      <div className="distribution-scale" />
      <div className="distribution-marker" style={{ left: `${Math.max(0, Math.min(100, ((packet.ndvi.mean || 0) - .1) / .45 * 100))}%` }}><span>mean</span></div>
    </div>
    <div className="scale-labels"><span>0.10 / SOIL</span><span>0.55 / VEGETATION</span></div>
    <div className="evidence-table">
      <div><span>Clear pixels</span><b>{scenario.cloud ? '10% · SCENARIO' : `${fmt(packet.clear_pixel_fraction * 100, 0)}%`} <small>SCL 4 + 5</small></b></div>
      <div><span>NDVI p10 / p90</span><b>{fmt(packet.ndvi.p10)} / {fmt(packet.ndvi.p90)}</b></div>
      <div><span>NDMI</span><b>{fmt(packet.ndmi.mean)} <small>20 m SWIR</small></b></div>
      <div><span>Observation age</span><b className={scenario.stale ? 'red-text' : ''}>{scenario.stale ? '>30 d · SCENARIO' : `${packet.scene_age_days} days`}</b></div>
    </div>
    <p className="note">Gap below the leave-one-out 20th percentile of the same CDL class inside this polygon. A gap is not a diagnosis.</p>

    <div className="section-label">CROP CLASSIFICATION <span>ANNUAL</span></div>
    <div className="crop-name">{packet.cdl.name}<span>CDL {packet.cdl.code}</span></div>
    <Source date="2025">USDA NASS CDL · 30 m</Source>
    <p className="note">Annual classification; current crop and growth stage are unconfirmed.</p>

    <div className="section-label">GROUND CONTEXT <span>REGIONAL</span></div>
    <div className="context-row"><Wind size={16} /><span>14-day rain</span><b>{fmt(packet.power.rain_mm, 1)}<small> mm</small></b></div>
    <div className="context-row"><Activity size={16} /><span>Mean air temperature</span><b>{fmt(packet.power.temperature_c, 1)}<small> °C</small></b></div>
    <Source date={packet.power.end}>NASA POWER · {packet.power.start} to</Source>
    <p className="note">~0.5° weather cell. {packet.power.rain_days_present}/14 rain days present; {packet.power.missing_values} missing values. Cannot resolve within-field causes.</p>
    <div className="soil-line"><span>{packet.ssurgo.texture}</span><b>{packet.ssurgo.component_pct}% component</b></div>
    <div className="soil-metrics"><span>OM <b>{packet.ssurgo.organic_matter_pct}%</b></span><span>pH <b>{packet.ssurgo.ph}</b></span><span>Clay <b>{packet.ssurgo.clay_pct}%</b></span></div>
    <Source date={packet.ssurgo.date}>USDA SSURGO · center-point context</Source>
    <p className="note">Organic matter is not nitrate. No measured nitrate is available.</p>

    <button className="disclosure" onClick={() => setExpanded(!expanded)} aria-expanded={expanded}>Layer details & provenance <ChevronDown size={15} className={expanded ? 'rotated' : ''} /></button>
    {expanded && <div className="layer-detail">
      <p>{packet.field_source}</p>
      <p>Scene: <span className="mono">{data.scene.id}</span></p>
      <p>Acquired: <span className="mono">{packet.scene_datetime}</span></p>
      <p>Reflectance: DN × 0.0001 − 0.1. Fixture NDVI check: {data.validation.clear_ndvi_mean} (expected 0.30).</p>
      <p>SCL counts: {Object.entries(packet.scl_counts).map(([k,v]) => `${k}: ${v}`).join(' / ')}. Only classes 4 and 5 retained.</p>
      <p>SSURGO texture: {packet.ssurgo.sand_pct}% sand / {packet.ssurgo.silt_pct}% silt / {packet.ssurgo.clay_pct}% clay.</p>
      {Object.entries(data.status).map(([key, status]) => <p key={key}><b>{key.toUpperCase()} / {status.mode}</b><br />{status.reason || 'Live request succeeded.'}</p>)}
    </div>}
  </div>;
}

export default function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [tab, setTab] = useState('evidence');
  const [scenario, setScenario] = useState(initialScenario);
  const [mission, setMission] = useState(null);
  const [progress, setProgress] = useState(0);
  const [flying, setFlying] = useState(false);
  const [busy, setBusy] = useState(false);
  const [packet, setPacket] = useState(null);
  const [advice, setAdvice] = useState(null);
  const [humanGo, setHumanGo] = useState(false);
  const [gate, setGate] = useState(null);
  const [product, setProduct] = useState('');
  const [stateOverride, setStateOverride] = useState(false);
  const [testGate, setTestGate] = useState(null);
  const [ndviVisible, setNdviVisible] = useState(true);
  const [overviewKey, setOverviewKey] = useState(0);
  const [application, setApplication] = useState(false);
  const [speed, setSpeed] = useState(32);
  const [utc, setUtc] = useState(new Date());
  const [events, setEvents] = useState([{ message: 'Connecting observation layers', at: new Date() }]);
  const generation = useRef(0);
  const selected = data?.fields.find(f => f.id === selectedId);
  const current = mission?.trace?.[Math.min(mission.trace.length - 1, Math.floor(progress * (mission.trace.length - 1)))];
  const deferred = scenario.cloud || scenario.stale || selected?.packet.action === 'defer_observation';
  const log = message => setEvents(e => [{ message, at: new Date() }, ...e].slice(0, 7));

  async function load(refresh = false) {
    setLoading(true); setError(null);
    try {
      const result = await api('/fuse', { refresh });
      generation.current++;
      setData(result); setSelectedId(null); resetMission();
      log(`${result.fields.length} DWR polygons fused · Sentinel-2 ${result.status.sentinel.mode}`);
      console.info('STAC datetime:', result.scene.datetime, 'POWER end date:', result.status.power.end_date);
    } catch (err) { setError(err.message); log(err.message); }
    finally { setLoading(false); }
  }

  function resetMission() {
    setMission(null); setPacket(null); setAdvice(null); setGate(null); setTestGate(null);
    setHumanGo(false); setProgress(0); setFlying(false); setApplication(false); setStateOverride(false);
  }

  function selectField(id) {
    if (flying || busy) return;
    generation.current++;
    setSelectedId(id); setTab('evidence'); resetMission();
    log(`Evidence selected / ${id}`);
  }

  useEffect(() => { load(); }, []);
  useEffect(() => { const id = setInterval(() => setUtc(new Date()), 1000); return () => clearInterval(id); }, []);

  useEffect(() => {
    if (!flying || !mission?.trace?.length) return;
    let raf;
    let previous = performance.now();
    let p = progress;
    const tick = now => {
      p = Math.max(0, Math.min(1, p + Math.max(0, now - previous) / 1000 * speed / Math.max(1, mission.duration_s)));
      previous = now;
      setProgress(p);
      if (p < 1) raf = requestAnimationFrame(tick);
      else {
        setFlying(false);
        if (application) { log('Simulated application playback complete'); return; }
        log(mission.status === 'returned_early' ? 'AF-1 landed / battery return constraint respected' : 'AF-1 landed / findings packet filed');
        finishMission(mission.mission_id);
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [flying, mission?.mission_id, speed, application]);

  async function finishMission(id) {
    const token = generation.current;
    try {
      const [findings, advisory] = await Promise.all([api(`/missions/${id}/findings`), api(`/missions/${id}/advice`)]);
      if (token !== generation.current) return;
      setPacket(findings); setAdvice(advisory); setTab('review');
      const decision = await api('/gate', { mission_id: id, human_go: false, product_name: product });
      if (token === generation.current) setGate(decision);
    } catch (err) { setError(err.message); }
  }

  async function dispatch() {
    if (!selected || busy || flying) return;
    setBusy(true); setError(null); resetMission();
    const token = generation.current;
    try {
      const result = await api('/simulate', { snapshot_id: data.snapshot_id, field_id: selected.id, ...scenario });
      if (token !== generation.current) return;
      setMission(result); setTab('mission');
      if (result.status === 'deferred') { log(result.reason); setError(result.reason); return; }
      log(`AF-1 dispatched / ${scenario.low_battery ? 'low battery scenario' : 'simulated inspection'}`);
      setProgress(0); setFlying(true);
    } catch (err) { setError(err.message); log(`Dispatch held / ${err.message}`); }
    finally { setBusy(false); }
  }

  async function updateGate(go, proposed = product) {
    setBusy(true); setError(null);
    try {
      const result = await api('/gate', { mission_id: mission.mission_id, human_go: go, product_name: proposed });
      setHumanGo(go); setGate(result); setProduct(proposed);
      if (stateOverride) await testState(true, proposed, go);
      log(`Human ${go ? 'GO' : 'NO-GO'} / policy ${result.status.toUpperCase()}`);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function testState(enabled, candidate = product, accepted = humanGo) {
    setStateOverride(enabled); setTestGate(null);
    if (!enabled) return;
    try {
      const result = await api('/gate', { mission_id: mission.mission_id, human_go: accepted,
        product_name: candidate, state_override: '15' });
      setTestGate(result);
      log(`Hawaiʻi policy test / ${result.status.toUpperCase()} · field remains in California`);
    } catch (err) { setError(err.message); }
  }

  async function apply() {
    setBusy(true); setError(null);
    try {
      const result = await api('/apply', { mission_id: mission.mission_id });
      if (!result.simulated) throw new Error('Only simulated application is supported');
      setApplication(true); setProgress(0); setFlying(true); setTab('mission');
      log('SIMULATED APPLICATION / independent gates passed');
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  function downloadPacket() {
    if (!packet) return;
    const blob = new Blob([JSON.stringify({ simulated: true, ...packet, advisory: advice, gates: gate }, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `agriforge-${selected.id}-${mission.mission_id.slice(0, 8)}.json`; anchor.click();
    URL.revokeObjectURL(url);
  }

  const candidateFields = data?.fields.filter(f => f.packet.score > 0 || f.packet.action === 'defer_observation') || [];
  const visibleFields = candidateFields.slice(0, 12);
  const catalogProducts = [...new Set(data?.policy_catalog.map(row => row.product_name) || [])];
  const lastEvent = events[0];
  return <main className={`app ${selected ? 'has-selection' : ''}`}>
    <GlobeBoundary><Globe data={data} selected={selected} onSelect={selectField} mission={mission} progress={progress} flying={flying}
      ndviVisible={ndviVisible} scenario={scenario} overviewKey={overviewKey} application={application} /></GlobeBoundary>
    <div className="top-shade" />
    <header className="topbar">
      <a href="/" className="brand" aria-label="AGRIFORGE home"><Logo /><span>AGRI<span>FORGE</span></span><small>FIELD OPERATIONS</small></a>
      <div className="topbar-middle"><span className="slash">/</span><span>WEST SIDE REC</span><span className="state-code">CA · 06</span></div>
      <div className="topbar-right"><span className="sim-tag"><Radio size={13} /> SIMULATED VEHICLES</span><time>{utc.toISOString().slice(11, 19)} <span>UTC</span></time></div>
    </header>

    <aside className="left-rail" aria-label="Field observation queue">
      <div className="site-heading"><div className="eyebrow"><MapPin size={13} /> FRESNO COUNTY, CALIFORNIA</div><h1>Five Points<span>.</span></h1>
        <p>UC West Side Research & Extension Center</p><div className="coordinates">36.341988° N &nbsp; 120.108177° W</div></div>
      <div className="feed-strip">
        <div><Satellite size={15} /><span>SENTINEL-2</span>{data ? <Lamp mode={data.status.sentinel.mode} /> : <span className="connecting">LINKING</span>}</div>
        <div><Wind size={15} /><span>NASA POWER</span>{data ? <Lamp mode={data.status.power.mode} /> : <span className="connecting">LINKING</span>}</div>
      </div>
      <div className="queue-heading"><span>PRIORITY QUEUE</span><span>{data ? String(candidateFields.length).padStart(2, '0') : '—'} FIELDS</span></div>
      <div className="queue-description">Ranked by same-crop NDVI gap × clear fraction.</div>
      <div className="field-queue">
        {loading && !data ? <div className="loading-fields"><div className="scan-line" /><Satellite size={22} /><b>Fusing observation layers</b><span>Querying Earth Search & NASA POWER.<br />Window-reading the latest clear scene.</span></div> : visibleFields.map(field =>
          <button key={field.id} className={`field-row ${selectedId === field.id ? 'selected' : ''}`} onClick={() => selectField(field.id)} disabled={flying || busy}>
            <span className={`field-pin ${field.packet.action === 'defer_observation' || scenario.cloud || scenario.stale ? 'hollow' : ''}`} />
            <span className="field-info"><strong>{field.packet.cdl.name}</strong><span>{field.id} <i>·</i> {field.packet.scene_age_days}d ago</span></span>
            <span className="field-score">{fmt(field.packet.score, 3)}<small>GAP × CLEAR</small></span>
          </button>)}
        {!loading && !data && <div className="empty-state"><TriangleAlert size={20} /><p>Observation service unavailable.</p><button onClick={() => load()}>Retry connection</button></div>}
        {data && visibleFields.length === 0 && <div className="empty-state">No within-field anomalies found. Refresh when another scene is available.</div>}
      </div>
      <div className="queue-footer"><span>{data ? `${data.fields.length} polygons processed` : 'MGRS TILE 10SGF'}</span><button className="icon-button" onClick={() => load(true)} disabled={loading || flying || busy} aria-label="Refresh live observations"><RefreshCw size={14} className={loading ? 'spin' : ''} /></button></div>
      <div className="layer-ledger"><div className="section-label">OBSERVATION REGISTER</div>
        <div><span>Sentinel-2 / 10 m</span><b>{shortDate(data?.scene.datetime)}</b></div>
        <div><span>POWER / regional</span><b>{data?.status.power.end_date || '—'}</b></div>
        <div><span>USDA CDL / annual</span><b>2025</b></div>
        <div><span>DWR / provisional</span><b>2024</b></div>
        <div><span>SSURGO / retrieved</span><b>2026-11-19</b></div>
      </div>
      <button className="orbit-button" onClick={() => { if (!flying && !busy) { setSelectedId(null); resetMission(); setOverviewKey(k=>k+1); } }} disabled={flying || busy}><Globe2 size={16} /> Return to orbit <Maximize2 size={13} /></button>
    </aside>

    {!selected && <div className="orbit-caption"><div className="orbit-crosshair"><i /><i /></div><span>FIVE POINTS, CALIFORNIA</span><p>{data ? 'Select a field to open its evidence and inspection plan.' : 'Establishing the observation window.'}</p><div className="orbit-location">EARTH / 36.34 N · 120.11 W</div></div>}

    <div className="scene-meta"><span className="eyebrow">{selected ? 'FIELD VIEW' : 'ORBIT VIEW'}</span><span>{selected ? selected.id : 'WESTERN UNITED STATES'}</span><small>{data ? `${shortDate(data.scene.datetime)} · ${data.scene.age_days}D OBSERVATION AGE` : 'ACQUIRING OBSERVATIONS'}</small></div>

    {selected && <aside className="right-console" aria-label="Field mission console">
      <div className="console-title"><div><div className="eyebrow">FIELD EVIDENCE / {String(selected.rank).padStart(2, '0')}</div><h2>{selected.id}</h2></div><button className="icon-button" aria-label="Close field console" onClick={() => { setSelectedId(null); resetMission(); setOverviewKey(k=>k+1); }} disabled={flying || busy}><X size={18} /></button></div>
      <div className="observation-status"><span className={deferred ? 'red-text' : 'amber-text'}><i className={`status-dot ${deferred ? 'red' : ''}`} />{deferred ? 'DEFER OBSERVATION' : 'INSPECTION CANDIDATE'}</span><span>NOT A DIAGNOSIS</span></div>
      <nav className="console-tabs" aria-label="Console sections">{['evidence','mission','review'].map(t => <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>{t}{t==='review' && packet && <span className="tab-dot" />}</button>)}</nav>
      <div className="console-scroll">
        {tab === 'evidence' && <Evidence packet={selected.packet} scenario={scenario} data={data} />}
        {tab === 'mission' && <>
          <div className="section-label">INSPECTION PLAN <span>SIMULATED</span></div>
          <div className="mission-vehicle"><div className="drone-glyph">✣</div><div><b>AF-1</b><span>{flying ? 'Executing simulated mission' : mission ? mission.status.replaceAll('_', ' ') : 'Ready at authored depot'}</span></div><span className="vehicle-badge">INSPECTION</span></div>
          <div className="evidence-table"><div><span>Grid spacing</span><b>30 m</b></div><div><span>Altitude</span><b>40 m AGL</b></div><div><span>Ground speed</span><b>8 m/s</b></div><div><span>Battery reserve</span><b className="green-text">25% incl. return</b></div><div><span>Payload</span><b>0 g · optical inspection</b></div></div>
          <p className="note">Lawnmower lanes and connectors stay inside the polygon. An authored 16 m transit corridor joins the depot to the field. No real aircraft is connected.</p>
          <div className="section-label">CONSTRAINT SCENARIOS <span>AUTHORED</span></div>
          {[['low_battery','Low battery','Return early, preserve reserve'],['cloud','Cloud cover','Defer inspection'],['stale','Stale observation','Defer when older than 30 days'],['exclusion','Exclusion wedge','Reject intersecting segments']].map(([key,label,hint]) => <Toggle key={key} label={label} hint={hint} checked={scenario[key]} disabled={flying || busy} onChange={value => { setScenario(s=>({...s,[key]:value})); resetMission(); log(`${label} scenario ${value?'armed':'cleared'}`); }} />)}
          {mission?.verification && <><div className="section-label">INDEPENDENT PATH CHECK <ShieldCheck size={15} /></div><div className="verification-grid"><Metric label="Geofence" value={mission.verification.geofence_violations} unit="violations" tone="green" /><Metric label="Exclusion" value={mission.verification.exclusion_violations} unit="violations" tone="green" /></div><p className="note">Full-segment geometry check. Linear energy: 1% / 80 m. No wind or turn costs. Simulation checks provide no formal flight certification.</p></>}
          {mission?.status === 'returned_early' && <div className="notice amber"><BatteryMedium size={17} /><span>Return constraint reached. AF-1 turns home before the reserve is breached. Planned landing {fmt(mission.battery_at_landing_pct, 1)}%.</span></div>}
          {mission?.rejected_segments?.length > 0 && <div className="notice"><ShieldCheck size={17} /><span>{mission.rejected_segments.length} proposed lane segments rejected at the authored exclusion wedge. Red dashes mark rejected segments.</span></div>}
          <div className="cold-vehicle"><span className="cold-dot" /><b>AF-2</b><span>COLD ON PAD</span><p>Single-vehicle inspection. AF-2 remains unassigned.</p></div>
        </>}
        {tab === 'review' && (!packet ? <div className="empty-state review-empty"><ShieldCheck size={28} /><h3>Awaiting findings</h3><p>Dispatch AF-1 and let it return. Its findings packet becomes the consultant’s only input.</p><button onClick={() => setTab('mission')}>Open inspection plan</button></div> : <>
          <div className="section-label">FINDINGS FILED <span>SIMULATED</span></div>
          <div className="findings-summary"><Check size={17} /><span>{mission.status === 'completed' ? 'Inspection complete' : 'Inspection returned early'}<small>{localDate(packet.filed_at)} PT · {selected.id}</small></span><button className="icon-button" onClick={downloadPacket} aria-label="Download findings JSON"><Download size={17} /></button></div>
          <div className="verification-grid"><Metric label="Simulated samples" value={mission.samples} /><Metric label="Path length" value={fmt(mission.distance_m/1000)} unit="km" /><Metric label="Landing battery" value={fmt(mission.battery_at_landing_pct,1)} unit="%" /><Metric label="Geofence violations" value={mission.verification?.geofence_violations ?? '—'} tone="green" /></div>
          <Source date={packet.filed_at}>Simulated AF-1 telemetry · not crop measurements</Source>
          <div className="section-label">CONSULTANT <span>TEMPLATE</span></div>
          <div className="advisory-action"><ArrowDownToLine size={18} /><strong>{advice?.action.replaceAll('_',' ')}</strong></div>
          <p className="speaker">Speaker: {advice?.speaker}. Reads only the JSON findings packet.</p>
          {advice?.sentences.map((sentence,i) => <p className="advisory-sentence" key={i}><span>{sentence.layer} · {shortDate(sentence.date)}</span>{sentence.text}</p>)}
          <div className="missing-evidence"><div className="eyebrow"><TriangleAlert size={13} /> MISSING AGRONOMIC EVIDENCE</div>{packet.missing_agronomic_fields.map(item => <div key={item}><span>—</span>{item}</div>)}</div>
          <p className="note">Possible explanations: {packet.alternative_explanations.join(', ')}. None is selected as fact. No treatment rate is proposed.</p>
          <div className="section-label">HUMAN GATE <span className={humanGo?'green-text':'red-text'}>{humanGo?'GO':'NO-GO'}</span></div>
          <p className="note">GO accepts the inspection record. Application requires an independent policy GO.</p>
          <div className="human-buttons"><button className={!humanGo?'selected-no':''} disabled={busy || flying} onClick={() => updateGate(false)}><X size={16} />NO-GO</button><button className={humanGo?'selected-go':''} disabled={busy || flying} onClick={() => updateGate(true)}><Check size={16} />GO / accept record</button></div>
          <div className="section-label">STATE POLICY GATE <span>CA · 06</span></div>
          <label className="select-label" htmlFor="product">Proposed product</label><div className="select-wrap"><select id="product" value={product} disabled={busy || flying} onChange={e => updateGate(humanGo,e.target.value)}><option value="">No approved product</option>{catalogProducts.map(p=><option key={p}>{p}</option>)}</select><ChevronDown size={15} /></div>
          {gate && <div className={`policy-result ${gate.policy_go ? 'go' : 'no-go'}`}><div><ShieldCheck size={17} /><b>{gate.policy_go?'GO':'NO-GO'} / {gate.status.toUpperCase()}</b></div><p>{gate.reason}</p>{gate.mission_veto && <p>{gate.mission_veto}</p>}{gate.row && <><small>{gate.row.authority}</small><p>{gate.row.restriction}</p><a href={gate.row.citation} target="_blank" rel="noreferrer">Official state authority <ExternalLink size={12} /></a></>}</div>}
          <div className="policy-test"><Toggle label="State override" hint="SIMULATED POLICY TEST / Hawaiʻi · 15" checked={stateOverride} onChange={v => testState(v)} disabled={busy || flying} />{stateOverride && <>
            <p className="note">The field and all satellite evidence remain in California. This compares the same product under Hawaiʻi policy, using the field’s actual CDL class.</p>
            <p className="note">Compared product: {product || 'No approved product'}.</p>
            {testGate && <div className="policy-result no-go"><div><ShieldCheck size={17} /><b>{testGate.status.toUpperCase()} / HAWAIʻI</b></div><p>{testGate.reason}</p>{testGate.row ? <><small>{testGate.row.authority}</small><p>{testGate.row.restriction}</p><a href={testGate.row.citation} target="_blank" rel="noreferrer">Official state authority <ExternalLink size={12} /></a></> : <p>No verified entry for CDL {selected.packet.cdl.code}. Select Lorsban Advanced above on a Cotton field to inspect the cited prohibition.</p>}</div>}
          </>}</div>
          <button className="application-button" disabled={!gate?.application_unlocked || busy || flying} onClick={apply}><LockKeyhole size={16} />{gate?.application_unlocked ? 'Play simulated application' : 'APPLICATION LOCKED'}</button>
        </>)}
      </div>
      <div className="console-action"><div><span className={deferred?'red-text':'amber-text'}>{deferred?'OBSERVATION DEFERRED':flying?'SIMULATED MISSION ACTIVE':'AF-1 / INSPECTION READY'}</span><small>{deferred?'Clear, recent imagery required':flying?`${Math.round(progress*100)}% of simulated track`:'Human review follows inspection'}</small></div><button className="dispatch-button" disabled={flying || busy || loading} onClick={dispatch}>{busy?<RefreshCw size={15} className="spin"/>:flying?<Radio size={15}/>:<Play size={15}/>} {deferred?'CHECK HOLD':flying?'IN FLIGHT':'DISPATCH'}</button></div>
    </aside>}

    <div className="map-controls"><button className={ndviVisible?'active':''} onClick={() => setNdviVisible(v=>!v)} disabled={!selected} aria-label="Toggle Sentinel-2 NDVI measurement overlay" aria-pressed={ndviVisible}><Layers size={17} /><span>NDVI</span></button><button onClick={() => selected ? selectField(selected.id) : visibleFields[0] && selectField(visibleFields[0].id)} disabled={flying || busy} aria-label="Focus highest priority field"><Crosshair size={17} /></button></div>
    {selected && <div className="map-legend"><span>MEASUREMENT / SENTINEL-2</span><div className="legend-bar"/><div><b>0.10</b><span>NDVI · 10 m</span><b>0.55</b></div><small>Soil / amber / vegetation · {shortDate(data.scene.datetime)}</small></div>}

    {error && <div className="error-banner" role="alert"><TriangleAlert size={17}/><span>{error}</span><button className="icon-button" onClick={()=>setError(null)} aria-label="Dismiss message"><X size={15}/></button></div>}
    <footer className="telemetry-dock">
      <div className="vehicle-status"><div className={`vehicle-status-icon ${flying?'active':''}`}><Radio size={20}/></div><div><b>AF-1 <span>/ SIM</span></b><small>{application?'SIMULATED APPLICATION':flying ? current?.phase?.replaceAll('_',' ').toUpperCase() : mission?.trace?.length?'LANDED':'ON PAD'}</small></div></div>
      <div className="telemetry-values"><Metric label="ELAPSED" value={time(current?.elapsed_s)} /><Metric label="DISTANCE" value={fmt((current?.distance_m||0)/1000)} unit="km"/><Metric label="BATTERY" value={fmt(current?.battery_pct ?? 100,1)} unit="%" tone={current?.battery_pct < 40?'amber':''}/><Metric label="ALT / AGL" value={current?.altitude_agl_m || '00'} unit="m"/><Metric label="SAMPLES / SIM" value={String(current?.samples||0).padStart(3,'0')}/></div>
      <div className="telemetry-position"><span>{fmt(current?.position?.[1] ?? 36.33615,6)} N</span><span>{fmt(Math.abs(current?.position?.[0] ?? -120.108177),6)} W</span><label>PLAYBACK <select aria-label="Simulation playback speed" value={speed} onChange={e=>setSpeed(Number(e.target.value))}><option value={16}>16×</option><option value={32}>32×</option><option value={64}>64×</option></select></label></div>
      <div className="mission-log"><div className="eyebrow"><span className="status-dot"/> SYSTEM LOG</div><span>{lastEvent?.at.toISOString().slice(11,19)} <b>{lastEvent?.message}</b></span></div>
      <div className="timeline-track"><div style={{width:`${progress*100}%`}}/></div>
    </footer>
  </main>;
}

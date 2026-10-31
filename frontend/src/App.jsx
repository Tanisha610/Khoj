import { useEffect, useRef, useState } from "react";
import "./App.css";

const API = import.meta.env.VITE_API_URL || "/api";
async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(Array.isArray(body.detail) ? body.detail.map((e) => e.msg).join(", ") : body.detail || "Request failed.");
  return body;
}

function Logo({ onClick }) { return <button className="logo" onClick={onClick} aria-label="OncoCare home"><span>O</span> OncoCare</button>; }
function Notice({ message, error }) { return message ? <div className={error ? "notice error" : "notice"}>{message}</div> : null; }
function Landing({ navigate }) {
  return <>
    <header className="site-header">
      <Logo onClick={() => navigate("landing")} />
      <nav>
        <button onClick={() => document.getElementById("how")?.scrollIntoView()}>How It Works</button>
        <button onClick={() => document.getElementById("technology")?.scrollIntoView()}>Biosensor Technology</button>
        <button className="text-button" onClick={() => navigate("login")}>Login</button>
        <button className="primary-button" onClick={() => navigate("register")}>Create Account</button>
      </nav>
    </header>
    <main className="landing">
      <section className="landing-hero">
        <div>
          <span className="eyebrow">RESEARCH PROTOTYPE · SOFTWARE SIMULATION · SYNTHETIC DATA ONLY</span>
          <h1>Exploring a smarter approach to breast health technology.</h1>
          <p>OncoCare demonstrates a proposed PCNA biosensor concept through an interactive virtual strip, simulated electronic reader, synthetic signal processing, and patient-specific digital records.</p>
          <button className="primary-button" onClick={() => navigate("register")}>Start Virtual Experience →</button>
          <button className="outline-button" onClick={() => document.getElementById("technology")?.scrollIntoView()}>Explore the Technology</button>
        </div>
        <div className="device-visual">
          <div className="reader-orbit"><div className="reader-core">O</div></div>
          <div className="virtual-strip">BIOSENSOR STRIP<div /></div>
          <span className="visual-label">VIRTUAL READER · VS-001</span>
        </div>
      </section>
      <LandingSignalLab />
      <section id="how" className="landing-section">
        <span className="eyebrow">PROJECT OVERVIEW</span>
        <h2>From proposed sensing chemistry to a transparent digital record.</h2>
        <div className="feature-grid">
          <article><b>01</b><h3>Disposable strip concept</h3><p>A proposed sensing layer is represented visually in software. No physical strip or biological sample is used.</p></article>
          <article><b>02</b><h3>Reusable reader concept</h3><p>The virtual reader demonstrates acquisition, basic processing, and communication with an app.</p></article>
          <article><b>03</b><h3>Patient-centered records</h3><p>Authenticated patients can complete an assessment and keep their own synthetic test history.</p></article>
        </div>
      </section>
      <section id="technology" className="landing-section lavender">
        <span className="eyebrow">PROPOSED BIOSENSOR TECHNOLOGY</span>
        <h2>A conceptual layered strip for biomarker detection.</h2>
        <p className="wide-copy biosensor-note">This proposed design is for illustration only and has not been physically or clinically validated.</p>
        <div className="biosensor-concept-grid">
          <figure className="biosensor-image-card">
            <img className="biosensor-image" src="/biosensor-strip-layers.png" alt="Exploded illustration of a proposed biosensor strip showing a protective cover, sample and reaction zone, reagent layer, electrode layer, insulating spacer, and supporting substrate." />
            <figcaption>Illustrative concept only · requires physical and clinical validation.</figcaption>
          </figure>
        </div>
        <div className="workflow-explainer"><strong>Virtual reader workflow</strong><span>Profile → virtual strip → synthetic signal → simple filtering → saved record. The generated values are arbitrary software units and are not PCNA concentrations.</span></div>
      </section>
      <section id="limits" className="landing-section">
        <span className="eyebrow">RESEARCH LIMITATIONS</span>
        <h2>An honest prototype is part of responsible innovation.</h2>
        <p className="wide-copy">This application demonstrates a proposed workflow only. It does not validate antibodies, measure interstitial fluid, establish clinical thresholds, or provide a cancer screening or diagnostic result. Physical prototyping, laboratory and clinical validation, and regulatory review remain necessary future work.</p>
      </section>
    </main>
  </>;
}

function LandingSignalLab() {
  const [scenario, setScenario] = useState("steady");
  const variation = Array.from({ length: 20 }, (_, index) => {
    if (scenario === "noisy") {
      return 0.53 + Math.sin(index * 2.4) * 0.105 + Math.cos(index * 4.1) * 0.065;
    }
    if (scenario === "drift") {
      return 0.34 + index * 0.015 + Math.sin(index * 1.3) * 0.025;
    }
    return 0.53 + Math.sin(index * 1.1) * 0.025 + Math.cos(index * 0.54) * 0.018;
  });
  const samples = variation.map((raw, index) => ({
    raw: Math.max(0.08, Math.min(0.92, raw)),
    filtered: variation.slice(Math.max(0, index - 2), index + 1)
      .reduce((sum, value) => sum + value, 0) / (Math.min(index + 1, 3)),
  }));
  const x = (index) => 44 + index * 712 / (samples.length - 1);
  const y = (value) => 184 - value * 158;
  const path = (key) => samples.map((sample, index) =>
    `${index === 0 ? "M" : "L"}${x(index)},${y(sample[key])}`
  ).join(" ");
  const choices = [
    { id: "steady", label: "Steady input" },
    { id: "noisy", label: "Noisy input" },
    { id: "drift", label: "Gradual drift" },
  ];
  const current = samples[samples.length - 1];

  return <section className="landing-signal-wrap" aria-labelledby="signal-lab-title">
    <div className="landing-signal-lab">
      <div className="signal-lab-copy">
        <span className="eyebrow">INTERACTIVE SIGNAL LAB</span>
        <h2 id="signal-lab-title">See what a simple filter changes.</h2>
        <p>Switch the synthetic input profile and compare its raw trace with a three-sample moving average.</p>
        <div className="signal-scenarios" role="group" aria-label="Choose a synthetic signal profile">
          {choices.map((choice) => <button
            key={choice.id}
            className={scenario === choice.id ? "active" : ""}
            aria-pressed={scenario === choice.id}
            onClick={() => setScenario(choice.id)}
          >{choice.label}</button>)}
        </div>
        <div className="signal-lab-readouts">
          <div><span>Last raw value</span><strong>{current.raw.toFixed(3)}</strong></div>
          <div><span>Filtered value</span><strong>{current.filtered.toFixed(3)}</strong></div>
        </div>
      </div>
      <div className="signal-lab-visual">
        <div className="signal-lab-chart-heading"><span>20-point example</span><span>ARBITRARY UNITS</span></div>
        <svg viewBox="0 0 800 220" role="img" aria-label={`Synthetic ${scenario} signal with raw and filtered traces`}>
          {[0.25, 0.5, 0.75].map((level) => <line key={level} x1="44" x2="756" y1={y(level)} y2={y(level)} className="signal-lab-gridline" />)}
          <path d={path("raw")} className="signal-lab-raw" />
          <path d={path("filtered")} className="signal-lab-filtered" />
          <circle cx={x(19)} cy={y(current.raw)} r="5" className="signal-lab-dot-raw" />
          <circle cx={x(19)} cy={y(current.filtered)} r="5" className="signal-lab-dot-filtered" />
        </svg>
        <div className="signal-lab-legend"><span><i className="raw-key" />Raw input</span><span><i className="filtered-key" />3-sample average</span></div>
        <p className="signal-lab-disclaimer">Illustrative software data only. This preview does not represent PCNA, a patient, or a real sensor.</p>
      </div>
    </div>
  </section>;
}

function Auth({ mode, navigate, onAuthenticated }) {
  const isRegister = mode === "register";
  const [form, setForm] = useState({ full_name: "", email: "", password: "", confirm_password: "", consent: false });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await request(isRegister ? "/auth/register" : "/auth/login", {
        method: "POST",
        body: JSON.stringify(isRegister ? form : { full_name: form.full_name, password: form.password }),
      });
      const loggedInPatient = await onAuthenticated();
      navigate(loggedInPatient?.role === "clinician"
        ? "clinician"
        : loggedInPatient?.hasAssessment ? "dashboard" : "assessment");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return <main className="auth-page"><Logo onClick={() => navigate("landing")} /><div className="auth-card"><span className="eyebrow">{isRegister ? "BEGIN YOUR JOURNEY" : "WELCOME BACK"}</span><h1>{isRegister ? "Create your private OncoCare space." : "Sign in to your patient space."}</h1><p>{isRegister ? "Your account stores only what this educational prototype needs." : "Use the patient name you entered during registration."}</p><Notice message={error} error /><form onSubmit={submit}>{isRegister && <label>Full name<input required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></label>}{isRegister && <label>Email address<input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>}{!isRegister && <label>Patient name<input required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></label>}<label>Password<input required minLength="8" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>{isRegister && <><label>Confirm password<input required minLength="8" type="password" value={form.confirm_password} onChange={(e) => setForm({ ...form, confirm_password: e.target.value })} /></label><label className="consent"><input type="checkbox" checked={form.consent} onChange={(e) => setForm({ ...form, consent: e.target.checked })} required /> I understand this is an educational research prototype using synthetic data, not a medical device.</label></>}<button className="primary-button full-button" disabled={loading}>{loading ? "Please wait…" : isRegister ? "Create account" : "Log in"}</button></form><button className="link-button" onClick={() => navigate(isRegister ? "login" : "register")}>{isRegister ? "Already have an account? Log in" : "Need an account? Create one"}</button></div></main>;
}

function Assessment({ assessment, onSaved, showError }) {
  const [form, setForm] = useState(assessment || { prefer_not_to_answer: false });
  const [saving, setSaving] = useState(false);
  const bmi = form.weight_kg && form.height_cm
    ? (Number(form.weight_kg) / ((Number(form.height_cm) / 100) ** 2)).toFixed(2)
    : null;

  function update(key, value) {
    setForm({ ...form, [key]: value });
  }

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    try {
      const result = await request("/patients/me/assessment", {
        method: "PUT",
        body: JSON.stringify({
          ...form,
          weight_kg: form.weight_kg ? Number(form.weight_kg) : null,
          height_cm: form.height_cm ? Number(form.height_cm) : null,
          relative_diagnosis_age: form.relative_diagnosis_age ? Number(form.relative_diagnosis_age) : null,
        }),
      });
      onSaved(result.assessment);
    } catch (error) {
      showError(error.message);
    } finally {
      setSaving(false);
    }
  }

  function answerSelect(label, key) {
    return <label>{label}<select value={form[key] || ""} onChange={(e) => update(key, e.target.value || null)}>
      <option value="">Choose an answer</option>
      <option value="yes">Yes</option>
      <option value="no">No</option>
      <option value="not_sure">Not sure</option>
      <option value="prefer_not_to_say">Prefer not to say</option>
    </select></label>;
  }

  return <section className="card assessment">
    <div className="section-heading">
      <span className="eyebrow">PATIENT ASSESSMENT</span>
      <h2>Tell us only what you are comfortable sharing.</h2>
      <p>This information is stored privately and is not used to diagnose or generate a cancer-risk score.</p>
    </div>
    <form onSubmit={save}>
      <fieldset>
        <legend>Section A · Patient information</legend>
        <div className="form-grid">
          <label>Weight (kg)<input type="number" min="1" max="500" value={form.weight_kg || ""} onChange={(e) => update("weight_kg", e.target.value)} /></label>
          <label>Height (cm)<input type="number" min="1" max="300" value={form.height_cm || ""} onChange={(e) => update("height_cm", e.target.value)} /></label>
        </div>
        {bmi && <div className="bmi-box"><strong>{bmi}</strong><span>BMI · general health context only</span></div>}
      </fieldset>
      <fieldset>
        <legend>Section B · Family history</legend>
        {answerSelect("Family history of breast cancer", "breast_cancer_family_history")}
        {form.breast_cancer_family_history === "yes" && <div className="form-grid">
          <label>Relationship<select value={form.affected_relative || ""} onChange={(e) => update("affected_relative", e.target.value)}>
            <option value="">Choose</option>
            {["Mother", "Sister", "Daughter", "Father", "Brother", "Other relative", "Prefer not to say"].map((x) => <option key={x}>{x}</option>)}
          </select></label>
          <label>Approximate age at diagnosis<input type="number" min="0" max="120" value={form.relative_diagnosis_age || ""} onChange={(e) => update("relative_diagnosis_age", e.target.value)} /></label>
        </div>}
        {answerSelect("Family history of ovarian cancer", "ovarian_cancer_family_history")}
      </fieldset>
      <fieldset>
        <legend>Section C · Personal health context</legend>
        <p className="field-note">Optional and private. You can choose “Prefer not to say.” These answers do not provide medical advice or affect a diagnostic result.</p>
        {answerSelect("Are you currently pregnant?", "currently_pregnant")}
        {answerSelect("Are you currently breastfeeding?", "currently_breastfeeding")}
        <label>Previous breast-related diagnosis<select value={form.prior_breast_diagnosis || ""} onChange={(e) => update("prior_breast_diagnosis", e.target.value)}>
          <option value="">Prefer not to answer</option><option value="yes">Yes</option><option value="no">No</option>
        </select></label>
        <label>Previous breast examination or investigation<select value={form.prior_breast_investigation || ""} onChange={(e) => update("prior_breast_investigation", e.target.value)}>
          <option value="">Prefer not to answer</option><option value="yes">Yes</option><option value="no">No</option>
        </select></label>
        <label>Additional relevant history<textarea maxLength="1000" value={form.additional_history || ""} onChange={(e) => update("additional_history", e.target.value)} placeholder="Optional context only" /></label>
        <label className="consent"><input type="checkbox" checked={form.prefer_not_to_answer || false} onChange={(e) => update("prefer_not_to_answer", e.target.checked)} /> Prefer not to answer optional health questions</label>
      </fieldset>
      <button className="primary-button" disabled={saving}>{saving ? "Saving…" : "Save assessment"}</button>
    </form>
  </section>;
}

function Dashboard({ patient, assessment, readings, navigate }) { const latest = readings[0]; return <><section className="dashboard-welcome card"><div><span className="eyebrow">WELCOME, {patient.full_name.split(" ")[0].toUpperCase()}</span><h1>Explore your health technology space.</h1><p>Your records are private to your account. Every reading here is synthetic software output.</p><button className="primary-button" onClick={() => navigate("test")}>Start Virtual Test →</button></div><div className="mini-reader">◉</div></section><div className="stats-grid"><div className="stat-card"><span>Patient ID</span><strong>{patient.patient_id}</strong><small>Private account</small></div><div className="stat-card"><span>Virtual tests</span><strong>{readings.length}</strong><small>Saved synthetic records</small></div><div className="stat-card"><span>Assessment</span><strong>{assessment ? "Complete" : "Not started"}</strong><small>Optional patient context</small></div></div><section className="two-column"><div className="card"><div className="card-heading"><h2>Latest synthetic reading</h2><button className="link-button" onClick={() => navigate("history")}>View all tests →</button></div>{latest ? <><div className="latest-value">{Number(latest.filtered_signal).toFixed(3)}<span>filtered synthetic units</span></div><p>{latest.test_id} · {new Date(latest.timestamp).toLocaleString()}</p></> : <div className="empty-state"><h3>No virtual tests yet</h3><p>Start a simulation to create your first private record.</p></div>}</div><div className="card"><span className="eyebrow">SAFETY NOTICE</span><h2>Complementary, never diagnostic.</h2><p>OncoCare does not measure real PCNA, diagnose cancer, or replace professional care.</p><button className="outline-button" onClick={() => navigate("assessment")}>{assessment ? "Edit assessment" : "Complete assessment"}</button></div></section></>; }

function VirtualTest({ navigate, onComplete, showError }) {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [sampleFlow, setSampleFlow] = useState(false);
  const [sampleProgress, setSampleProgress] = useState(0);
  const [completedTest, setCompletedTest] = useState(null);
  const [processedSamples, setProcessedSamples] = useState([]);
  const testInProgress = useRef(false);

  async function activate() {
    setLoading(true);
    try {
      setStep(4);
      await new Promise((resolve) => window.setTimeout(resolve, 650));
      setStep(5);
      await new Promise((resolve) => window.setTimeout(resolve, 650));
      setStep(6);
      const result = await request("/simulate", { method: "POST", body: JSON.stringify({ scenario: "random" }) });
      for (let index = 1; index <= result.test.samples.length; index += 1) {
        setProcessedSamples(result.test.samples.slice(0, index));
        await new Promise((resolve) => window.setTimeout(resolve, 70));
      }
      setCompletedTest(result.test);
      onComplete(result.test);
      setStep(7);
    } catch (error) {
      showError(error.message);
      setStep(3);
      setSampleFlow(false);
    } finally {
      setLoading(false);
    }
  }

  async function startSampleFlow() {
    if (testInProgress.current) return;
    testInProgress.current = true;
    setSampleProgress(0);
    setProcessedSamples([]);
    setSampleFlow(true);
    for (let progress = 5; progress <= 100; progress += 5) {
      await new Promise((resolve) => window.setTimeout(resolve, 45));
      setSampleProgress(progress);
    }
    setSampleFlow(false);
    await activate();
    testInProgress.current = false;
  }

  const steps = ["Introduction", "Prepare", "Sample flow", "Hypothetical recognition", "Electrochemical model", "Signal processing", "Review"];
  const titles = [
    "Understand the simulation",
    "Prepare the virtual strip",
    "Watch the virtual sample workflow",
    "Simulating hypothetical recognition…",
    "Modeling a synthetic electrical response…",
    "Processing 20 synthetic signal samples…",
    "Your simulated test report is ready",
  ];
  const lead = step <= 3
    ? "This is a software-only conceptual workflow. No biological sample is collected, tested, or measured."
    : step < 7
      ? "The display is an animation of hypothetical model stages. Generated values are synthetic assumptions, not measured PCNA."
      : "This report contains synthetic software output only. It is not a patient measurement or clinical result.";

  return <section className="card workflow">
    <span className="eyebrow">GUIDED VIRTUAL TEST · STEP {step} OF 7</span>
    <h1>{titles[step - 1]}</h1>
    <p className="lead">{lead}</p>
    <div className="steps">{steps.map((name, index) => <span className={step >= index + 1 ? "active" : ""} key={name}>{index + 1}. {name}</span>)}</div>
    <div className={`strip-stage ${step === 3 ? "sample-animation-stage" : ""} ${step >= 4 && step <= 6 ? "sensor-processing-stage" : ""}`}>
      <div className="virtual-strip">BIO<span>SENSOR</span><div /></div>
      {step === 3 && <div className="sample-path" aria-label="Conceptual sample animation"><span className="sample-drop" style={{ "--sample-progress": `${sampleProgress}%` }}>●</span><small>CONCEPTUAL SAMPLE PATH</small></div>}
      {step >= 4 && step <= 6 && <div className={`sensor-stage-signal stage-${step}`} aria-label={titles[step - 1]}><span /><span /><span /></div>}
      <div className="reader-outline">REUSABLE<br />READER<br /><b>VS-001</b></div>
    </div>
    {(step === 3 || (step >= 4 && step <= 6)) && <div className="simulation-boundary"><strong>Visual demonstration only</strong><span>No actual PCNA recognition, biochemical reaction, or patient measurement occurs. PCNA input values are selected from a synthetic dataset.</span></div>}
    {step === 6 && processedSamples.length > 0 && <SignalChart samples={processedSamples} live />}
    {step === 7 && completedTest && <><div className="result-preview"><strong>{completedTest.signal_quality} · {completedTest.sample_count} samples saved</strong><span>Test {completedTest.test_id} is available in this account. Signal quality describes technical checks only—not cancer detection or risk.</span></div><div className="detail-grid"><div><span>Hypothetical PCNA input</span><strong>{Number(completedTest.hypothetical_pcna_ng_ml).toFixed(2)}</strong><small>synthetic ng/mL</small></div><div><span>Raw / filtered current</span><strong>{Number(completedTest.simulated_current_uA).toFixed(4)} / {Number(completedTest.filtered_current_uA).toFixed(4)}</strong><small>microamps</small></div><div><span>Filtered ADC</span><strong>{completedTest.filtered_adc_counts}</strong><small>12-bit counts</small></div></div></>}
    <div className="workflow-actions">
      {step < 3 && <button className="outline-button" onClick={() => setStep(step + 1)}>Continue →</button>}
      {step === 3 && <button className="primary-button" onClick={startSampleFlow} disabled={loading || sampleFlow}>{sampleFlow ? "Sample moving…" : "Start virtual sample flow →"}</button>}
      {step >= 4 && step <= 6 && <button className="primary-button" disabled>{loading ? "Processing…" : "Preparing…"}</button>}
      {step === 7 && <><button className="primary-button" onClick={() => navigate("detail", completedTest)}>View Full Report</button><button className="outline-button" onClick={() => { setStep(1); setSampleProgress(0); setSampleFlow(false); setCompletedTest(null); }}>Run Another Simulation</button></>}
    </div>
  </section>;
}

function SignalChart({ samples, live = false, deviceSignal = false }) {
  const width = 760;
  const height = 220;
  const inset = 24;
  const rawKey = deviceSignal ? "raw_signal" : "raw_adc_counts";
  const filteredKey = deviceSignal ? "filtered_signal" : "filtered_adc_counts";
  const max = Math.max(1, ...samples.flatMap((sample) => [sample[rawKey], sample[filteredKey]]));
  const path = (key) => samples.map((sample, index) => {
    const x = inset + index * (width - inset * 2) / Math.max(1, samples.length - 1);
    const y = height - inset - Number(sample[key]) / max * (height - inset * 2);
    return `${index === 0 ? "M" : "L"}${x},${y}`;
  }).join(" ");

  if (!samples.length) return null;
  return <section className="signal-chart card">
    <div className="card-heading"><h2>{live ? "Live synthetic signal playback" : "Raw versus filtered signal"}</h2><span className="muted-label">{live ? `${samples.length} of 20 samples · ` : ""}{deviceSignal ? "unitless synthetic signal" : "12-bit ADC counts"} · technical signal only</span></div>
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={deviceSignal ? "Chart of raw and filtered unitless device signals across the test samples" : "Chart of raw and filtered ADC counts across the test samples"}>
      {[0, 1, 2, 3].map((line) => <line key={line} x1={inset} x2={width - inset} y1={inset + line * (height - inset * 2) / 3} y2={inset + line * (height - inset * 2) / 3} className="chart-gridline" />)}
      <path d={path(rawKey)} className="chart-raw" />
      <path d={path(filteredKey)} className="chart-filtered" />
    </svg>
    <div className="chart-legend"><span className="chart-legend-raw">{deviceSignal ? "Raw signal" : "Raw ADC"}</span><span className="chart-legend-filtered">{deviceSignal ? "Filtered signal" : "Filtered ADC"}</span></div>
  </section>;
}

function History({ readings, navigate }) {
  return <section className="card">
    <div className="section-heading"><span className="eyebrow">PRIVATE TO YOUR ACCOUNT</span><h1>Test history</h1><p>All values are synthetic software output. Signal quality is technical validity only.</p></div>
    {readings.length === 0 ? <div className="empty-state"><h3>No tests saved yet</h3><button className="primary-button" onClick={() => navigate("test")}>Start a virtual test</button></div> : <div className="history-table-wrap"><table className="history-table"><thead><tr><th>Test / date</th><th>Hypothetical PCNA input</th><th>Samples</th><th>Technical signal quality</th></tr></thead><tbody>{readings.map((item) => <tr key={item.test_id || item.record_id}><td><button className="link-button" onClick={() => navigate("detail", item)}>{item.test_id}</button><small>{new Date(item.timestamp).toLocaleString()}</small></td><td>{item.hypothetical_pcna_ng_ml != null ? `${Number(item.hypothetical_pcna_ng_ml).toFixed(2)} ng/mL · synthetic` : "Legacy simulated signal"}</td><td>{item.sample_count || item.sample_number || "—"}</td><td><span className={`status-pill ${item.signal_quality === "INVALID" ? "status-invalid" : ""}`}>{item.signal_quality || "SIMULATED"}</span></td></tr>)}</tbody></table></div>}
  </section>;
}

function Detail({ reading, navigate }) {
  const [test, setTest] = useState(null);
  const [samples, setSamples] = useState([]);
  const [loadedTestId, setLoadedTestId] = useState(null);
  const [error, setError] = useState("");
  const loading = Boolean(reading?.test_id && loadedTestId !== reading.test_id);
  const isDeviceSignal = test?.test_type === "device_signal";

  useEffect(() => {
    let active = true;
    if (!reading?.test_id) return () => { active = false; };
    Promise.all([request(`/tests/${encodeURIComponent(reading.test_id)}`), request(`/tests/${encodeURIComponent(reading.test_id)}/readings`)])
      .then(([testResult, readingsResult]) => {
        if (!active) return;
        setTest(testResult.test);
        setSamples(readingsResult.readings || []);
        setError("");
      })
      .catch((loadError) => {
        if (active) setError(loadError.message);
      })
      .finally(() => { if (active) setLoadedTestId(reading.test_id); });
    return () => { active = false; };
  }, [reading?.test_id]);

  async function downloadReport() {
    try {
      const response = await fetch(`${API}/tests/${encodeURIComponent(reading.test_id)}/report`, { credentials: "include" });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || "Could not download the report.");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `onco-care-${reading.test_id}.pdf`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (downloadError) {
      setError(downloadError.message);
    }
  }

  if (!reading) return <History readings={[]} navigate={navigate} />;
  const report = test || reading;
  const isFullReport = Boolean(test && !isDeviceSignal);
  return <><section className="card">
    <div className="card-heading"><button className="link-button" onClick={() => navigate("history")}>← Back to history</button>{isFullReport && <button className="primary-button" onClick={downloadReport}>Download PDF report</button>}</div>
    <div className="section-heading"><span className="eyebrow">SIMULATED TEST RECORD</span><h1>{report.test_id}</h1><p>{new Date(report.timestamp).toLocaleString()} · {report.device_id || "VS-001"}</p></div>
    {loading && <p className="muted-label">Loading the saved test report…</p>}
    {error && <Notice message={error} error />}
    {isDeviceSignal ? <div className="detail-grid">
      <div><span>Raw device signal</span><strong>{Number(report.raw_signal || 0).toFixed(4)}</strong><small>unitless synthetic signal</small></div>
      <div><span>Filtered device signal</span><strong>{Number(report.filtered_signal || 0).toFixed(4)}</strong><small>unitless moving average</small></div>
    </div> : <div className="detail-grid">
      <div><span>Hypothetical PCNA input</span><strong>{report.hypothetical_pcna_ng_ml != null ? Number(report.hypothetical_pcna_ng_ml).toFixed(3) : "—"}</strong><small>synthetic ng/mL input only</small></div>
      <div><span>Raw simulated current</span><strong>{report.simulated_current_uA != null ? Number(report.simulated_current_uA).toFixed(4) : Number(report.filtered_signal || 0).toFixed(4)}</strong><small>microamps · modeled</small></div>
      <div><span>Filtered current</span><strong>{report.filtered_current_uA != null ? Number(report.filtered_current_uA).toFixed(4) : "—"}</strong><small>microamps · moving average</small></div>
      <div><span>Simulated voltage</span><strong>{report.simulated_voltage_V != null ? Number(report.simulated_voltage_V).toFixed(4) : "—"}</strong><small>volts · modeled</small></div>
      <div><span>Raw ADC count</span><strong>{report.raw_adc_counts ?? "—"}</strong><small>12-bit ADC</small></div>
      <div><span>Filtered ADC count</span><strong>{report.filtered_adc_counts ?? "—"}</strong><small>12-bit ADC</small></div>
      <div><span>Signal quality</span><strong>{report.signal_quality}</strong><small>technical validity only</small></div>
    </div>}
    <dl className="detail-list"><div><dt>Patient ID</dt><dd>{report.patient_id || "Current account"}</dd></div><div><dt>Device ID</dt><dd>{report.device_id || "VS-001"}</dd></div><div><dt>Samples collected</dt><dd>{report.sample_count || report.sample_number || "—"}</dd></div><div><dt>Test status</dt><dd>{report.test_status || "COMPLETED"}</dd></div><div><dt>Simulation mode</dt><dd>SIMULATED</dd></div><div><dt>Technical quality check</dt><dd>{report.quality_explanation || "Legacy synthetic signal record."}</dd></div></dl>
    <div className="notice">SIMULATION ONLY: this hypothetical dataset input is not a patient's measured PCNA concentration. The system does not detect actual PCNA, diagnose cancer, or provide a clinical result.</div>
  </section>{samples.length > 0 && <><SignalChart samples={samples} deviceSignal={isDeviceSignal} /><section className="card"><div className="card-heading"><h2>Sample readings</h2><span className="muted-label">{samples.length} stored samples</span></div><div className="sample-table-wrap"><table className="sample-table"><thead>{isDeviceSignal ? <tr><th>#</th><th>Raw signal</th><th>Filtered signal</th><th>Quality</th></tr> : <tr><th>#</th><th>Raw current (uA)</th><th>Filtered current (uA)</th><th>Raw voltage (V)</th><th>Raw ADC</th><th>Filtered ADC</th><th>Quality</th></tr>}</thead><tbody>{samples.map((sample) => isDeviceSignal
      ? <tr key={sample.sample_number}><td>{sample.sample_number}</td><td>{Number(sample.raw_signal).toFixed(4)}</td><td>{Number(sample.filtered_signal).toFixed(4)}</td><td>{sample.signal_quality}</td></tr>
      : <tr key={sample.sample_number}><td>{sample.sample_number}</td><td>{Number(sample.simulated_current_uA).toFixed(5)}</td><td>{Number(sample.filtered_current_uA).toFixed(5)}</td><td>{Number(sample.simulated_voltage_V).toFixed(5)}</td><td>{sample.raw_adc_counts}</td><td>{sample.filtered_adc_counts}</td><td>{sample.signal_quality}</td></tr>)}</tbody></table></div></section></>}</>;
}

export default function App() {
  const [view, setView] = useState("landing");
  const [patient, setPatient] = useState(null);
  const [assessment, setAssessment] = useState(null);
  const [readings, setReadings] = useState([]);
  const [selected, setSelected] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    request("/auth/me").then(async (result) => {
      const [assessmentResult, readingsResult] = await Promise.all([
        request("/patients/me/assessment"),
        request("/patients/me/readings"),
      ]);
      setAssessment(assessmentResult.assessment);
      setReadings(readingsResult.readings || []);
      setPatient(result.patient);
      setView(result.patient.role === "clinician"
        ? "clinician"
        : assessmentResult.assessment ? "dashboard" : "assessment");
    }).catch(() => {});
  }, []);
  function navigate(next, data = null) {
    setMessage("");
    setError("");
    if (patient?.role === "patient" && !assessment && next !== "assessment") {
      next = "assessment";
      setMessage("Complete or decline the assessment to continue.");
    }
    if (data) setSelected(data);
    setView(next);
  }
  async function refresh() {
    const me = await request("/auth/me");
    setPatient(me.patient);
    let savedAssessment = null;
    try {
      const [assessmentResult, readingsResult] = await Promise.all([
        request("/patients/me/assessment"),
        request("/patients/me/readings"),
      ]);
      savedAssessment = assessmentResult.assessment;
      setAssessment(savedAssessment);
      setReadings(readingsResult.readings || []);
    } catch {
      setAssessment(null);
      setReadings([]);
    }
    setView(me.patient.role === "clinician" ? "clinician" : savedAssessment ? "dashboard" : "assessment");
    return { ...me.patient, hasAssessment: Boolean(savedAssessment) };
  }
  async function logout() {
    await request("/auth/logout", { method: "POST" }).catch(() => {});
    setPatient(null);
    setAssessment(null);
    setReadings([]);
    navigate("landing");
  }
  function showError(text) { setError(text); setMessage(""); }
  if (!patient && view === "login") return <Auth mode="login" navigate={navigate} onAuthenticated={refresh} />;
  if (!patient && view === "register") return <Auth mode="register" navigate={navigate} onAuthenticated={refresh} />;
  if (!patient) return <Landing navigate={navigate} />;
  return <div className="app-shell"><aside><Logo onClick={() => navigate(patient.role === "clinician" ? "clinician" : "dashboard")} /><nav>{patient.role === "clinician" ? <button onClick={() => navigate("clinician")}>⌂ Research review</button> : <><button onClick={() => navigate("dashboard")}>⌂ Overview</button><button onClick={() => navigate("assessment")}>▦ Assessment</button><button onClick={() => navigate("test")}>＋ Virtual test</button><button onClick={() => navigate("history")}>◷ Test history</button><button onClick={() => navigate("profile")}>◯ My profile</button></>}</nav><button className="logout" onClick={logout}>Log out</button></aside><main className="portal"><header className="portal-header"><div><span className="eyebrow">{patient.role === "clinician" ? "ONCOCARE CLINICIAN SPACE" : "YOUR ONCOCARE SPACE"}</span><h2>{view === "dashboard" ? "Overview" : view === "clinician" ? "Research review" : view === "assessment" ? "Patient assessment" : view === "test" ? "Virtual test" : view === "history" ? "Test history" : view === "detail" ? "Test details" : "My profile"}</h2></div><div className="patient-chip">{patient.full_name}<small>{patient.patient_id}</small></div></header><Notice message={error} error /><Notice message={message} />{view === "clinician" && <ClinicianDashboard />}{view === "dashboard" && <Dashboard patient={patient} assessment={assessment} readings={readings} navigate={navigate} />}{view === "assessment" && <><Assessment assessment={assessment} onSaved={(value) => { setAssessment(value); setMessage("Assessment saved to your profile."); if (!assessment) setView("dashboard"); }} showError={showError} />{!assessment && <p className="assessment-onboarding-note">Please complete this assessment or select “Prefer not to answer” before continuing. Your answers will be saved to your private profile.</p>}</>}{view === "test" && <VirtualTest navigate={navigate} onComplete={(reading) => { setReadings((items) => [reading, ...items]); setSelected(reading); setMessage("Synthetic reading saved to your private history."); }} showError={showError} />}{view === "history" && <History readings={readings} navigate={navigate} />}{view === "detail" && <Detail reading={selected} navigate={navigate} />}{view === "profile" && <Profile patient={patient} assessment={assessment} onSaved={(value) => { setPatient(value); setMessage("Profile updated."); }} showError={showError} />}</main></div>;
}

function ClinicianDashboard() {
  const [patients, setPatients] = useState([]);
  const [selected, setSelected] = useState(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    request("/clinician/patients").then((result) => setPatients(result.patients || [])).catch((loadError) => setError(loadError.message));
  }, []);
  async function review(patientId) {
    try {
      setSelected(await request(`/clinician/patients/${patientId}/review`));
      setError("");
    } catch (loadError) {
      setError(loadError.message);
    }
  }
  async function saveNote(event) {
    event.preventDefault();
    if (!selected || !note.trim()) return;
    try {
      await request(`/clinician/patients/${selected.patient.patient_id}/notes`, { method: "POST", body: JSON.stringify({ note }) });
      setSelected({ ...selected, notes: [{ note, created_at: new Date().toISOString() }, ...selected.notes] });
      setNote("");
    } catch (saveError) {
      setError(saveError.message);
    }
  }
  return <section className="clinician-dashboard">
    <div className="doctor-hero card"><span className="eyebrow">CLINICIAN RESEARCH REVIEW</span><h1>Review synthetic patient data.</h1><p>Inspect signal quality, test history, and patient-provided context. This workspace does not diagnose cancer or generate clinical risk results.</p></div>
    <Notice message={error} error />
    <div className="clinician-grid">
      <section className="card"><div className="card-heading"><h2>Patient records</h2><span className="muted-label">{patients.length} patients</span></div>{patients.length ? <div className="patient-list">{patients.map((item) => <button className="patient-row" key={item.patient_id} onClick={() => review(item.patient_id)}><span><strong>{item.full_name}</strong><small>{item.patient_id}</small></span><span><strong>{item.test_count}</strong><small>virtual tests</small></span></button>)}</div> : <div className="empty-state">No patient records available.</div>}</section>
      <section className="card review-panel">{selected ? <><span className="eyebrow">SELECTED PATIENT</span><h2>{selected.patient.full_name}</h2><p className="muted-label">{selected.patient.patient_id}</p><div className="review-summary"><div><strong>{selected.readings.length}</strong><span>synthetic tests</span></div><div><strong>{selected.readings[0] ? selected.readings[0].signal_quality : "—"}</strong><span>latest quality</span></div></div><h3>Signal review</h3>{selected.readings.length ? <div className="review-readings">{selected.readings.slice(0, 5).map((reading) => <div key={reading.record_id}><strong>{reading.test_id}</strong><span>{Number(reading.filtered_signal).toFixed(3)} filtered units</span><small>{new Date(reading.timestamp).toLocaleString()}</small></div>)}</div> : <p className="muted-label">No synthetic tests recorded.</p>}<h3>Research interpretation note</h3><form onSubmit={saveNote}><textarea value={note} onChange={(event) => setNote(event.target.value)} maxLength="2000" placeholder="Describe signal quality or software behavior. Do not enter a diagnosis." /><button className="primary-button">Save review note</button></form>{selected.notes.length > 0 && <div className="saved-notes">{selected.notes.map((item, index) => <p key={`${item.created_at}-${index}`}>{item.note}<small>{new Date(item.created_at).toLocaleString()}</small></p>)}</div>}</> : <div className="empty-state"><h3>Select a patient record</h3><p>Choose a patient to review their synthetic readings and assessment context.</p></div>}</section>
    </div>
  </section>;
}

function Profile({ patient, assessment, onSaved, showError }) {
  const [form, setForm] = useState(patient || {});
  const [saving, setSaving] = useState(false);
  async function save(e) {
    e.preventDefault();
    setSaving(true);
    try {
      const result = await request("/patients/me", {
        method: "PATCH",
        body: JSON.stringify({ ...form, date_of_birth: form.date_of_birth || null }),
      });
      onSaved(result.patient);
    } catch (error) {
      showError(error.message);
    } finally {
      setSaving(false);
    }
  }
  return <section className="card profile profile-content">
    <div className="section-heading">
      <span className="eyebrow">MY PROFILE</span>
      <h1>Your personal details</h1>
      <p>Review and update the information connected to your private OncoCare account.</p>
    </div>
    <div className="profile-id"><span>Patient ID</span><strong>{form.patient_id || "Loading…"}</strong></div>
    <form onSubmit={save}>
      <label>Full name<input required value={form.full_name || ""} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></label>
      <label>Email address<input value={form.email || ""} disabled /></label>
      <div className="form-grid">
        <label>Date of birth<input type="date" value={form.date_of_birth || ""} onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })} /></label>
        <label>Sex (optional)<input value={form.sex || ""} onChange={(e) => setForm({ ...form, sex: e.target.value })} /></label>
      </div>
      <label>Phone (optional)<input value={form.phone || ""} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></label>
      <button className="primary-button" disabled={saving}>{saving ? "Saving…" : "Save profile"}</button>
    </form>
    <AssessmentProfile assessment={assessment} />
  </section>;
}

function AssessmentProfile({ assessment }) {
  const displayAnswer = (value) => ({
    yes: "Yes",
    no: "No",
    not_sure: "Not sure",
    prefer_not_to_say: "Prefer not to say",
  }[value] || value);
  const fields = [
    ["Weight", assessment?.weight_kg ? `${assessment.weight_kg} kg` : null],
    ["Height", assessment?.height_cm ? `${assessment.height_cm} cm` : null],
    ["BMI", assessment?.bmi],
    ["Breast cancer family history", assessment?.breast_cancer_family_history],
    ["Affected relative", assessment?.affected_relative],
    ["Relative's age at diagnosis", assessment?.relative_diagnosis_age],
    ["Ovarian cancer family history", assessment?.ovarian_cancer_family_history],
    ["Currently pregnant", displayAnswer(assessment?.currently_pregnant)],
    ["Currently breastfeeding", displayAnswer(assessment?.currently_breastfeeding)],
    ["Previous breast-related diagnosis", assessment?.prior_breast_diagnosis],
    ["Previous breast examination", assessment?.prior_breast_investigation],
    ["Additional history", assessment?.additional_history],
    ["Optional questions declined", assessment?.prefer_not_to_answer ? "Yes" : assessment ? "No" : null],
  ];

  return <section className="profile-assessment">
    <div className="section-heading">
      <span className="eyebrow">SAVED HEALTH INFORMATION</span>
      <h2>Patient assessment</h2>
      <p>Your assessment is linked to your private account and can be updated from the Assessment tab.</p>
    </div>
    {assessment
      ? <dl className="detail-list">{fields.filter(([, value]) => value !== null && value !== undefined && value !== "").map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
      : <p>No assessment has been saved yet.</p>}
  </section>;
}

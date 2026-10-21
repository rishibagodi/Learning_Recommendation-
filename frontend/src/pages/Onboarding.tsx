import { useEffect, useState } from 'react';
import { api, type Domain, type Format, type Level } from '../api';

const LEVELS: { id: Level; label: string; hint: string }[] = [
  { id: 'beginner', label: 'Beginner', hint: 'New to this field' },
  { id: 'intermediate', label: 'Intermediate', hint: 'Know the basics' },
  { id: 'advanced', label: 'Advanced', hint: 'Want to go deeper' },
];
const FORMATS: { id: Format; label: string; hint: string }[] = [
  { id: 'video', label: 'Videos', hint: 'Watch tutorials' },
  { id: 'article', label: 'Reading', hint: 'Docs and articles' },
  { id: 'practice', label: 'Practice', hint: 'Exercises and projects' },
];

export default function Onboarding({ name, onDone }: { name: string; onDone: () => void }) {
  const [domains, setDomains] = useState<Domain[]>([]);
  const [step, setStep] = useState(1);
  const [domain, setDomain] = useState('');
  const [goal, setGoal] = useState('');
  const [level, setLevel] = useState<Level>('beginner');
  const [format, setFormat] = useState<Format>('video');
  const [hours, setHours] = useState(6);
  const [days, setDays] = useState(4);
  const [community, setCommunity] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.domains().then(setDomains).catch(e => setError(e.message)); }, []);
  const d = domains.find(x => x.id === domain);

  const submit = async () => {
    setBusy(true); setError('');
    try {
      await api.onboarding({ domain, goal, level, format, hours_per_week: hours, days_per_week: days, likes_discussion: community });
      onDone();
    } catch (e) { setError((e as Error).message); setBusy(false); }
  };

  return (
    <div className="narrow">
      <p className="eyebrow">Step {step} of 3</p>
      {step === 1 && <>
        <h1>Hi {name.split(' ')[0]}, what do you want to learn?</h1>
        <div className="choice-grid">
          {domains.map(x => (
            <button key={x.id} className={`choice ${domain === x.id ? 'on' : ''}`} onClick={() => { setDomain(x.id); setGoal(''); }}>
              <b>{x.name}</b>
              <span>{x.description}</span>
              <small className="muted">{x.topics.join(' · ')}</small>
            </button>
          ))}
        </div>
        <div className="actions"><button className="btn primary" disabled={!domain} onClick={() => setStep(2)}>Next</button></div>
      </>}

      {step === 2 && d && <>
        <h1>What's your goal in {d.name}?</h1>
        <div className="choice-list">
          {d.goals.map(g => (
            <button key={g.id} className={`choice row ${goal === g.id ? 'on' : ''}`} onClick={() => setGoal(g.id)}>
              <b>{g.name}</b>
            </button>
          ))}
        </div>
        <div className="actions">
          <button className="btn ghost" onClick={() => setStep(1)}>Back</button>
          <button className="btn primary" disabled={!goal} onClick={() => setStep(3)}>Next</button>
        </div>
      </>}

      {step === 3 && <>
        <h1>How do you like to learn?</h1>
        <h3>Your current level</h3>
        <div className="pill-row">
          {LEVELS.map(l => (
            <button key={l.id} className={`pill ${level === l.id ? 'on' : ''}`} onClick={() => setLevel(l.id)}>
              {l.label}<small>{l.hint}</small>
            </button>
          ))}
        </div>
        <h3>Preferred format</h3>
        <div className="pill-row">
          {FORMATS.map(f => (
            <button key={f.id} className={`pill ${format === f.id ? 'on' : ''}`} onClick={() => setFormat(f.id)}>
              {f.label}<small>{f.hint}</small>
            </button>
          ))}
        </div>
        <div className="sliders">
          <label><span>Hours per week: <b>{hours}</b></span>
            <input type="range" min={1} max={30} value={hours} onChange={e => setHours(+e.target.value)} />
          </label>
          <label><span>Study days per week: <b>{days}</b></span>
            <input type="range" min={1} max={7} value={days} onChange={e => setDays(+e.target.value)} />
          </label>
        </div>
        <label className="check">
          <input type="checkbox" checked={community} onChange={e => setCommunity(e.target.checked)} />
          I like learning with others (forums, study groups)
        </label>
        {error && <p className="error">{error}</p>}
        <div className="actions">
          <button className="btn ghost" onClick={() => setStep(2)}>Back</button>
          <button className="btn primary" disabled={busy} onClick={submit}>{busy ? 'Saving…' : 'Next: quick skill check'}</button>
        </div>
      </>}
    </div>
  );
}

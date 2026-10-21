import { useEffect, useState } from 'react';
import { api, type Me, type Roadmap, type Step } from '../api';

export const STATUS_LABEL: Record<Step['status'], string> = {
  locked: 'Locked', available: 'Up next', revise: 'Revise', completed: 'Completed', skipped: 'Skipped (known)',
};
const FORMAT_LABEL = { video: 'Videos', article: 'Reading', practice: 'Practice' };
const DIFF = ['', 'Beginner', 'Intermediate', 'Advanced'];

export default function Dashboard({ me, onOpen }: { me: Me; onOpen: (key: string) => void }) {
  const [rm, setRm] = useState<Roadmap | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { api.roadmap().then(setRm).catch(e => setError(e.message)); }, []);

  const p = me.profile!;
  if (error) return <p className="error">{error}</p>;
  if (!rm) return <p className="muted">Loading your roadmap…</p>;
  const next = rm.steps.find(s => s.status === 'available' || s.status === 'revise');

  return (
    <div className="dash">
      <section className="dash-head">
        <div>
          <p className="eyebrow">{rm.domain}</p>
          <h1>{rm.goal}</h1>
          {next
            ? <button className="btn primary" onClick={() => onOpen(next.topic_key)}>Continue: {next.name}</button>
            : <p className="good-text">All steps done. Goal reached!</p>}
        </div>
        <div className="stats">
          <div className="stat"><b>{rm.progress_pct}%</b><span>complete</span></div>
          <div className="stat"><b>{rm.remaining_weeks}</b><span>weeks left at {p.hours_per_week} h/week</span></div>
          <div className="stat"><b>{rm.steps.filter(s => s.status === 'skipped').length}</b><span>topics skipped</span></div>
        </div>
        <div className="progress"><div style={{ width: `${rm.progress_pct}%` }} /></div>
      </section>

      <div className="dash-grid">
        <ol className="roadmap">
          {rm.steps.map(s => {
            const openable = s.status !== 'locked';
            return (
              <li key={s.topic_key} className={`rm-step ${s.status}`}>
                <span className="rm-dot">{s.status === 'completed' || s.status === 'skipped' ? '✓' : s.position}</span>
                <button className="rm-card" disabled={!openable} onClick={() => onOpen(s.topic_key)}>
                  <div className="rm-title">
                    <b>{s.name}</b>
                    <span className={`tag ${s.status}`}>{STATUS_LABEL[s.status]}</span>
                  </div>
                  <div className="rm-meta muted">
                    {DIFF[s.difficulty]} · ~{s.hours} h ({s.weeks} wk)
                    {s.skill_score && <> · skill check {s.skill_score}</>}
                    {s.step_score && <> · last check {s.step_score}</>}
                  </div>
                  {s.status === 'locked' && <div className="rm-meta muted">Unlocks after {s.prereqs.join(', ')}</div>}
                </button>
              </li>
            );
          })}
        </ol>

        <aside className="card profile-card">
          <p className="eyebrow">Your learner profile</p>
          <h2>{p.cluster_name}</h2>
          <dl>
            <dt>Level</dt><dd className="cap">{p.level}</dd>
            <dt>Preferred format</dt><dd>{FORMAT_LABEL[p.format]}</dd>
            <dt>Study time</dt><dd>{p.hours_per_week} h over {p.days_per_week} days a week</dd>
          </dl>
          <p className="muted small">
            {p.cluster_id !== null
              ? <>Assigned by {p.cluster_source} ({me.model.clusters} clusters, silhouette {me.model.silhouette}).</>
              : <>Assigned by a rule-based fallback. Train the K-Means model on OULAD to use real learner data.</>}
            {' '}Your format and level steer which resources are ranked first.
          </p>
        </aside>
      </div>
    </div>
  );
}

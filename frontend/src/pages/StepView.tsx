import { useCallback, useEffect, useState } from 'react';
import { api, type Question, type QuizResult, type Resource, type StepDetail } from '../api';
import { STATUS_LABEL } from './Dashboard';
import QuizForm from './QuizForm';

const KIND = { video: 'Video', article: 'Reading', practice: 'Practice' };
const DIFF = ['', 'Beginner', 'Intermediate', 'Advanced'];
const views = (n: number | null) => !n ? '' : n >= 1e6 ? `${(n / 1e6).toFixed(1)}M views` : n >= 1e3 ? `${Math.round(n / 1e3)}K views` : `${n} views`;

export default function StepView({ topicKey, onBack, onOpen }: { topicKey: string; onBack: () => void; onOpen: (k: string) => void }) {
  const [step, setStep] = useState<StepDetail | null>(null);
  const [error, setError] = useState('');
  const [quiz, setQuiz] = useState<Question[] | null>(null);
  const [result, setResult] = useState<QuizResult | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api.step(topicKey).then(setStep).catch(e => setError(e.message)), [topicKey]);
  useEffect(() => { load(); }, [load]);

  const toggle = async (r: Resource, done: boolean, helpful: boolean | null = r.helpful === null ? null : !!r.helpful) => {
    await api.progress(r.id, done, helpful);
    load();
  };
  const startQuiz = async () => { setResult(null); setQuiz(await api.stepQuiz(topicKey)); };
  const submitQuiz = async (a: Record<string, number>) => {
    setBusy(true);
    try { setResult(await api.submitStepQuiz(topicKey, a)); setQuiz(null); load(); } finally { setBusy(false); }
  };

  if (error) return <><button className="btn ghost sm" onClick={onBack}>← Roadmap</button><p className="error">{error}</p></>;
  if (!step) return <p className="muted">Finding the best resources for you…</p>;

  return (
    <div className="step">
      <button className="btn ghost sm" onClick={onBack}>← Roadmap</button>
      <section className="step-head">
        <p className="eyebrow">Step {step.position} · {DIFF[step.difficulty]} · ~{step.hours} h</p>
        <h1>{step.name} <span className={`tag ${step.status}`}>{STATUS_LABEL[step.status]}</span></h1>
        <p className="reason">{step.reason}</p>
        {step.warning && <p className="warning">{step.warning}</p>}
      </section>

      <h2>Recommended for you</h2>
      <div className="res-grid">
        {step.recommended.map((r, i) => (
          <article key={r.id} className={`res ${r.kind}`}>
            {r.thumbnail
              ? <a href={r.url} target="_blank" rel="noreferrer" className="thumb"><img src={r.thumbnail} alt="" loading="lazy" />{r.duration_min ? <span className="dur">{Math.round(r.duration_min)} min</span> : null}</a>
              : <a href={r.url} target="_blank" rel="noreferrer" className="thumb placeholder">{KIND[r.kind]}</a>}
            <div className="res-body">
              <div className="res-tags">
                {i === 0 && <span className="tag top">Top pick</span>}
                <span className="tag">{KIND[r.kind]}</span>
                <span className="tag">{DIFF[r.difficulty]}</span>
              </div>
              <a href={r.url} target="_blank" rel="noreferrer" className="res-title">{r.title}</a>
              {(r.channel || r.views) && <div className="muted small">{[r.channel, views(r.views)].filter(Boolean).join(' · ')}</div>}
              <p className="why"><b>Why:</b> {r.why}</p>
              <div className="res-actions">
                <button className="btn sm" onClick={() => toggle(r, true)}>✓ Mark as done</button>
                <span className="muted small" title="Ranking score relative to the top pick">{Math.round(100 * r.score / step.recommended[0].score)}% match</span>
              </div>
            </div>
          </article>
        ))}
        {step.recommended.length === 0 && <p className="muted">You've finished every resource for this topic. Take the check below.</p>}
      </div>

      {step.completed.length > 0 && (
        <details className="done-list">
          <summary>Completed resources ({step.completed.length})</summary>
          <ul>
            {step.completed.map(r => (
              <li key={r.id}>
                <a href={r.url} target="_blank" rel="noreferrer">{r.title}</a>
                <span className="helpful">
                  Helpful?
                  <button className={`btn xs ${r.helpful === 1 ? 'on' : ''}`} onClick={() => toggle(r, true, true)}>Yes</button>
                  <button className={`btn xs ${r.helpful === 0 ? 'on' : ''}`} onClick={() => toggle(r, true, false)}>No</button>
                  <button className="btn xs ghost" onClick={() => toggle(r, false, null)}>Undo</button>
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}

      <section className="card check-card">
        <h2>Check your understanding</h2>
        {result && (
          <div className={`result ${result.passed ? 'pass' : 'fail'}`}>
            <b>{result.correct}/{result.total} correct. {result.passed ? 'Step completed!' : 'Not yet: your resources now focus on the basics.'}</b>
            {result.passed && result.next && <button className="btn primary sm" onClick={() => onOpen(result.next!.topic_key)}>Next: {result.next.name}</button>}
            {result.passed && !result.next && <span>That was the last step of your roadmap.</span>}
          </div>
        )}
        {quiz
          ? <QuizForm questions={quiz} submitLabel="Submit answers" busy={busy} onSubmit={submitQuiz} />
          : <button className="btn" onClick={startQuiz}>{step.status === 'completed' ? 'Retake the check' : `Take the ${step.name} check`}</button>}
      </section>
    </div>
  );
}

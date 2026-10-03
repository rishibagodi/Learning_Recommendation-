import { useEffect, useState } from 'react';
import type { Recommendation } from '../api';
import { getRecommendations } from '../api';

interface Props {
  studentId: number;
}

export default function RecommendationsPanel({ studentId }: Props) {
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [n, setN] = useState(5);

  useEffect(() => {
    setLoading(true);
    setError('');
    getRecommendations(studentId, n)
      .then((res) => setRecs(res.recommendations))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [studentId, n]);

  if (loading)
    return (
      <div className="loading">
        <div className="spinner" />
        <span>Generating recommendations…</span>
      </div>
    );

  if (error)
    return <div className="empty-state">⚠️ {error}</div>;

  return (
    <div className="card">
      <div className="card__header">
        <div className="card__title">
          <span className="icon">💡</span> Recommended Resources
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Top</span>
          <select
            value={n}
            onChange={(e) => setN(Number(e.target.value))}
            style={{
              background: 'var(--bg-tertiary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
              padding: '4px 8px',
              fontSize: '0.8rem',
              fontFamily: 'var(--font-mono)',
              cursor: 'pointer',
            }}
          >
            {[3, 5, 10, 15, 20].map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </div>
      </div>

      {recs.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state__icon">📭</div>
          No recommendations available for this student
        </div>
      ) : (
        recs.map((r, i) => (
          <div className="rec-card" key={r.id_site}>
            <div className="rec-card__header">
              <div className="rec-card__rank">{i + 1}</div>
              <div className="rec-card__title">Site #{r.id_site}</div>
              <div className="rec-card__score">Score: {r.score.toFixed(4)}</div>
            </div>
            <div className="rec-card__tags">
              <span className="tag tag--topic">{r.topic}</span>
              <span className="tag tag--format">{r.bucket.replace(/_/g, ' ')}</span>
              <span
                className="tag"
                style={{
                  background: 'var(--accent-amber-dim)',
                  color: 'var(--accent-amber)',
                }}
              >
                {r.activity_type}
              </span>
            </div>
            <div className="rec-card__explanation">{r.explanation}</div>
          </div>
        ))
      )}
    </div>
  );
}

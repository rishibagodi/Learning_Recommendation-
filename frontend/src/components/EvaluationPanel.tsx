import { useEffect, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Cell,
} from 'recharts';
import type { EvaluationResponse } from '../api';
import { getEvaluation } from '../api';

export default function EvaluationPanel() {
  const [data, setData] = useState<EvaluationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getEvaluation()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading)
    return (
      <div className="loading">
        <div className="spinner" />
        <span>Loading evaluation results…</span>
      </div>
    );

  if (error)
    return <div className="empty-state">⚠️ {error}</div>;

  if (!data) return null;

  const barData = [
    {
      metric: 'Precision@5',
      'Content-Based Only': data.content_only.precision_at_k,
      'Hybrid (KB + Clustering)': data.hybrid.precision_at_k,
    },
    {
      metric: 'Recall@5',
      'Content-Based Only': data.content_only.recall_at_k,
      'Hybrid (KB + Clustering)': data.hybrid.recall_at_k,
    },
  ];

  const improvementPrec =
    data.content_only.precision_at_k > 0
      ? ((data.hybrid.precision_at_k - data.content_only.precision_at_k) /
          data.content_only.precision_at_k) *
        100
      : 0;

  const improvementRec =
    data.content_only.recall_at_k > 0
      ? ((data.hybrid.recall_at_k - data.content_only.recall_at_k) /
          data.content_only.recall_at_k) *
        100
      : 0;

  return (
    <>
      {/* Metrics summary cards */}
      <div className="card">
        <div className="card__title" style={{ marginBottom: 16 }}>
          <span className="icon">📊</span> Ablation Study: Content-Based Only vs. Hybrid
        </div>

        <div className="grid-2" style={{ marginBottom: 20 }}>
          {/* Hybrid column */}
          <div style={{ background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-md)', padding: 20 }}>
            <h4 style={{ fontSize: '0.82rem', color: 'var(--accent-blue)', marginBottom: 12 }}>
              🔷 Hybrid (Content-Based + Clustering)
            </h4>
            <div className="grid-2">
              <div className="eval-metric">
                <div className="eval-metric__value" style={{ color: 'var(--accent-blue)' }}>
                  {(data.hybrid.precision_at_k * 100).toFixed(2)}%
                </div>
                <div className="eval-metric__label">Precision@5</div>
              </div>
              <div className="eval-metric">
                <div className="eval-metric__value" style={{ color: 'var(--accent-teal)' }}>
                  {(data.hybrid.recall_at_k * 100).toFixed(2)}%
                </div>
                <div className="eval-metric__label">Recall@5</div>
              </div>
            </div>
            <div style={{ marginTop: 8, textAlign: 'center', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Evaluated on {data.hybrid.num_students_evaluated} students
            </div>
          </div>

          {/* Content-only column */}
          <div style={{ background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-md)', padding: 20 }}>
            <h4 style={{ fontSize: '0.82rem', color: 'var(--accent-amber)', marginBottom: 12 }}>
              🔶 Content-Based Only
            </h4>
            <div className="grid-2">
              <div className="eval-metric">
                <div className="eval-metric__value" style={{ color: 'var(--accent-amber)' }}>
                  {(data.content_only.precision_at_k * 100).toFixed(2)}%
                </div>
                <div className="eval-metric__label">Precision@5</div>
              </div>
              <div className="eval-metric">
                <div className="eval-metric__value" style={{ color: 'var(--accent-rose)' }}>
                  {(data.content_only.recall_at_k * 100).toFixed(2)}%
                </div>
                <div className="eval-metric__label">Recall@5</div>
              </div>
            </div>
            <div style={{ marginTop: 8, textAlign: 'center', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Evaluated on {data.content_only.num_students_evaluated} students
            </div>
          </div>
        </div>

        {/* Improvement indicator */}
        <div
          style={{
            background: 'var(--accent-green-dim)',
            borderRadius: 'var(--radius-md)',
            padding: '14px 20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 24,
          }}
        >
          <span style={{ fontSize: '0.85rem', color: 'var(--accent-green)', fontWeight: 600 }}>
            ↑ Clustering boost
          </span>
          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-green)', fontWeight: 700 }}>
            Precision: +{improvementPrec.toFixed(1)}%
          </span>
          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-green)', fontWeight: 700 }}>
            Recall: +{improvementRec.toFixed(1)}%
          </span>
        </div>
      </div>

      {/* Bar chart comparison */}
      <div className="card">
        <div className="card__title" style={{ marginBottom: 16 }}>
          <span className="icon">📉</span> Visual Comparison
        </div>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={barData} margin={{ top: 10, right: 30, left: 10, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
            <XAxis
              dataKey="metric"
              tick={{ fill: '#9ba1b7', fontSize: 13 }}
            />
            <YAxis
              tick={{ fill: '#6b7185', fontSize: 11 }}
              tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`}
            />
            <Tooltip
              contentStyle={{
                background: '#1e2132',
                border: '1px solid rgba(99,132,255,0.3)',
                borderRadius: 8,
                fontSize: '0.82rem',
                color: '#e8eaf0',
              }}
              formatter={(value: number) => `${(value * 100).toFixed(3)}%`}
            />
            <Legend wrapperStyle={{ fontSize: '0.8rem', color: '#9ba1b7' }} />
            <Bar dataKey="Content-Based Only" fill="#fbbf24" radius={[4, 4, 0, 0]} barSize={50}>
              {barData.map((_, index) => (
                <Cell key={`cb-${index}`} fill="#fbbf24" fillOpacity={0.8} />
              ))}
            </Bar>
            <Bar dataKey="Hybrid (KB + Clustering)" fill="#6384ff" radius={[4, 4, 0, 0]} barSize={50}>
              {barData.map((_, index) => (
                <Cell key={`hy-${index}`} fill="#6384ff" fillOpacity={0.8} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Methodology note */}
      <div className="card">
        <div className="card__title" style={{ marginBottom: 10 }}>
          <span className="icon">📝</span> Methodology
        </div>
        <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
          <p>
            <strong>Evaluation protocol:</strong> For each student, 30% of their actual VLE interactions
            are held out as the test set. Recommendations are generated against the remaining 70%.
            Precision@5 measures the fraction of top-5 recommendations that appear in the held-out set;
            Recall@5 measures the fraction of the held-out set that is recovered.
          </p>
          <p style={{ marginTop: 10 }}>
            <strong>Ablation design:</strong> The "Content-Based Only" variant uses the same TF-IDF pipeline
            but neutralizes the cluster-based format boost (all format buckets set to 25% weight).
            The "Hybrid" variant applies a 1.3× boost to resources matching the student's cluster's
            dominant content-type preference. The difference demonstrates the marginal value of
            K-Means clustering in the recommendation pipeline.
          </p>
          <p style={{ marginTop: 10 }}>
            <strong>Note on absolute values:</strong> Precision/Recall values are expectedly low because
            the resource catalog contains {'>'}6000 items while the test set is a small slice of each
            student's interactions. The key insight is the <em>relative improvement</em> from
            adding cluster-based personalization.
          </p>
        </div>
      </div>
    </>
  );
}

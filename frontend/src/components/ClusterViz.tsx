import { useEffect, useState, useMemo } from 'react';
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import type { ClustersResponse } from '../api';
import { getClusters } from '../api';

const CLUSTER_COLORS = [
  '#6384ff', '#a78bfa', '#2dd4bf',
  '#fbbf24', '#fb7185', '#34d399',
];

export default function ClusterViz() {
  const [data, setData] = useState<ClustersResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getClusters()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  // Group students by cluster for Recharts scatter series
  const clusterGroups = useMemo(() => {
    if (!data) return [];
    const groups: Record<number, { id_student: number; pca_x: number; pca_y: number }[]> = {};
    data.students.forEach((s) => {
      if (!groups[s.cluster_label]) groups[s.cluster_label] = [];
      groups[s.cluster_label].push(s);
    });
    return Object.entries(groups).map(([label, students]) => ({
      label: Number(label),
      name: data.centroids.find((c) => c.cluster_id === Number(label))?.cluster_name ?? `Cluster ${label}`,
      students: students.slice(0, 1000), // cap for performance
      color: CLUSTER_COLORS[Number(label) % CLUSTER_COLORS.length],
    }));
  }, [data]);

  if (loading)
    return (
      <div className="loading">
        <div className="spinner" />
        <span>Loading cluster data…</span>
      </div>
    );

  if (error)
    return <div className="empty-state">⚠️ {error}</div>;

  if (!data) return null;

  return (
    <>
      {/* Summary */}
      <div className="card">
        <div className="card__header">
          <div className="card__title">
            <span className="icon">🔬</span> Cluster Analysis
          </div>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <span className="sil-badge">
              Silhouette: {data.silhouette_score.toFixed(4)}
            </span>
            <span
              className="sil-badge"
              style={{ background: 'var(--accent-blue-dim)', color: 'var(--accent-blue)' }}
            >
              k = {data.k}
            </span>
          </div>
        </div>

        {/* PCA scatter plot */}
        <div className="cluster-viz">
          <ResponsiveContainer width="100%" height={420}>
            <ScatterChart margin={{ top: 10, right: 20, bottom: 30, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis
                type="number"
                dataKey="pca_x"
                name="PC1"
                tick={{ fill: '#6b7185', fontSize: 11 }}
                label={{
                  value: 'Principal Component 1',
                  position: 'insideBottom',
                  offset: -18,
                  fill: '#6b7185',
                  fontSize: 12,
                }}
              />
              <YAxis
                type="number"
                dataKey="pca_y"
                name="PC2"
                tick={{ fill: '#6b7185', fontSize: 11 }}
                label={{
                  value: 'Principal Component 2',
                  angle: -90,
                  position: 'insideLeft',
                  offset: 0,
                  fill: '#6b7185',
                  fontSize: 12,
                }}
              />
              <Tooltip
                cursor={{ strokeDasharray: '3 3' }}
                contentStyle={{
                  background: '#1e2132',
                  border: '1px solid rgba(99,132,255,0.3)',
                  borderRadius: 8,
                  fontSize: '0.78rem',
                  color: '#e8eaf0',
                }}
                formatter={(value: number) => value.toFixed(3)}
              />
              <Legend
                wrapperStyle={{ fontSize: '0.78rem', color: '#9ba1b7' }}
              />
              {clusterGroups.map((g) => (
                <Scatter
                  key={g.label}
                  name={g.name}
                  data={g.students}
                  fill={g.color}
                  fillOpacity={0.6}
                  r={3}
                />
              ))}
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Centroid table */}
      <div className="card">
        <div className="card__title" style={{ marginBottom: 12 }}>
          <span className="icon">📋</span> Cluster Centroids (unscaled)
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="centroid-table">
            <thead>
              <tr>
                <th>Cluster</th>
                <th>Name</th>
                <th>% Content</th>
                <th>% Quiz</th>
                <th>% Discussion</th>
                <th>% Other</th>
                <th>Active Days</th>
                <th>Clicks/Day</th>
              </tr>
            </thead>
            <tbody>
              {data.centroids.map((c) => (
                <tr key={c.cluster_id}>
                  <td>
                    <span
                      style={{
                        display: 'inline-block',
                        width: 10,
                        height: 10,
                        borderRadius: '50%',
                        background: CLUSTER_COLORS[c.cluster_id % CLUSTER_COLORS.length],
                        marginRight: 6,
                      }}
                    />
                    {c.cluster_id}
                  </td>
                  <td style={{ fontFamily: 'var(--font-sans)', fontWeight: 500 }}>
                    {c.cluster_name}
                  </td>
                  <td>{(c.pct_structured_content * 100).toFixed(1)}%</td>
                  <td>{(c.pct_interactive_quiz * 100).toFixed(1)}%</td>
                  <td>{(c.pct_discussion_social * 100).toFixed(1)}%</td>
                  <td>{(c.pct_other * 100).toFixed(1)}%</td>
                  <td>{c.active_days?.toFixed(1) ?? '-'}</td>
                  <td>{c.clicks_per_active_day?.toFixed(1) ?? '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Elbow / silhouette line data */}
      <div className="card">
        <div className="card__title" style={{ marginBottom: 12 }}>
          <span className="icon">📈</span> Elbow & Silhouette Scores
        </div>
        <div className="grid-2">
          <div>
            <h4 style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: 8 }}>
              Inertia by k
            </h4>
            {data.elbow_data.k_values.map((k, i) => (
              <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.78rem',
                    width: 40,
                    color: k === data.k ? 'var(--accent-blue)' : 'var(--text-muted)',
                    fontWeight: k === data.k ? 700 : 400,
                  }}
                >
                  k={k}
                </span>
                <div
                  style={{
                    flex: 1,
                    height: 6,
                    background: 'rgba(255,255,255,0.06)',
                    borderRadius: 3,
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      height: '100%',
                      width: `${(data.elbow_data.inertias[i] / Math.max(...data.elbow_data.inertias)) * 100}%`,
                      background: k === data.k ? 'var(--accent-blue)' : 'var(--accent-blue-dim)',
                      borderRadius: 3,
                    }}
                  />
                </div>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: 'var(--text-muted)', width: 80, textAlign: 'right' }}>
                  {data.elbow_data.inertias[i].toFixed(0)}
                </span>
              </div>
            ))}
          </div>
          <div>
            <h4 style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: 8 }}>
              Silhouette Score by k
            </h4>
            {data.elbow_data.k_values.map((k, i) => (
              <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.78rem',
                    width: 40,
                    color: k === data.k ? 'var(--accent-green)' : 'var(--text-muted)',
                    fontWeight: k === data.k ? 700 : 400,
                  }}
                >
                  k={k}
                </span>
                <div
                  style={{
                    flex: 1,
                    height: 6,
                    background: 'rgba(255,255,255,0.06)',
                    borderRadius: 3,
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      height: '100%',
                      width: `${(data.elbow_data.silhouette_scores[i] / Math.max(...data.elbow_data.silhouette_scores)) * 100}%`,
                      background: k === data.k ? 'var(--accent-green)' : 'var(--accent-green-dim)',
                      borderRadius: 3,
                    }}
                  />
                </div>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: 'var(--text-muted)', width: 60, textAlign: 'right' }}>
                  {data.elbow_data.silhouette_scores[i].toFixed(4)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

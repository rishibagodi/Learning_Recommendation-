import { useEffect, useState } from 'react';
import type { StudentProfile } from '../api';
import { getStudent } from '../api';

interface Props {
  studentId: number;
}

const BUCKET_COLORS: Record<string, string> = {
  structured_content: 'var(--accent-blue)',
  interactive_quiz: 'var(--accent-purple)',
  discussion_social: 'var(--accent-teal)',
  other: 'var(--accent-amber)',
};

const BUCKET_LABELS: Record<string, string> = {
  structured_content: 'Structured Content',
  interactive_quiz: 'Interactive / Quiz',
  discussion_social: 'Discussion / Social',
  other: 'Other',
};

const CLUSTER_COLORS = [
  'var(--cluster-0)', 'var(--cluster-1)', 'var(--cluster-2)',
  'var(--cluster-3)', 'var(--cluster-4)', 'var(--cluster-5)',
];

export default function ProfilePanel({ studentId }: Props) {
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    setError('');
    getStudent(studentId)
      .then(setProfile)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [studentId]);

  if (loading)
    return (
      <div className="loading">
        <div className="spinner" />
        <span>Loading profile…</span>
      </div>
    );

  if (error)
    return <div className="empty-state">⚠️ {error}</div>;

  if (!profile) return null;

  const p = profile.pace_stats;
  const engagementBuckets = p
    ? [
        { key: 'structured_content', pct: p.pct_structured_content },
        { key: 'interactive_quiz', pct: p.pct_interactive_quiz },
        { key: 'discussion_social', pct: p.pct_discussion_social },
        { key: 'other', pct: p.pct_other },
      ]
    : [];

  const clColor =
    profile.cluster_label !== null
      ? CLUSTER_COLORS[profile.cluster_label % CLUSTER_COLORS.length]
      : 'var(--text-muted)';

  return (
    <>
      {/* Basic info + cluster */}
      <div className="card">
        <div className="card__header">
          <div className="card__title">
            <span className="icon">👤</span> Student Profile
          </div>
          <span
            className="cluster-badge"
            style={{
              background: `color-mix(in srgb, ${clColor} 15%, transparent)`,
              color: clColor,
            }}
          >
            ● {profile.cluster_name}
          </span>
        </div>

        <div className="info-row">
          <div className="profile-stat">
            <span className="profile-stat__label">Student ID</span>
            <span className="profile-stat__value profile-stat__value--accent">
              #{profile.id_student}
            </span>
          </div>
          <div className="profile-stat">
            <span className="profile-stat__label">Gender</span>
            <span className="profile-stat__value">{profile.gender}</span>
          </div>
          <div className="profile-stat">
            <span className="profile-stat__label">Region</span>
            <span className="profile-stat__value">{profile.region}</span>
          </div>
          <div className="profile-stat">
            <span className="profile-stat__label">Education</span>
            <span className="profile-stat__value">{profile.highest_education}</span>
          </div>
          <div className="profile-stat">
            <span className="profile-stat__label">Age Band</span>
            <span className="profile-stat__value">{profile.age_band}</span>
          </div>
          <div className="profile-stat">
            <span className="profile-stat__label">Result</span>
            <span className="profile-stat__value">{profile.final_result}</span>
          </div>
        </div>
      </div>

      {/* Pace stats + engagement */}
      {p && (
        <div className="card">
          <div className="card__title">
            <span className="icon">📊</span> Engagement & Pace
          </div>
          <div className="info-row" style={{ marginTop: 16 }}>
            <div className="profile-stat">
              <span className="profile-stat__label">Active Days (avg)</span>
              <span className="profile-stat__value">{p.avg_active_days}</span>
            </div>
            <div className="profile-stat">
              <span className="profile-stat__label">Clicks / Active Day</span>
              <span className="profile-stat__value">{p.avg_clicks_per_active_day}</span>
            </div>
          </div>
          <div className="engagement-bars" style={{ marginTop: 12 }}>
            {engagementBuckets.map((b) => (
              <div className="engagement-bar" key={b.key}>
                <span className="engagement-bar__label">{BUCKET_LABELS[b.key]}</span>
                <div className="engagement-bar__track">
                  <div
                    className="engagement-bar__fill"
                    style={{
                      width: `${(b.pct * 100).toFixed(1)}%`,
                      background: BUCKET_COLORS[b.key],
                    }}
                  />
                </div>
                <span className="engagement-bar__pct">{(b.pct * 100).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Weak topics */}
      <div className="card">
        <div className="card__title" style={{ marginBottom: 12 }}>
          <span className="icon">🎯</span> Topic Performance
        </div>
        {profile.weak_topics.length === 0 ? (
          <div className="empty-state">No assessment data available</div>
        ) : (
          profile.weak_topics.map((wt) => (
            <div
              key={wt.code_module}
              className={`weak-topic-item ${!wt.is_weak ? 'weak-topic-item--strong' : ''}`}
            >
              <div>
                <span className="weak-topic-item__module">{wt.code_module}</span>
                {wt.is_weak && (
                  <span className="tag tag--topic" style={{ marginLeft: 8 }}>
                    WEAK
                  </span>
                )}
              </div>
              <span className="weak-topic-item__scores">
                Module: {wt.module_avg_score} / Avg: {wt.student_avg_score}
              </span>
            </div>
          ))
        )}
      </div>
    </>
  );
}

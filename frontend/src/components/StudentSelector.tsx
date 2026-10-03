import { useState, useEffect, useRef, useCallback } from 'react';
import type { StudentSummary } from '../api';
import { getStudents } from '../api';

interface Props {
  onSelect: (student: StudentSummary) => void;
  selected: StudentSummary | null;
}

const CLUSTER_COLORS = [
  'var(--cluster-0)', 'var(--cluster-1)', 'var(--cluster-2)',
  'var(--cluster-3)', 'var(--cluster-4)', 'var(--cluster-5)',
];

export default function StudentSelector({ onSelect, selected }: Props) {
  const [query, setQuery] = useState('');
  const [allStudents, setAllStudents] = useState<StudentSummary[]>([]);
  const [filtered, setFiltered] = useState<StudentSummary[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Load students on mount
  useEffect(() => {
    setLoading(true);
    getStudents(2000, 0)
      .then((res) => {
        setAllStudents(res.students);
        setFiltered(res.students.slice(0, 30));
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  // Filter on query change
  useEffect(() => {
    if (!query.trim()) {
      setFiltered(allStudents.slice(0, 30));
      return;
    }
    const q = query.toLowerCase();
    const f = allStudents.filter(
      (s) =>
        String(s.id_student).includes(q) ||
        s.cluster_name.toLowerCase().includes(q) ||
        s.region?.toLowerCase().includes(q)
    );
    setFiltered(f.slice(0, 30));
  }, [query, allStudents]);

  // Click-outside to close
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleSelect = useCallback(
    (s: StudentSummary) => {
      onSelect(s);
      setQuery(String(s.id_student));
      setOpen(false);
    },
    [onSelect]
  );

  return (
    <div className="student-selector" ref={ref}>
      <input
        className="student-selector__input"
        type="text"
        placeholder={loading ? 'Loading students…' : 'Search student ID, name, region…'}
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
      />
      {open && filtered.length > 0 && (
        <div className="student-selector__dropdown">
          {filtered.map((s) => (
            <div
              key={s.id_student}
              className="student-selector__item"
              onClick={() => handleSelect(s)}
            >
              <span className="student-selector__item-id">#{s.id_student}</span>
              <span
                className="student-selector__item-cluster"
                style={{
                  background: s.cluster_label !== null
                    ? `${CLUSTER_COLORS[s.cluster_label % CLUSTER_COLORS.length]}22`
                    : 'var(--bg-tertiary)',
                  color: s.cluster_label !== null
                    ? CLUSTER_COLORS[s.cluster_label % CLUSTER_COLORS.length]
                    : 'var(--text-muted)',
                }}
              >
                {s.cluster_name}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

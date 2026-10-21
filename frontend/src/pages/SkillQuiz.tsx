import { useEffect, useState } from 'react';
import { api, type Question, type SkillResult } from '../api';
import QuizForm from './QuizForm';

export default function SkillQuiz({ onDone }: { onDone: () => void }) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [results, setResults] = useState<SkillResult[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => { api.skillQuiz().then(setQuestions).catch(e => setError(e.message)); }, []);

  const submit = async (answers: Record<string, number>) => {
    setBusy(true);
    try { setResults(await api.submitSkillQuiz(answers)); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  if (results) {
    const skipped = results.filter(r => r.correct === r.total).length;
    return (
      <div className="narrow">
        <p className="eyebrow">Skill check results</p>
        <h1>{skipped ? `You can skip ${skipped} topic${skipped > 1 ? 's' : ''}` : 'Your roadmap starts from the basics'}</h1>
        <table className="table">
          <thead><tr><th>Topic</th><th>Score</th><th>What happens</th></tr></thead>
          <tbody>
            {results.map(r => (
              <tr key={r.topic}>
                <td>{r.topic}</td>
                <td>{r.correct}/{r.total}</td>
                <td><span className={`tag ${r.correct === r.total ? 'good' : r.correct ? 'warn' : 'bad'}`}>{r.result}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="actions"><button className="btn primary" onClick={onDone}>See my roadmap</button></div>
      </div>
    );
  }

  return (
    <div className="narrow">
      <p className="eyebrow">Quick skill check · {questions.length} questions</p>
      <h1>Let's see what you already know</h1>
      <p className="muted">Answer honestly; a guess that's right could skip a topic you need. Topics you get fully right are skipped in your roadmap.</p>
      {error && <p className="error">{error}</p>}
      {questions.length > 0 && <QuizForm questions={questions} submitLabel="Build my roadmap" busy={busy} onSubmit={submit} />}
    </div>
  );
}

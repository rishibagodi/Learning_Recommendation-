import { useState } from 'react';
import type { Question } from '../api';

/** Renders MCQs grouped by topic; calls onSubmit with {questionId: optionIndex}. */
export default function QuizForm({ questions, submitLabel, onSubmit, busy }: {
  questions: Question[]; submitLabel: string; busy?: boolean; onSubmit: (a: Record<string, number>) => void;
}) {
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const answered = Object.keys(answers).length;
  let lastTopic = '';

  return (
    <div className="quiz">
      {questions.map((q, i) => {
        const header = q.topic !== lastTopic ? <h3 className="quiz-topic">{q.topic}</h3> : null;
        lastTopic = q.topic;
        return (
          <div key={q.id}>
            {header}
            <fieldset className="question">
              <legend><span className="qnum">{i + 1}</span>{q.q}</legend>
              {q.options.map((o, j) => (
                <label key={j} className={`option ${answers[q.id] === j ? 'on' : ''}`}>
                  <input type="radio" name={q.id} checked={answers[q.id] === j} onChange={() => setAnswers({ ...answers, [q.id]: j })} />
                  {o}
                </label>
              ))}
            </fieldset>
          </div>
        );
      })}
      <div className="actions sticky">
        <span className="muted">{answered}/{questions.length} answered</span>
        <button className="btn primary" disabled={busy || answered < questions.length} onClick={() => onSubmit(answers)}>
          {busy ? 'Checking…' : submitLabel}
        </button>
      </div>
    </div>
  );
}

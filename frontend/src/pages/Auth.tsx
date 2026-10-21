import { useState, type FormEvent } from 'react';
import { api, setToken } from '../api';

export default function Auth({ onDone }: { onDone: () => void }) {
  const [mode, setMode] = useState<'login' | 'signup'>('signup');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(''); setBusy(true);
    try {
      const r = mode === 'signup' ? await api.signup(name, email, password) : await api.login(email, password);
      setToken(r.token);
      onDone();
    } catch (err) {
      setError((err as Error).message);
    } finally { setBusy(false); }
  };

  return (
    <div className="auth">
      <section className="auth-pitch">
        <div className="brand big"><span className="brand-mark">◆</span> AI Learning Recommender</div>
        <h1>Tell us what you want to learn. We'll build your roadmap.</h1>
        <ul className="pitch-list">
          <li><b>Skill check</b> finds what you already know, so you skip it.</li>
          <li><b>Personal roadmap</b> orders topics by prerequisites and fits your weekly time.</li>
          <li><b>Videos and resources</b> picked for your level and favourite format, each with a reason.</li>
        </ul>
      </section>
      <form className="card auth-card" onSubmit={submit}>
        <div className="seg">
          <button type="button" className={mode === 'signup' ? 'on' : ''} onClick={() => setMode('signup')}>Sign up</button>
          <button type="button" className={mode === 'login' ? 'on' : ''} onClick={() => setMode('login')}>Log in</button>
        </div>
        {mode === 'signup' && (
          <label>Name<input value={name} onChange={e => setName(e.target.value)} required autoComplete="name" /></label>
        )}
        <label>Email<input type="email" value={email} onChange={e => setEmail(e.target.value)} required autoComplete="email" /></label>
        <label>Password
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} required minLength={6}
            autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} />
        </label>
        {error && <p className="error">{error}</p>}
        <button className="btn primary" disabled={busy}>{busy ? 'Please wait…' : mode === 'signup' ? 'Create account' : 'Log in'}</button>
      </form>
    </div>
  );
}

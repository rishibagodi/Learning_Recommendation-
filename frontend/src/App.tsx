import { useCallback, useEffect, useState } from 'react';
import { api, getToken, setToken, type Me } from './api';
import Auth from './pages/Auth';
import Onboarding from './pages/Onboarding';
import SkillQuiz from './pages/SkillQuiz';
import Dashboard from './pages/Dashboard';
import StepView from './pages/StepView';

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(!!getToken());
  const [stepKey, setStepKey] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!getToken()) { setMe(null); setLoading(false); return; }
    try { setMe(await api.me()); } catch { setMe(null); } finally { setLoading(false); }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const logout = () => { setToken(null); setMe(null); setStepKey(null); };
  const restart = async () => {
    if (!window.confirm('Start over with a new domain or goal? Your current roadmap and progress will be cleared.')) return;
    await api.restart();
    setStepKey(null);
    refresh();
  };

  if (loading) return <div className="center muted">Loading…</div>;
  if (!me) return <Auth onDone={refresh} />;

  return (
    <div className="shell">
      <header className="topbar">
        <button className="brand" onClick={() => setStepKey(null)}>
          <span className="brand-mark">◆</span> AI Learning Recommender
        </button>
        <div className="topbar-right">
          {me.stage === 'ready' && <button className="btn ghost sm" onClick={restart}>Change goal</button>}
          <span className="muted">{me.user.name}</span>
          <button className="btn ghost sm" onClick={logout}>Log out</button>
        </div>
      </header>
      <main className="content">
        {me.stage === 'onboarding' && <Onboarding name={me.user.name} onDone={refresh} />}
        {me.stage === 'quiz' && <SkillQuiz onDone={refresh} />}
        {me.stage === 'ready' && (stepKey
          ? <StepView key={stepKey} topicKey={stepKey} onBack={() => setStepKey(null)} onOpen={setStepKey} />
          : <Dashboard me={me} onOpen={setStepKey} />)}
      </main>
    </div>
  );
}

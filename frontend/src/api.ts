/** Typed client for the v2 backend. The login token lives in localStorage. */

const TOKEN_KEY = 'lrs_token';

export const getToken = () => {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
};
export const setToken = (t: string | null) => {
  try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); } catch { /* storage blocked */ }
};

async function call<T>(method: string, url: string, body?: unknown): Promise<T> {
  const token = getToken();
  const resp = await fetch(`/api${url}`, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await resp.json().catch(() => ({}));
  if (resp.status === 401 && token) setToken(null);
  if (!resp.ok) {
    const d = data.detail;
    throw new Error(typeof d === 'string' ? d : Array.isArray(d) ? d.map((e: { msg: string }) => e.msg).join(', ') : `Error ${resp.status}`);
  }
  return data as T;
}

/* ---------- types ---------- */

export type Format = 'video' | 'article' | 'practice';
export type Level = 'beginner' | 'intermediate' | 'advanced';

export interface User { id: number; name: string; email: string }
export interface Profile {
  domain: string; goal: string; level: Level; format: Format;
  hours_per_week: number; days_per_week: number; likes_discussion: number;
  cluster_id: number | null; cluster_name: string; cluster_source: string;
}
export interface Me {
  user: User; stage: 'onboarding' | 'quiz' | 'ready'; profile: Profile | null;
  model: { type: string; students?: number; clusters?: number; silhouette?: number };
}
export interface Domain { id: string; name: string; description: string; goals: { id: string; name: string }[]; topics: string[] }
export interface Question { id: string; topic: string; q: string; options: string[] }
export interface SkillResult { topic: string; correct: number; total: number; result: string }

export type StepStatus = 'locked' | 'available' | 'revise' | 'completed' | 'skipped';
export interface Step {
  topic_key: string; name: string; position: number; status: StepStatus; difficulty: number;
  hours: number; weeks: number; prereqs: string[]; skill_score: string | null; step_score: string | null;
}
export interface Roadmap {
  domain: string; goal: string; steps: Step[]; progress_pct: number;
  total_hours: number; remaining_hours: number; remaining_weeks: number;
}
export interface Resource {
  id: number; kind: Format; source: string; title: string; url: string; channel: string | null;
  thumbnail: string | null; duration_min: number | null; views: number | null; difficulty: number;
  score: number; why: string; done: number; helpful: number | null;
}
export interface StepDetail extends Step {
  keywords: string[]; warning: string | null; reason: string; recommended: Resource[]; completed: Resource[];
}
export interface QuizResult { correct: number; total: number; passed: boolean; next: Step | null }

/* ---------- endpoints ---------- */

type AuthResp = { token: string; user: User };
export const api = {
  signup: (name: string, email: string, password: string) => call<AuthResp>('POST', '/auth/signup', { name, email, password }),
  login: (email: string, password: string) => call<AuthResp>('POST', '/auth/login', { email, password }),
  me: () => call<Me>('GET', '/me'),
  domains: () => call<Domain[]>('GET', '/domains'),
  onboarding: (body: Omit<Profile, 'cluster_id' | 'cluster_name' | 'cluster_source' | 'likes_discussion'> & { likes_discussion: boolean }) =>
    call<Profile>('POST', '/onboarding', body),
  skillQuiz: () => call<Question[]>('GET', '/quiz/skill'),
  submitSkillQuiz: (answers: Record<string, number>) => call<SkillResult[]>('POST', '/quiz/skill', { answers }),
  restart: () => call<{ ok: boolean }>('DELETE', '/profile'),
  roadmap: () => call<Roadmap>('GET', '/roadmap'),
  step: (key: string) => call<StepDetail>('GET', `/steps/${encodeURIComponent(key)}`),
  stepQuiz: (key: string) => call<Question[]>('GET', `/steps/${encodeURIComponent(key)}/quiz`),
  submitStepQuiz: (key: string, answers: Record<string, number>) =>
    call<QuizResult>('POST', `/steps/${encodeURIComponent(key)}/quiz`, { answers }),
  progress: (id: number, done: boolean, helpful: boolean | null = null) =>
    call<{ ok: boolean }>('POST', `/resources/${id}/progress`, { done, helpful }),
};

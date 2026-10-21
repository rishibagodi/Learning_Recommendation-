# AI-Based Learning Recommendation System (v2)

A student signs up, picks a domain and goal, takes a short skill check, and gets a **personalized roadmap** with **YouTube videos, docs and practice resources** for each step. Every recommendation comes with a reason. The roadmap adapts after a mini-quiz on each step.

## How it works

| Stage | What happens | Technique | Code |
|---|---|---|---|
| 1. Onboarding | Domain, goal, level, preferred format (video / reading / practice), hours and days per week | Learner feature vector | `main.py` → `/api/onboarding` |
| 2. Learner profile | Assigns a profile such as "practice-driven fast learner" | K-Means trained on OULAD click behaviour; rule-based fallback until trained | `profile_model.py` |
| 3. Skill check | 2 MCQs per topic; full marks = topic skipped, partial = shorter estimate | Score per topic | `/api/quiz/skill` |
| 4. Roadmap | Goal → required topics (prerequisite closure) → ordered, known topics skipped, weeks estimated | Skill graph + topological sort (Kahn) | `roadmap.py` |
| 5. Recommendations | Ranks the topic's videos and links for this learner | TF-IDF + cosine similarity × format boost × profile boost × difficulty match × session-length fit × popularity | `recommender.py` |
| 6. Explanations | e.g. "Matches your preference for videos; beginner level, right for you now; 20 min fits one study session" | Explainable output | `recommender.explain` |
| 7. Adapt | 3-question check per step: pass → completed, next unlocks; fail → "revise", resources shift to basics | Feedback loop | `/api/steps/{topic}/quiz` |

**Domains (MVP):** Web Development, Data Science, AI / Machine Learning. Each has 3 goals, 8 topics with prerequisites, 3 MCQs per topic and curated links. Edit or add domains in `backend/app/domains/*.json`; no code change is needed.

## Setup

**Requirements:** Python 3.10+, Node.js 18+.

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
```

Fill in `backend/.env`:

- `YOUTUBE_API_KEY`: in [Google Cloud Console](https://console.cloud.google.com/), create a project → APIs & Services → Library → enable **YouTube Data API v3** → Credentials → Create credentials → API key.
- `JWT_SECRET`: any random string of 32+ characters.

Start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

Videos are fetched from YouTube the first time a student opens a step, then cached in `app.db`. To fetch everything up front (about 2,500 of the 10,000 free daily quota units):

```bash
python -m app.content fetch
```

Without a key the app still works and shows the curated docs and practice links.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173 (proxies /api to :8000)
```

For a single-server demo, run `npm run build`; the backend then serves the built site at http://localhost:8000.

### 3. Optional: train the learner-profile model on OULAD

Put the OULAD `vle.csv` and `studentVle.csv` in `data/raw/` ([download](https://analyse.kmi.open.ac.uk/open-dataset)), then:

```bash
cd backend
python -m app.profile_model train      # k=4 by default; prints silhouette and cluster sizes
```

This saves `data/processed/profile_model.pkl`; restart the API to use it. A new user's answers are mapped onto the same 6 behaviour features using OULAD percentiles (for example, "prefers practice" → 90th percentile of quiz-click share), then assigned to the nearest cluster. This mapping is an approximation: OULAD has click data, not questionnaire answers.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/auth/signup`, `/api/auth/login` | Returns a JWT |
| GET | `/api/me` | User, stage (`onboarding` / `quiz` / `ready`), profile, model info |
| GET | `/api/domains` | Domains, goals, topics |
| POST | `/api/onboarding` | Save answers, assign learner profile |
| GET/POST | `/api/quiz/skill` | Skill-check questions / submit, which builds the roadmap |
| GET | `/api/roadmap` | Steps with status, hours, weeks, progress |
| GET | `/api/steps/{topic_key}` | Ranked resources with reasons |
| POST | `/api/resources/{id}/progress` | Mark done / helpful |
| GET/POST | `/api/steps/{topic_key}/quiz` | Mini-quiz / submit |
| DELETE | `/api/profile` | Start over with a new goal |

Interactive docs: http://localhost:8000/docs

## Project structure

```
backend/
  app/
    main.py            FastAPI routes
    auth.py            signup/login, PBKDF2 hashes, JWT
    db.py              SQLite schema + helpers (app.db is created automatically)
    content.py         domain loader, curated links, YouTube Data API fetch + cache
    profile_model.py   K-Means learner profiles (train on OULAD / assign new users)
    roadmap.py         prerequisite closure + topological sort + progress view
    recommender.py     hybrid TF-IDF ranking + explanations
    pipeline.py        v1 OULAD pipeline (reused for profile features)
    domains/           web_dev.json, data_science.json, ai_ml.json
  .env.example
frontend/src/
  App.tsx              stage routing
  api.ts               typed API client
  pages/               Auth, Onboarding, SkillQuiz, Dashboard, StepView, QuizForm
```

## Notes and limits

- The curated links in the domain files were written by hand; click through them once before a demo.
- The YouTube free quota is 10,000 units a day; each topic search costs about 101 units. Results are cached, so each topic is searched once.
- Future work: LLM-generated roadmaps for any domain, collaborative filtering ("students like you also watched") from the helpful/done feedback, a teacher view, streaks and reminders.

Dataset (optional profile model): OULAD, CC-BY 4.0. Code: MIT.

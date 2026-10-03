# OULAD Learning Resource Recommendation System

An AI-based personalized learning resource recommendation system built as an academic course project. Uses **K-Means clustering** on student engagement behavior and **content-based filtering** (TF-IDF + cosine similarity) to recommend resources targeted at each student's weak topic areas, with natural-language explanations for every recommendation.

## Dataset

- **Source**: [Open University Learning Analytics Dataset (OULAD)](https://analyse.kmi.open.ac.uk/open-dataset) — CC-BY 4.0 license
- **Downloaded from**: Official OU Analyse website
- **Files** (7 CSVs in `data/raw/`):
  - `courses.csv` — Module/presentation info
  - `assessments.csv` — Assessment metadata
  - `vle.csv` — Virtual Learning Environment resource catalog
  - `studentInfo.csv` — Student demographics
  - `studentRegistration.csv` — Enrollment data
  - `studentAssessment.csv` — Student assessment scores
  - `studentVle.csv` — Student click-level VLE interactions (~10.6M rows)

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Frontend (React + TypeScript + Recharts)                │
│  ├── Student Selector (searchable dropdown)              │
│  ├── Profile Panel (cluster, pace, weak topics)          │
│  ├── Recommendations Panel (top-N with explanations)     │
│  ├── Cluster Visualization (PCA scatter plot)            │
│  └── Evaluation Tab (ablation study bar charts)          │
├──────────────────────────────────────────────────────────┤
│  Backend (Python + FastAPI)                              │
│  ├── Stage 1: Preprocessing (engagement matrix)          │
│  ├── Stage 2: Weak-topic detection                       │
│  ├── Stage 3: K-Means clustering (elbow + silhouette)    │
│  ├── Stage 4: Resource catalog + TF-IDF vectorization    │
│  ├── Stage 5: Hybrid recommendation (filter → rank)      │
│  └── Stage 6: Evaluation (Precision@k, Recall@k)        │
└──────────────────────────────────────────────────────────┘
```

## ML Pipeline Details

### 1. Preprocessing
- Merges `studentVle` + `vle` to build per-student content-type engagement matrix
- Activity types bucketed into 4 categories:
  - **structured_content**: oucontent, resource, subpage, url, page
  - **interactive_quiz**: quiz, externalquiz
  - **discussion_social**: forumng, ouwiki, ouelluminate, oucollaborate
  - **other**: anything else
- Features: % of total clicks per bucket + pace features (active_days, clicks_per_active_day)

### 2. Weak-Topic Detection
- Merges `studentAssessment` + `assessments` to compute per-student average score per module
- Flags modules where a student's score < their own global average as "weak areas"

### 3. K-Means Clustering
- Clusters students on engagement-bucket percentages + pace features (StandardScaler applied)
- Elbow method + silhouette score used to justify k (tested k=3 to 6)
- Each cluster is named/interpreted based on its centroid (e.g., "quiz-driven fast learner")

### 4. Resource Catalog
- Built from `vle.csv`, each resource tagged with topic (code_module) and format (bucketed activity type)
- Vectorized with TF-IDF

### 5. Hybrid Recommendation (Staged)
- **Stage 1**: Filter catalog to resources tagged with student's weak topic(s)
- **Stage 2**: Rank by cosine similarity to student profile, boosted (1.3×) by cluster's dominant content-type preference
- Returns top-N with one-line natural-language explanation per recommendation

### 6. Evaluation
- **Precision@k** and **Recall@k** via 70/30 holdout of student VLE interactions
- **Ablation study**: content-based-only vs. hybrid (content-based + clustering)
- Demonstrates that clustering measurably improves hit rate

## How to Run

### Prerequisites
- Python 3.10+ 
- Node.js 18+
- npm 9+

### Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Run the data pipeline (first time — processes ~430MB of data, takes ~2 min)
python -m app.pipeline

# Start the API server (loads cached pipeline state)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The pipeline prints silhouette scores, chosen k, and ablation study results to the console.

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (proxies /api to localhost:8000)
npm run dev
```

Open http://localhost:5173 in your browser.

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/students?limit=100&offset=0` | List students with ID, cluster label, basic info |
| `GET /api/students/{id}` | Full profile: cluster, pace stats, weak topics |
| `GET /api/students/{id}/recommendations?n=5` | Ranked resources + explanation strings |
| `GET /api/clusters` | Cluster centroids + PCA 2D coordinates per student |
| `GET /api/evaluation` | Precision@k / Recall@k for both ablation variants |

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── pipeline.py          # Full ML pipeline (6 stages)
│   │   └── main.py              # FastAPI endpoints
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api.ts               # Typed API client
│   │   ├── App.tsx              # Main app shell
│   │   ├── App.css              # Component styles
│   │   ├── index.css            # Design system
│   │   ├── main.tsx             # Entry point
│   │   └── components/
│   │       ├── StudentSelector.tsx
│   │       ├── ProfilePanel.tsx
│   │       ├── RecommendationsPanel.tsx
│   │       ├── ClusterViz.tsx
│   │       └── EvaluationPanel.tsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
├── data/
│   ├── raw/                     # OULAD CSV files (not committed)
│   └── processed/               # Cached pipeline state
└── README.md
```

## Design Decisions

- **No deep learning / collaborative filtering**: Intentionally scoped to K-Means + content-based filtering since OULAD has no explicit rating signal
- **Staged (not blended) recommendation**: Filter first by weak topics, then rank — makes the pipeline explainable
- **Explanation strings**: Every recommendation includes a human-readable reason, critical for academic transparency
- **Ablation study**: Demonstrates the marginal value of clustering — hybrid approach nearly doubles precision

## License

Dataset: CC-BY 4.0 (Open University Learning Analytics Dataset)
Code: MIT

import { useState } from 'react';
import type { StudentSummary } from './api';
import StudentSelector from './components/StudentSelector';
import ProfilePanel from './components/ProfilePanel';
import RecommendationsPanel from './components/RecommendationsPanel';
import ClusterViz from './components/ClusterViz';
import EvaluationPanel from './components/EvaluationPanel';
import './App.css';

type Tab = 'student' | 'clusters' | 'evaluation';

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('student');
  const [selectedStudent, setSelectedStudent] = useState<StudentSummary | null>(null);

  return (
    <div className="app-shell">
      {/* Header */}
      <header className="app-header">
        <div className="app-header__title">
          <h1>🎓 OULAD Learning Resource Recommender</h1>
          <span className="badge">K-Means + Content-Based</span>
        </div>
        <StudentSelector onSelect={setSelectedStudent} selected={selectedStudent} />
      </header>

      {/* Tabs */}
      <nav className="tabs">
        <button
          className={`tab ${activeTab === 'student' ? 'tab--active' : ''}`}
          onClick={() => setActiveTab('student')}
        >
          👤 Student Profile & Recommendations
        </button>
        <button
          className={`tab ${activeTab === 'clusters' ? 'tab--active' : ''}`}
          onClick={() => setActiveTab('clusters')}
        >
          🔬 Cluster Analysis
        </button>
        <button
          className={`tab ${activeTab === 'evaluation' ? 'tab--active' : ''}`}
          onClick={() => setActiveTab('evaluation')}
        >
          📊 Evaluation & Ablation
        </button>
      </nav>

      {/* Content */}
      <main className="app-main">
        {activeTab === 'student' && (
          <>
            {!selectedStudent ? (
              <div className="empty-state">
                <div className="empty-state__icon">🔍</div>
                <p>Select a student from the search bar above to view their profile and recommendations.</p>
                <p className="text-muted" style={{ marginTop: 8, fontSize: '0.82rem' }}>
                  Try searching by student ID (e.g., 11391) or cluster type (e.g., "quiz-driven")
                </p>
              </div>
            ) : (
              <div className="grid-2">
                <div>
                  <ProfilePanel studentId={selectedStudent.id_student} />
                </div>
                <div>
                  <RecommendationsPanel studentId={selectedStudent.id_student} />
                </div>
              </div>
            )}
          </>
        )}

        {activeTab === 'clusters' && <ClusterViz />}

        {activeTab === 'evaluation' && <EvaluationPanel />}
      </main>
    </div>
  );
}

export default App;

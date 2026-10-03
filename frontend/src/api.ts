/**
 * API client for the OULAD Learning Resource Recommender backend.
 */

const BASE = '/api';

async function fetchJSON<T>(url: string): Promise<T> {
  const resp = await fetch(url);
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`API error ${resp.status}: ${text}`);
  }
  return resp.json() as Promise<T>;
}

/* ---------- Types ---------- */

export interface StudentSummary {
  id_student: number;
  gender: string;
  region: string;
  highest_education: string;
  age_band: string;
  final_result: string;
  cluster_label: number | null;
  cluster_name: string;
}

export interface StudentListResponse {
  total: number;
  offset: number;
  limit: number;
  students: StudentSummary[];
}

export interface WeakTopic {
  code_module: string;
  module_avg_score: number;
  student_avg_score: number;
  is_weak: boolean;
}

export interface PaceStats {
  avg_active_days: number;
  avg_clicks_per_active_day: number;
  pct_structured_content: number;
  pct_interactive_quiz: number;
  pct_discussion_social: number;
  pct_other: number;
}

export interface StudentProfile {
  id_student: number;
  gender: string;
  region: string;
  highest_education: string;
  age_band: string;
  final_result: string;
  cluster_label: number | null;
  cluster_name: string;
  pace_stats: PaceStats;
  weak_topics: WeakTopic[];
}

export interface Recommendation {
  id_site: number;
  activity_type: string;
  topic: string;
  bucket: string;
  score: number;
  explanation: string;
}

export interface RecommendationResponse {
  id_student: number;
  n: number;
  recommendations: Recommendation[];
}

export interface ClusterCentroid {
  cluster_id: number;
  cluster_name: string;
  pct_structured_content: number;
  pct_interactive_quiz: number;
  pct_discussion_social: number;
  pct_other: number;
  active_days: number;
  clicks_per_active_day: number;
}

export interface ClusterStudent {
  id_student: number;
  cluster_label: number;
  pca_x: number;
  pca_y: number;
}

export interface ElbowData {
  k_values: number[];
  inertias: number[];
  silhouette_scores: number[];
}

export interface ClustersResponse {
  k: number;
  silhouette_score: number;
  elbow_data: ElbowData;
  centroids: ClusterCentroid[];
  students: ClusterStudent[];
}

export interface EvalVariant {
  precision_at_k: number;
  recall_at_k: number;
  num_students_evaluated: number;
}

export interface EvaluationResponse {
  hybrid: EvalVariant;
  content_only: EvalVariant;
}

/* ---------- API functions ---------- */

export function getStudents(limit = 100, offset = 0): Promise<StudentListResponse> {
  return fetchJSON(`${BASE}/students?limit=${limit}&offset=${offset}`);
}

export function getStudent(id: number): Promise<StudentProfile> {
  return fetchJSON(`${BASE}/students/${id}`);
}

export function getRecommendations(id: number, n = 5): Promise<RecommendationResponse> {
  return fetchJSON(`${BASE}/students/${id}/recommendations?n=${n}`);
}

export function getClusters(): Promise<ClustersResponse> {
  return fetchJSON(`${BASE}/clusters`);
}

export function getEvaluation(): Promise<EvaluationResponse> {
  return fetchJSON(`${BASE}/evaluation`);
}

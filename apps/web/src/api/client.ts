/**
 * API client for RepoPilot backend.
 */

export interface HealthResponse {
  status: string;
}

export interface ReadyResponse {
  status: string;
  database: string;
}

export interface Repository {
  id: string;
  source: string;
  url: string | null;
  full_name: string;
  default_branch: string;
  status: "registered" | "scanning" | "ready" | "failed" | string;
  indexed_at: string | null;
  created_at: string;
}

export interface ModuleMetricItem {
  path: string;
  loc: number;
  sloc: number;
  complexity: number;
  maintainability_index: number;
  functions_count: number;
  fan_in: number;
  fan_out: number;
}

export interface MetricsSummary {
  total_loc: number;
  total_sloc: number;
  total_lloc: number;
  total_comments: number;
  total_blank: number;
  avg_complexity: number;
  avg_maintainability_index: number;
  modules_count: number;
  modules?: ModuleMetricItem[];
}

export interface Scan {
  id: string;
  repository_id: string;
  status: "pending" | "in_progress" | "completed" | "failed" | string;
  current_stage: "queued" | "fetching" | "filtering" | "parsing" | "metrics" | "completed" | "failed" | string;
  stage_progress: Record<string, any> | null;
  error_message: string | null;
  file_count: number;
  total_lines: number;
  total_symbols: number;
  metrics_summary: MetricsSummary | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface RAGCitation {
  file_path: string;
  start_line: number;
  end_line: number;
  content: string;
  symbol_name?: string | null;
  similarity_score: number;
  source: string;
}

export interface RAGResponse {
  question: string;
  answer: string;
  abstained: boolean;
  citations: RAGCitation[];
  source: string;
  model_version: string;
}

export interface SearchResultItem {
  id: string;
  path: string;
  start_line: number;
  end_line: number;
  score: number;
  content: string;
  symbol_name?: string | null;
  symbol_type?: string | null;
  context_header: string;
  source: string;
}

export interface SearchResponse {
  repository_id: string;
  query: string;
  count: number;
  results: SearchResultItem[];
}

const API_BASE_URL = import.meta.env.VITE_API_URL || "";

export async function fetchHealthz(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/healthz`);
  if (!response.ok) {
    throw new Error(`API health check failed with status ${response.status}`);
  }
  return response.json() as Promise<HealthResponse>;
}

export async function fetchReadyz(): Promise<ReadyResponse> {
  const response = await fetch(`${API_BASE_URL}/readyz`);
  if (!response.ok) {
    const errorBody = (await response.json().catch(() => ({}))) as Partial<ReadyResponse>;
    throw new Error(
      errorBody.database
        ? `Database: ${errorBody.database} (Status: ${errorBody.status || response.status})`
        : `API readiness check failed with status ${response.status}`
    );
  }
  return response.json() as Promise<ReadyResponse>;
}

export async function fetchRepositories(): Promise<Repository[]> {
  const response = await fetch(`${API_BASE_URL}/repositories`);
  if (!response.ok) {
    throw new Error(`Failed to fetch repositories (HTTP ${response.status})`);
  }
  return response.json() as Promise<Repository[]>;
}

export async function fetchRepository(id: string): Promise<Repository> {
  const response = await fetch(`${API_BASE_URL}/repositories/${id}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch repository '${id}' (HTTP ${response.status})`);
  }
  return response.json() as Promise<Repository>;
}

export async function registerRepository(url: string): Promise<Repository> {
  const response = await fetch(`${API_BASE_URL}/repositories`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.error?.message || err.detail || `Registration failed (HTTP ${response.status})`);
  }
  return response.json() as Promise<Repository>;
}

export async function uploadRepositoryZip(file: File): Promise<Repository> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE_URL}/repositories/upload`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.error?.message || err.detail || `Upload failed (HTTP ${response.status})`);
  }
  return response.json() as Promise<Repository>;
}

export async function triggerScan(repoId: string): Promise<Scan> {
  const response = await fetch(`${API_BASE_URL}/repositories/${repoId}/scan`, {
    method: "POST",
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.error?.message || err.detail || `Failed to trigger scan (HTTP ${response.status})`);
  }
  return response.json() as Promise<Scan>;
}

export async function fetchLatestScan(repoId: string): Promise<Scan | null> {
  const response = await fetch(`${API_BASE_URL}/repositories/${repoId}/scan`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Failed to fetch latest scan (HTTP ${response.status})`);
  }
  return response.json() as Promise<Scan>;
}

export async function fetchScans(repoId: string): Promise<Scan[]> {
  const response = await fetch(`${API_BASE_URL}/repositories/${repoId}/scans`);
  if (!response.ok) {
    throw new Error(`Failed to fetch scans (HTTP ${response.status})`);
  }
  return response.json() as Promise<Scan[]>;
}

export async function askQuestion(
  repoId: string,
  question: string,
  maxCitations: number = 5
): Promise<RAGResponse> {
  const response = await fetch(`${API_BASE_URL}/repositories/${repoId}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, max_citations: maxCitations }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Question query failed (HTTP ${response.status})`);
  }
  return response.json() as Promise<RAGResponse>;
}

export async function searchCode(
  repoId: string,
  query: string,
  limit: number = 10
): Promise<SearchResponse> {
  const response = await fetch(
    `${API_BASE_URL}/repositories/${repoId}/search?q=${encodeURIComponent(query)}&limit=${limit}`
  );
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Search failed (HTTP ${response.status})`);
  }
  return response.json() as Promise<SearchResponse>;
}

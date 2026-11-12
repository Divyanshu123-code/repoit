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

export interface TopFeature {
  feature: string;
  value: number;
  description: string;
}

export interface MLPredictionItem {
  id: string;
  file_path: string;
  function_name: string | null;
  line_start: number | null;
  line_end: number | null;
  risk_probability: number;
  risk_band: "low" | "medium" | "high";
  model_version: string;
  top_features: TopFeature[];
  source: "ml_predicted";
  created_at: string;
}

export interface DefectRiskSummary {
  total_modules: number;
  high_risk_count: number;
  medium_risk_count: number;
  low_risk_count: number;
  average_risk_probability: number;
}

export interface DefectRiskResponse {
  repository_id: string;
  model_version: string;
  disclaimer: string;
  source: "ml_predicted";
  summary: DefectRiskSummary;
  predictions: MLPredictionItem[];
}

export async function fetchDefectRisk(
  repoId: string,
  riskBand?: "low" | "medium" | "high"
): Promise<DefectRiskResponse> {
  const query = riskBand ? `?risk_band=${riskBand}` : "";
  const response = await fetch(`${API_BASE_URL}/repositories/${repoId}/defect-risk${query}`);
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to fetch defect risk (HTTP ${response.status})`);
  }
  return response.json() as Promise<DefectRiskResponse>;
}

export async function triggerDefectRiskPrediction(
  repoId: string
): Promise<DefectRiskResponse> {
  const response = await fetch(`${API_BASE_URL}/repositories/${repoId}/defect-risk/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Prediction failed (HTTP ${response.status})`);
  }
  return response.json() as Promise<DefectRiskResponse>;
}

// --- Phase 4: Static Findings & Dependency Graph ---

export interface StaticFindingItem {
  id: string;
  rule: string;
  rule_url: string | null;
  message: string;
  severity: "error" | "warning" | "info";
  category: string;
  file_path: string;
  line_number: number;
  column_number: number | null;
  end_line_number: number | null;
  end_column_number: number | null;
  fix_suggested: string | null;
  source: "static";
  created_at: string;
}

export interface FindingsSummary {
  total_findings: number;
  error_count: number;
  warning_count: number;
  info_count: number;
}

export interface StaticFindingsResponse {
  repository_id: string;
  source: "static";
  summary: FindingsSummary;
  findings: StaticFindingItem[];
  total_count: number;
  limit: number;
  offset: number;
}

export async function fetchStaticFindings(
  repoId: string,
  severity?: string,
  rule?: string,
  file?: string
): Promise<StaticFindingsResponse> {
  const params = new URLSearchParams();
  if (severity) params.append("severity", severity);
  if (rule) params.append("rule", rule);
  if (file) params.append("file", file);
  params.append("limit", "100");

  const qs = params.toString() ? `?${params.toString()}` : "";
  const response = await fetch(`${API_BASE_URL}/repositories/${repoId}/findings${qs}`);
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to fetch static findings (HTTP ${response.status})`);
  }
  return response.json() as Promise<StaticFindingsResponse>;
}

export async function triggerStaticScan(repoId: string): Promise<StaticFindingsResponse> {
  const response = await fetch(`${API_BASE_URL}/repositories/${repoId}/findings/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Static scan failed (HTTP ${response.status})`);
  }
  return response.json() as Promise<StaticFindingsResponse>;
}

export interface GraphNode {
  id: string;
  file_path: string;
  in_degree: number;
  out_degree: number;
  is_internal: boolean;
}

export interface GraphEdgeItem {
  id: string;
  source_file: string;
  target_module: string;
  target_file: string | null;
  import_statement: string | null;
  line_number: number | null;
  is_internal: boolean;
  imported_symbols: string[];
  source: "graph_derived";
}

export interface GraphSummary {
  total_nodes: number;
  internal_edges_count: number;
  external_edges_count: number;
  cycles_count: number;
  is_dag: boolean;
  density: number;
  top_imported_modules: Array<{
    file_path: string;
    in_degree: number;
    out_degree: number;
  }>;
}

export interface GraphResponse {
  repository_id: string;
  scan_id: string | null;
  source: "graph_derived";
  summary: GraphSummary;
  nodes: GraphNode[];
  edges: GraphEdgeItem[];
}

export interface AffectedFileItem {
  file_path: string;
  depth: number;
  impact_tier: "changed" | "direct" | "transitive";
  seed_file: string;
  dependency_chain: string[];
  direct_imported_module: string | null;
  in_degree: number;
  out_degree: number;
  source: "graph_derived";
}

export interface ImpactResponse {
  repository_id: string;
  changed_files: string[];
  max_depth: number;
  include_changed: boolean;
  total_affected_count: number;
  direct_affected_count: number;
  transitive_affected_count: number;
  total_repo_files: number;
  impact_ratio: number;
  affected_files: AffectedFileItem[];
  source: "graph_derived";
}

export async function fetchRepositoryGraph(
  repoId: string,
  internalOnly: boolean = true
): Promise<GraphResponse> {
  const response = await fetch(
    `${API_BASE_URL}/repositories/${repoId}/graph?internal_only=${internalOnly}`
  );
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to fetch graph (HTTP ${response.status})`);
  }
  return response.json() as Promise<GraphResponse>;
}

export async function fetchChangeImpact(
  repoId: string,
  changedFiles: string[],
  maxDepth: number = 3,
  includeChanged: boolean = false
): Promise<ImpactResponse> {
  const response = await fetch(`${API_BASE_URL}/repositories/${repoId}/graph/impact`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      changed_files: changedFiles,
      max_depth: maxDepth,
      include_changed: includeChanged,
    }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Impact query failed (HTTP ${response.status})`);
  }
  return response.json() as Promise<ImpactResponse>;
}

export async function triggerRebuildGraph(
  repoId: string,
  includeExternal: boolean = false
): Promise<GraphResponse> {
  const response = await fetch(`${API_BASE_URL}/repositories/${repoId}/graph/rebuild`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ include_external: includeExternal }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Rebuild graph failed (HTTP ${response.status})`);
  }
  return response.json() as Promise<GraphResponse>;
}


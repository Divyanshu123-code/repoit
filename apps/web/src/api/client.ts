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


import React from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchHealthz, fetchReadyz } from "../api/client";

export const HealthPage: React.FC = () => {
  const healthQuery = useQuery({
    queryKey: ["healthz"],
    queryFn: fetchHealthz,
    refetchInterval: 10000,
  });

  const readyQuery = useQuery({
    queryKey: ["readyz"],
    queryFn: fetchReadyz,
    refetchInterval: 10000,
  });

  return (
    <div style={{ maxWidth: "680px", margin: "2rem auto", padding: "0 1rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
        <h2 style={{ margin: 0, color: "#0f172a", fontSize: "1.5rem" }}>System Health Status</h2>
        <button
          onClick={() => {
            void healthQuery.refetch();
            void readyQuery.refetch();
          }}
          style={{
            padding: "0.5rem 1rem",
            backgroundColor: "#2563eb",
            color: "#ffffff",
            border: "none",
            borderRadius: "6px",
            cursor: "pointer",
            fontWeight: 500,
          }}
        >
          Refresh Probes
        </button>
      </div>

      <div style={{ display: "grid", gap: "1rem" }}>
        {/* Liveness Probe */}
        <div
          style={{
            border: "1px solid #e2e8f0",
            borderRadius: "8px",
            padding: "1.25rem",
            backgroundColor: "#ffffff",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <h3 style={{ margin: "0 0 0.25rem", fontSize: "1.1rem" }}>API Liveness (`/healthz`)</h3>
              <p style={{ margin: 0, color: "#64748b", fontSize: "0.875rem" }}>
                Verifies the FastAPI application server process is running.
              </p>
            </div>
            <div>
              {healthQuery.isLoading && <span style={{ color: "#64748b" }}>Checking...</span>}
              {healthQuery.isSuccess && (
                <span
                  style={{
                    backgroundColor: "#dcfce7",
                    color: "#166534",
                    padding: "0.25rem 0.75rem",
                    borderRadius: "9999px",
                    fontWeight: 600,
                    fontSize: "0.875rem",
                  }}
                >
                  ● ONLINE ({healthQuery.data.status.toUpperCase()})
                </span>
              )}
              {healthQuery.isError && (
                <span
                  style={{
                    backgroundColor: "#fee2e2",
                    color: "#991b1b",
                    padding: "0.25rem 0.75rem",
                    borderRadius: "9999px",
                    fontWeight: 600,
                    fontSize: "0.875rem",
                  }}
                >
                  ● UNREACHABLE
                </span>
              )}
            </div>
          </div>
          {healthQuery.isError && (
            <p style={{ margin: "0.75rem 0 0", color: "#b91c1c", fontSize: "0.875rem" }}>
              {healthQuery.error.message}
            </p>
          )}
        </div>

        {/* Readiness Probe */}
        <div
          style={{
            border: "1px solid #e2e8f0",
            borderRadius: "8px",
            padding: "1.25rem",
            backgroundColor: "#ffffff",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <h3 style={{ margin: "0 0 0.25rem", fontSize: "1.1rem" }}>Database Readiness (`/readyz`)</h3>
              <p style={{ margin: 0, color: "#64748b", fontSize: "0.875rem" }}>
                Verifies database connectivity (PostgreSQL + pgvector).
              </p>
            </div>
            <div>
              {readyQuery.isLoading && <span style={{ color: "#64748b" }}>Checking...</span>}
              {readyQuery.isSuccess && (
                <span
                  style={{
                    backgroundColor: "#dcfce7",
                    color: "#166534",
                    padding: "0.25rem 0.75rem",
                    borderRadius: "9999px",
                    fontWeight: 600,
                    fontSize: "0.875rem",
                  }}
                >
                  ● READY ({readyQuery.data.database.toUpperCase()})
                </span>
              )}
              {readyQuery.isError && (
                <span
                  style={{
                    backgroundColor: "#fef3c7",
                    color: "#92400e",
                    padding: "0.25rem 0.75rem",
                    borderRadius: "9999px",
                    fontWeight: 600,
                    fontSize: "0.875rem",
                  }}
                >
                  ● NOT READY
                </span>
              )}
            </div>
          </div>
          {readyQuery.isError && (
            <p style={{ margin: "0.75rem 0 0", color: "#b45309", fontSize: "0.875rem" }}>
              {readyQuery.error.message}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};


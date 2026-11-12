import React from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchRepository,
  fetchLatestScan,
  triggerScan,
  Repository,
  Scan,
} from "../api/client";

const STAGES = [
  { id: "queued", label: "Queued", desc: "Waiting for worker" },
  { id: "fetching", label: "Safe Fetch", desc: "Shallow clone / unpack" },
  { id: "filtering", label: "File Filter", desc: "Prune binaries & secrets" },
  { id: "parsing", label: "Tree-sitter", desc: "Extract symbols & imports" },
  { id: "metrics", label: "Code Metrics", desc: "Radon CC & Halstead" },
  { id: "completed", label: "Ready", desc: "Indexed & analyzed" },
];

export const RepoOverviewPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const repoId = id || "";
  const queryClient = useQueryClient();

  // 1. Fetch Repository details
  const {
    data: repository,
    isLoading: isRepoLoading,
    error: repoError,
  } = useQuery<Repository>({
    queryKey: ["repository", repoId],
    queryFn: () => fetchRepository(repoId),
    enabled: Boolean(repoId),
    refetchInterval: (query) => {
      const data = query.state.data;
      return data?.status === "scanning" ? 1000 : 5000;
    },
  });

  // 2. Fetch Latest Scan (live poll when scanning/in_progress)
  const { data: latestScan } = useQuery<Scan | null>({
    queryKey: ["latest_scan", repoId],
    queryFn: () => fetchLatestScan(repoId),
    enabled: Boolean(repoId),
    refetchInterval: (query) => {
      const scan = query.state.data;
      const isScanning =
        repository?.status === "scanning" ||
        scan?.status === "in_progress" ||
        scan?.status === "pending";
      return isScanning ? 1000 : false;
    },
  });

  // 3. Trigger / Re-run scan mutation
  const scanMutation = useMutation({
    mutationFn: () => triggerScan(repoId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repository", repoId] });
      queryClient.invalidateQueries({ queryKey: ["latest_scan", repoId] });
    },
  });

  if (isRepoLoading) {
    return (
      <div style={{ maxWidth: "1100px", margin: "3rem auto", textAlign: "center", color: "#64748b" }}>
        Loading repository overview...
      </div>
    );
  }

  if (repoError || !repository) {
    return (
      <div style={{ maxWidth: "1100px", margin: "3rem auto", padding: "0 1.5rem" }}>
        <div style={{ padding: "1.5rem", backgroundColor: "#fef2f2", color: "#991b1b", borderRadius: "8px" }}>
          Repository not found or error loading repository.
        </div>
        <div style={{ marginTop: "1rem" }}>
          <Link to="/" style={{ color: "#2563eb", textDecoration: "none" }}>
            ← Back to Repositories
          </Link>
        </div>
      </div>
    );
  }

  const isScanning =
    repository.status === "scanning" ||
    latestScan?.status === "in_progress" ||
    latestScan?.status === "pending";

  const getStageIndex = (stageId: string) => {
    return STAGES.findIndex((s) => s.id === stageId);
  };

  const currentStageIdx = latestScan ? getStageIndex(latestScan.current_stage) : -1;

  const getRankColor = (cc: number) => {
    if (cc <= 5) return { label: "Rank A (Simple)", color: "#059669", bg: "#ecfdf5" };
    if (cc <= 10) return { label: "Rank B (Moderate)", color: "#2563eb", bg: "#eff6ff" };
    if (cc <= 20) return { label: "Rank C (Complex)", color: "#d97706", bg: "#fffbeb" };
    return { label: "Rank D+ (High Risk)", color: "#dc2626", bg: "#fef2f2" };
  };

  const metrics = latestScan?.metrics_summary;

  return (
    <div style={{ maxWidth: "1100px", margin: "2rem auto", padding: "0 1.5rem" }}>
      {/* Breadcrumb & Navigation */}
      <div style={{ marginBottom: "1rem" }}>
        <Link to="/" style={{ color: "#2563eb", textDecoration: "none", fontSize: "0.9rem", fontWeight: 500 }}>
          ← Back to Repositories
        </Link>
      </div>

      {/* Header Card */}
      <div
        style={{
          backgroundColor: "#ffffff",
          borderRadius: "8px",
          padding: "1.5rem",
          boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.1)",
          border: "1px solid #e2e8f0",
          marginBottom: "1.5rem",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.25rem" }}>
            <h1 style={{ fontSize: "1.6rem", fontWeight: 700, margin: 0, color: "#0f172a" }}>
              {repository.full_name}
            </h1>
            <span
              style={{
                display: "inline-block",
                padding: "0.2rem 0.6rem",
                borderRadius: "9999px",
                fontSize: "0.75rem",
                fontWeight: 600,
                textTransform: "uppercase",
                backgroundColor:
                  repository.status === "ready"
                    ? "#ecfdf5"
                    : repository.status === "scanning"
                    ? "#eff6ff"
                    : repository.status === "failed"
                    ? "#fef2f2"
                    : "#f8fafc",
                color:
                  repository.status === "ready"
                    ? "#047857"
                    : repository.status === "scanning"
                    ? "#1d4ed8"
                    : repository.status === "failed"
                    ? "#b91c1c"
                    : "#475569",
                border: `1px solid ${
                  repository.status === "ready"
                    ? "#a7f3d0"
                    : repository.status === "scanning"
                    ? "#bfdbfe"
                    : repository.status === "failed"
                    ? "#fecaca"
                    : "#cbd5e1"
                }`,
              }}
            >
              {repository.status}
            </span>
            <span
              style={{
                fontSize: "0.75rem",
                fontWeight: 600,
                color: "#64748b",
                backgroundColor: "#f1f5f9",
                padding: "0.2rem 0.5rem",
                borderRadius: "4px",
              }}
            >
              source: static
            </span>
          </div>

          <p style={{ margin: 0, color: "#64748b", fontSize: "0.9rem" }}>
            Branch: <code style={{ backgroundColor: "#f1f5f9", padding: "0.1rem 0.3rem", borderRadius: "3px" }}>{repository.default_branch}</code>
            {repository.url && (
              <>
                {" • "}
                <a
                  href={repository.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: "#2563eb", textDecoration: "none" }}
                >
                  View on GitHub ↗
                </a>
              </>
            )}
            {" • "}
            Last indexed: {repository.indexed_at ? new Date(repository.indexed_at).toLocaleString() : "Never"}
          </p>
        </div>

        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
          <Link
            to={`/repositories/${repository.id}/defect-risk`}
            style={{
              backgroundColor: "#fef3c7",
              color: "#92400e",
              border: "1px solid #f59e0b",
              padding: "0.65rem 1.25rem",
              borderRadius: "6px",
              fontWeight: 600,
              fontSize: "0.9rem",
              textDecoration: "none",
              display: "inline-flex",
              alignItems: "center",
              gap: "0.4rem",
            }}
          >
            <span>🎯 Defect Risk</span>
          </Link>
          <Link
            to={`/repositories/${repository.id}/chat`}
            style={{
              backgroundColor: "#ffffff",
              color: "#2563eb",
              border: "1px solid #2563eb",
              padding: "0.65rem 1.25rem",
              borderRadius: "6px",
              fontWeight: 600,
              fontSize: "0.9rem",
              textDecoration: "none",
              display: "inline-flex",
              alignItems: "center",
              gap: "0.4rem",
            }}
          >
            <span>💬 Ask AI Assistant</span>
          </Link>
          <button
            onClick={() => scanMutation.mutate()}
            disabled={isScanning || scanMutation.isPending}
            style={{
              backgroundColor: isScanning ? "#94a3b8" : "#2563eb",
              color: "#ffffff",
              padding: "0.65rem 1.25rem",
              borderRadius: "6px",
              border: "none",
              fontWeight: 600,
              fontSize: "0.9rem",
              cursor: isScanning ? "not-allowed" : "pointer",
            }}
          >
            {isScanning
              ? "Scanning in Progress..."
              : repository.status === "ready"
              ? "Re-run Scan"
              : "Trigger Scan"}
          </button>
        </div>
      </div>

      {/* Live Scan Progress Stepper (Acceptance Criteria: shows scan progress live) */}
      <div
        style={{
          backgroundColor: "#ffffff",
          borderRadius: "8px",
          padding: "1.5rem",
          boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.1)",
          border: "1px solid #e2e8f0",
          marginBottom: "1.5rem",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
          <div>
            <h2 style={{ fontSize: "1.1rem", fontWeight: 600, margin: 0 }}>Scan Pipeline & Stage Progress</h2>
            <p style={{ margin: "0.25rem 0 0", color: "#64748b", fontSize: "0.85rem" }}>
              Live stage execution status for ingestion, Tree-sitter AST symbol extraction, and radon metrics.
            </p>
          </div>
          {isScanning && (
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#2563eb", fontSize: "0.85rem", fontWeight: 600 }}>
              <span style={{ display: "inline-block", width: "8px", height: "8px", borderRadius: "50%", backgroundColor: "#2563eb" }} />
              Live Polling Active (1s)
            </div>
          )}
        </div>

        {/* Stepper items */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: "0.5rem" }}>
          {STAGES.map((stg, idx) => {
            const isCompleted =
              latestScan?.status === "completed" ||
              (currentStageIdx > idx && latestScan?.status !== "failed");
            const isCurrent = latestScan?.current_stage === stg.id && isScanning;
            const isFailed = latestScan?.status === "failed" && latestScan?.current_stage === "failed" && idx === Math.max(0, currentStageIdx);

            let borderColor = "#e2e8f0";
            let bgColor = "#f8fafc";
            let textColor = "#64748b";

            if (isCompleted) {
              borderColor = "#a7f3d0";
              bgColor = "#ecfdf5";
              textColor = "#047857";
            } else if (isCurrent) {
              borderColor = "#bfdbfe";
              bgColor = "#eff6ff";
              textColor = "#1d4ed8";
            } else if (isFailed) {
              borderColor = "#fecaca";
              bgColor = "#fef2f2";
              textColor = "#b91c1c";
            }

            return (
              <div
                key={stg.id}
                style={{
                  border: `1px solid ${borderColor}`,
                  backgroundColor: bgColor,
                  borderRadius: "6px",
                  padding: "0.75rem",
                  transition: "all 0.2s ease",
                }}
              >
                <div style={{ fontSize: "0.75rem", fontWeight: 700, color: textColor, marginBottom: "0.25rem" }}>
                  {isCompleted ? "✓ " : isCurrent ? "⏳ " : isFailed ? "✕ " : `${idx + 1}. `}
                  {stg.label}
                </div>
                <div style={{ fontSize: "0.75rem", color: "#64748b" }}>{stg.desc}</div>
              </div>
            );
          })}
        </div>

        {/* Failure message display if failed */}
        {latestScan?.status === "failed" && (
          <div
            style={{
              marginTop: "1rem",
              padding: "0.75rem 1rem",
              backgroundColor: "#fef2f2",
              color: "#991b1b",
              borderRadius: "6px",
              fontSize: "0.85rem",
              border: "1px solid #fecaca",
            }}
          >
            <strong>Scan Failed:</strong> {latestScan.error_message || "Unknown error during execution."}
          </div>
        )}
      </div>

      {/* Language & Code Metrics Overview */}
      {metrics && (
        <div style={{ marginBottom: "1.5rem" }}>
          <h2 style={{ fontSize: "1.15rem", fontWeight: 600, margin: "0 0 1rem" }}>
            Language & Code Metrics
          </h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1rem" }}>
            {/* Primary Language */}
            <div
              style={{
                backgroundColor: "#ffffff",
                padding: "1.25rem",
                borderRadius: "8px",
                border: "1px solid #e2e8f0",
                boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.05)",
              }}
            >
              <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "#64748b", textTransform: "uppercase" }}>
                Primary Language
              </div>
              <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#0f172a", marginTop: "0.25rem" }}>
                Python
              </div>
              <div style={{ fontSize: "0.8rem", color: "#059669", marginTop: "0.25rem", fontWeight: 500 }}>
                100% Python codebase
              </div>
            </div>

            {/* Total Lines of Code */}
            <div
              style={{
                backgroundColor: "#ffffff",
                padding: "1.25rem",
                borderRadius: "8px",
                border: "1px solid #e2e8f0",
                boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.05)",
              }}
            >
              <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "#64748b", textTransform: "uppercase" }}>
                Lines of Code (LOC)
              </div>
              <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#0f172a", marginTop: "0.25rem" }}>
                {metrics.total_loc.toLocaleString()}
              </div>
              <div style={{ fontSize: "0.8rem", color: "#64748b", marginTop: "0.25rem" }}>
                {metrics.total_sloc.toLocaleString()} SLOC • {metrics.total_comments} Comments
              </div>
            </div>

            {/* Extracted Symbols */}
            <div
              style={{
                backgroundColor: "#ffffff",
                padding: "1.25rem",
                borderRadius: "8px",
                border: "1px solid #e2e8f0",
                boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.05)",
              }}
            >
              <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "#64748b", textTransform: "uppercase" }}>
                Tree-sitter Symbols
              </div>
              <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#0f172a", marginTop: "0.25rem" }}>
                {(latestScan.total_symbols || 0).toLocaleString()}
              </div>
              <div style={{ fontSize: "0.8rem", color: "#64748b", marginTop: "0.25rem" }}>
                Classes, functions, and methods
              </div>
            </div>

            {/* Cyclomatic Complexity */}
            <div
              style={{
                backgroundColor: "#ffffff",
                padding: "1.25rem",
                borderRadius: "8px",
                border: "1px solid #e2e8f0",
                boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.05)",
              }}
            >
              <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "#64748b", textTransform: "uppercase" }}>
                Avg Cyclomatic Complexity
              </div>
              <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#0f172a", marginTop: "0.25rem" }}>
                {metrics.avg_complexity}
              </div>
              <div style={{ marginTop: "0.25rem" }}>
                {(() => {
                  const r = getRankColor(metrics.avg_complexity);
                  return (
                    <span
                      style={{
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        padding: "0.1rem 0.4rem",
                        borderRadius: "4px",
                        backgroundColor: r.bg,
                        color: r.color,
                      }}
                    >
                      {r.label}
                    </span>
                  );
                })()}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* File Tree & Module Breakdown */}
      <div
        style={{
          backgroundColor: "#ffffff",
          borderRadius: "8px",
          boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.1)",
          border: "1px solid #e2e8f0",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            padding: "1rem 1.5rem",
            borderBottom: "1px solid #e2e8f0",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <h2 style={{ fontSize: "1.1rem", fontWeight: 600, margin: 0 }}>Analyzed Python Files</h2>
            <span
              style={{
                fontSize: "0.75rem",
                fontWeight: 600,
                color: "#64748b",
                backgroundColor: "#f1f5f9",
                padding: "0.15rem 0.4rem",
                borderRadius: "4px",
              }}
            >
              source: static
            </span>
          </div>
          <span style={{ fontSize: "0.85rem", color: "#64748b" }}>
            {metrics?.modules ? `${metrics.modules.length} modules` : "No modules indexed"}
          </span>
        </div>

        {!metrics?.modules || metrics.modules.length === 0 ? (
          <div style={{ padding: "3rem", textAlign: "center", color: "#64748b" }}>
            <p style={{ margin: "0 0 0.5rem" }}>No module analysis data available.</p>
            <p style={{ margin: 0, fontSize: "0.85rem" }}>
              Click "Trigger Scan" above to run the ingestion and analysis pipeline.
            </p>
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
            <thead>
              <tr
                style={{
                  backgroundColor: "#f8fafc",
                  borderBottom: "1px solid #e2e8f0",
                  fontSize: "0.75rem",
                  textTransform: "uppercase",
                  color: "#64748b",
                }}
              >
                <th style={{ padding: "0.75rem 1.5rem" }}>File Path</th>
                <th style={{ padding: "0.75rem 1rem" }}>LOC</th>
                <th style={{ padding: "0.75rem 1rem" }}>SLOC</th>
                <th style={{ padding: "0.75rem 1rem" }}>Complexity</th>
                <th style={{ padding: "0.75rem 1rem" }}>MI Score</th>
                <th style={{ padding: "0.75rem 1rem" }}>Functions</th>
                <th style={{ padding: "0.75rem 1.5rem" }}>Coupling (In/Out)</th>
              </tr>
            </thead>
            <tbody>
              {metrics.modules.map((m) => (
                <tr key={m.path} style={{ borderBottom: "1px solid #f1f5f9", fontSize: "0.9rem" }}>
                  <td style={{ padding: "0.85rem 1.5rem", fontFamily: "monospace", color: "#1e293b", fontWeight: 600 }}>
                    {m.path}
                  </td>
                  <td style={{ padding: "0.85rem 1rem", color: "#64748b" }}>{m.loc}</td>
                  <td style={{ padding: "0.85rem 1rem", color: "#64748b" }}>{m.sloc}</td>
                  <td style={{ padding: "0.85rem 1rem", fontWeight: 600 }}>{m.complexity}</td>
                  <td style={{ padding: "0.85rem 1rem", color: m.maintainability_index > 50 ? "#059669" : "#d97706" }}>
                    {m.maintainability_index}
                  </td>
                  <td style={{ padding: "0.85rem 1rem", color: "#64748b" }}>{m.functions_count}</td>
                  <td style={{ padding: "0.85rem 1.5rem", color: "#64748b", fontSize: "0.85rem" }}>
                    in: {m.fan_in} • out: {m.fan_out}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

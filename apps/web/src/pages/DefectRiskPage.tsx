import React, { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchRepository,
  fetchDefectRisk,
  triggerDefectRiskPrediction,
} from "../api/client";

export function DefectRiskPage(): React.ReactElement {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [selectedBand, setSelectedBand] = useState<"all" | "low" | "medium" | "high">("all");

  const repoQuery = useQuery({
    queryKey: ["repository", id],
    queryFn: () => (id ? fetchRepository(id) : null),
    enabled: Boolean(id),
  });

  const riskQuery = useQuery({
    queryKey: ["defect-risk", id, selectedBand],
    queryFn: () =>
      id
        ? fetchDefectRisk(
            id,
            selectedBand === "all" ? undefined : selectedBand
          )
        : null,
    enabled: Boolean(id),
  });

  const predictMutation = useMutation({
    mutationFn: () => (id ? triggerDefectRiskPrediction(id) : Promise.reject("No repo id")),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["defect-risk", id] });
    },
  });

  const repo = repoQuery.data;
  const riskData = riskQuery.data;
  const summary = riskData?.summary;

  return (
    <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "24px 16px" }}>
      {/* Breadcrumb Navigation */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px", fontSize: "14px", color: "#64748b" }}>
        <Link to="/" style={{ color: "#3b82f6", textDecoration: "none" }}>Repositories</Link>
        <span>/</span>
        {id && (
          <Link to={`/repositories/${id}`} style={{ color: "#3b82f6", textDecoration: "none" }}>
            {repo?.full_name || "Overview"}
          </Link>
        )}
        <span>/</span>
        <span style={{ fontWeight: 600, color: "#1e293b" }}>ML Defect Risk</span>
      </div>

      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
        <div>
          <h1 style={{ margin: "0 0 6px 0", fontSize: "26px", fontWeight: 700, color: "#0f172a" }}>
            Defect Risk Analysis
          </h1>
          <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
            <span style={{ fontSize: "14px", color: "#64748b" }}>
              Repository: <strong>{repo?.full_name || id}</strong>
            </span>
            <span
              data-testid="model-version-badge"
              style={{
                backgroundColor: "#e0e7ff",
                color: "#3730a3",
                padding: "2px 8px",
                borderRadius: "4px",
                fontSize: "12px",
                fontWeight: 600,
              }}
            >
              Model: {riskData?.model_version || "v2.0.0"}
            </span>
            <span
              data-testid="rule-5-source-badge"
              style={{
                backgroundColor: "#f1f5f9",
                color: "#475569",
                padding: "2px 8px",
                borderRadius: "4px",
                fontSize: "12px",
                fontWeight: 600,
              }}
            >
              source: {riskData?.source || "ml_predicted"}
            </span>
          </div>
        </div>

        <div style={{ display: "flex", gap: "12px" }}>
          <Link
            to={`/repositories/${id}`}
            style={{
              padding: "8px 16px",
              backgroundColor: "#f8fafc",
              border: "1px solid #cbd5e1",
              borderRadius: "6px",
              color: "#334155",
              textDecoration: "none",
              fontWeight: 500,
              fontSize: "14px",
            }}
          >
            ← Overview
          </Link>
          <Link
            to={`/repositories/${id}/chat`}
            style={{
              padding: "8px 16px",
              backgroundColor: "#f8fafc",
              border: "1px solid #cbd5e1",
              borderRadius: "6px",
              color: "#334155",
              textDecoration: "none",
              fontWeight: 500,
              fontSize: "14px",
            }}
          >
            💬 Chat RAG
          </Link>
          <button
            onClick={() => predictMutation.mutate()}
            disabled={predictMutation.isPending}
            style={{
              padding: "8px 16px",
              backgroundColor: "#2563eb",
              border: "none",
              borderRadius: "6px",
              color: "#ffffff",
              fontWeight: 600,
              fontSize: "14px",
              cursor: predictMutation.isPending ? "not-allowed" : "pointer",
            }}
          >
            {predictMutation.isPending ? "Analyzing Risk..." : "⚡ Re-analyze Defect Risk"}
          </button>
        </div>
      </div>

      {/* Hard Rule 6 Notice Banner */}
      <div
        data-testid="rule-6-disclaimer-banner"
        style={{
          backgroundColor: "#fffbeb",
          border: "1px solid #fde68a",
          borderLeft: "5px solid #d97706",
          borderRadius: "6px",
          padding: "14px 18px",
          marginBottom: "24px",
          color: "#92400e",
          fontSize: "14px",
          lineHeight: "1.5",
        }}
      >
        <strong>⚠️ Probabilistic Risk Notice (Hard Rule 6): </strong>
        {riskData?.disclaimer || "Predictions are risk estimates, never confirmed bugs."} Model version{" "}
        <strong>{riskData?.model_version || "v2.0.0"}</strong> uses McCabe cyclomatic complexity, Halstead volume,
        and executable LOC metrics to prioritize manual code review and automated testing.
      </div>

      {/* KPI Summary Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px", marginBottom: "24px" }}>
        <div style={{ backgroundColor: "#ffffff", padding: "16px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
          <div style={{ fontSize: "12px", color: "#64748b", textTransform: "uppercase", fontWeight: 600 }}>Total Modules</div>
          <div style={{ fontSize: "28px", fontWeight: 700, color: "#0f172a", marginTop: "4px" }}>
            {summary?.total_modules ?? 0}
          </div>
        </div>

        <div style={{ backgroundColor: "#ffffff", padding: "16px", borderRadius: "8px", border: "1px solid #fecaca", borderLeft: "4px solid #ef4444" }}>
          <div style={{ fontSize: "12px", color: "#b91c1c", textTransform: "uppercase", fontWeight: 600 }}>High Risk (&ge;65%)</div>
          <div style={{ fontSize: "28px", fontWeight: 700, color: "#dc2626", marginTop: "4px" }}>
            {summary?.high_risk_count ?? 0}
          </div>
        </div>

        <div style={{ backgroundColor: "#ffffff", padding: "16px", borderRadius: "8px", border: "1px solid #fed7aa", borderLeft: "4px solid #f97316" }}>
          <div style={{ fontSize: "12px", color: "#c2410c", textTransform: "uppercase", fontWeight: 600 }}>Medium Risk (35-65%)</div>
          <div style={{ fontSize: "28px", fontWeight: 700, color: "#ea580c", marginTop: "4px" }}>
            {summary?.medium_risk_count ?? 0}
          </div>
        </div>

        <div style={{ backgroundColor: "#ffffff", padding: "16px", borderRadius: "8px", border: "1px solid #bbf7d0", borderLeft: "4px solid #22c55e" }}>
          <div style={{ fontSize: "12px", color: "#15803d", textTransform: "uppercase", fontWeight: 600 }}>Low Risk (&lt;35%)</div>
          <div style={{ fontSize: "28px", fontWeight: 700, color: "#16a34a", marginTop: "4px" }}>
            {summary?.low_risk_count ?? 0}
          </div>
        </div>

        <div style={{ backgroundColor: "#ffffff", padding: "16px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
          <div style={{ fontSize: "12px", color: "#64748b", textTransform: "uppercase", fontWeight: 600 }}>Avg Defect Probability</div>
          <div style={{ fontSize: "28px", fontWeight: 700, color: "#0f172a", marginTop: "4px" }}>
            {summary ? `${(summary.average_risk_probability * 100).toFixed(1)}%` : "0.0%"}
          </div>
        </div>
      </div>

      {/* Filter Tabs */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
        {(["all", "high", "medium", "low"] as const).map((band) => (
          <button
            key={band}
            onClick={() => setSelectedBand(band)}
            style={{
              padding: "6px 14px",
              borderRadius: "6px",
              border: selectedBand === band ? "2px solid #2563eb" : "1px solid #cbd5e1",
              backgroundColor: selectedBand === band ? "#eff6ff" : "#ffffff",
              color: selectedBand === band ? "#1d4ed8" : "#475569",
              fontWeight: 600,
              fontSize: "13px",
              cursor: "pointer",
              textTransform: "capitalize",
            }}
          >
            {band === "all" ? "All Modules" : `${band} Risk`}
          </button>
        ))}
      </div>

      {/* Predictions Table / Cards */}
      {riskQuery.isLoading ? (
        <div style={{ padding: "40px", textAlign: "center", color: "#64748b" }}>Loading defect predictions...</div>
      ) : riskData?.predictions.length === 0 ? (
        <div style={{ padding: "40px", textAlign: "center", backgroundColor: "#ffffff", borderRadius: "8px", border: "1px dashed #cbd5e1" }}>
          <p style={{ color: "#64748b", margin: "0 0 16px 0" }}>
            No defect risk predictions found for this filter. Run an analysis to predict defect propensities.
          </p>
          <button
            onClick={() => predictMutation.mutate()}
            style={{
              padding: "8px 16px",
              backgroundColor: "#2563eb",
              color: "#ffffff",
              border: "none",
              borderRadius: "6px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Run Defect Risk Analysis
          </button>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {riskData?.predictions.map((item) => {
            const isHigh = item.risk_band === "high";
            const isMedium = item.risk_band === "medium";
            const badgeBg = isHigh ? "#fee2e2" : isMedium ? "#ffedd5" : "#dcfce7";
            const badgeColor = isHigh ? "#b91c1c" : isMedium ? "#c2410c" : "#15803d";

            return (
              <div
                key={item.id}
                data-testid="defect-prediction-row"
                style={{
                  backgroundColor: "#ffffff",
                  border: "1px solid #e2e8f0",
                  borderRadius: "8px",
                  padding: "16px",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                  <div>
                    <span style={{ fontFamily: "monospace", fontSize: "15px", fontWeight: 600, color: "#0f172a" }}>
                      {item.file_path}
                    </span>
                    {item.function_name && (
                      <span style={{ marginLeft: "8px", color: "#64748b", fontSize: "13px" }}>
                        ::{item.function_name}()
                      </span>
                    )}
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <span
                      style={{
                        backgroundColor: badgeBg,
                        color: badgeColor,
                        padding: "3px 10px",
                        borderRadius: "12px",
                        fontWeight: 700,
                        fontSize: "12px",
                        textTransform: "uppercase",
                      }}
                    >
                      {item.risk_band} Risk ({(item.risk_probability * 100).toFixed(1)}%)
                    </span>
                  </div>
                </div>

                {/* Progress bar visualizer */}
                <div style={{ width: "100%", height: "6px", backgroundColor: "#f1f5f9", borderRadius: "3px", overflow: "hidden", marginBottom: "12px" }}>
                  <div
                    style={{
                      width: `${Math.min(100, item.risk_probability * 100)}%`,
                      height: "100%",
                      backgroundColor: isHigh ? "#ef4444" : isMedium ? "#f97316" : "#22c55e",
                    }}
                  />
                </div>

                {/* Top Contributing Features from SHAP */}
                {item.top_features && item.top_features.length > 0 && (
                  <div>
                    <span style={{ fontSize: "12px", fontWeight: 600, color: "#64748b", textTransform: "uppercase" }}>
                      Top Feature Drivers (SHAP):
                    </span>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "6px" }}>
                      {item.top_features.map((feat) => (
                        <span
                          key={feat.feature}
                          title={feat.description}
                          style={{
                            backgroundColor: "#f8fafc",
                            border: "1px solid #e2e8f0",
                            borderRadius: "4px",
                            padding: "2px 8px",
                            fontSize: "12px",
                            color: "#334155",
                          }}
                        >
                          <strong>{feat.feature}</strong>: {feat.value}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

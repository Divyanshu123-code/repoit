import React, { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchRepository,
  fetchRepositoryGraph,
  fetchChangeImpact,
  fetchStaticFindings,
  triggerStaticScan,
  triggerRebuildGraph,
} from "../api/client";

export const GraphAnalysisPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  // Active view: "graph" | "findings"
  const [activeTab, setActiveTab] = useState<"graph" | "findings">("graph");

  // Graph state
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [maxDepth, setMaxDepth] = useState<number>(3);
  const [includeChanged, setIncludeChanged] = useState<boolean>(false);
  const [nodeSearch, setNodeSearch] = useState<string>("");

  // Findings state
  const [severityFilter, setSeverityFilter] = useState<string>("");
  const [findingsSearch, setFindingsSearch] = useState<string>("");
  const [triageStatusFilter, setTriageStatusFilter] = useState<string>("all");
  // Local triage status map: finding.id -> "active" | "ignored" | "resolved"
  const [triageMap, setTriageMap] = useState<Record<string, string>>({});

  // 1. Fetch Repository metadata
  const { data: repo, isLoading: repoLoading } = useQuery({
    queryKey: ["repository", id],
    queryFn: () => fetchRepository(id!),
    enabled: !!id,
  });

  // 2. Fetch Dependency Graph
  const {
    data: graphData,
    isLoading: graphLoading,
  } = useQuery({
    queryKey: ["repository-graph", id],
    queryFn: () => fetchRepositoryGraph(id!, true),
    enabled: !!id,
  });

  // 3. Fetch Change Impact when a node is selected
  const {
    data: impactData,
    isLoading: impactLoading,
  } = useQuery({
    queryKey: ["change-impact", id, selectedNode, maxDepth, includeChanged],
    queryFn: () =>
      fetchChangeImpact(id!, [selectedNode!], maxDepth, includeChanged),
    enabled: !!id && !!selectedNode,
  });

  // 4. Fetch Static Findings
  const {
    data: findingsData,
    isLoading: findingsLoading,
  } = useQuery({
    queryKey: ["static-findings", id, severityFilter],
    queryFn: () => fetchStaticFindings(id!, severityFilter || undefined),
    enabled: !!id,
  });

  // Mutations
  const rebuildGraphMutation = useMutation({
    mutationFn: () => triggerRebuildGraph(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["repository-graph", id] });
    },
  });

  const scanStaticMutation = useMutation({
    mutationFn: () => triggerStaticScan(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["static-findings", id] });
    },
  });

  if (repoLoading || !repo) {
    return (
      <div style={{ padding: "2rem", maxWidth: "1280px", margin: "0 auto" }}>
        <p style={{ color: "#64748b" }}>Loading repository data...</p>
      </div>
    );
  }

  // Filter nodes for selector
  const filteredNodes = (graphData?.nodes || []).filter((n) =>
    n.file_path.toLowerCase().includes(nodeSearch.toLowerCase())
  );

  // Filter findings
  const filteredFindings = (findingsData?.findings || []).filter((f) => {
    const matchesSearch =
      findingsSearch === "" ||
      f.rule.toLowerCase().includes(findingsSearch.toLowerCase()) ||
      f.file_path.toLowerCase().includes(findingsSearch.toLowerCase()) ||
      f.message.toLowerCase().includes(findingsSearch.toLowerCase());

    const currentStatus = triageMap[f.id] || "active";
    const matchesTriage =
      triageStatusFilter === "all" || currentStatus === triageStatusFilter;

    return matchesSearch && matchesTriage;
  });

  const handleTriageChange = (findingId: string, newStatus: string) => {
    setTriageMap((prev) => ({ ...prev, [findingId]: newStatus }));
  };

  return (
    <div style={{ maxWidth: "1280px", margin: "0 auto", padding: "2rem 1.5rem" }}>
      {/* Breadcrumb */}
      <div style={{ marginBottom: "1rem" }}>
        <Link
          to={`/repositories/${repo.id}`}
          style={{
            color: "#2563eb",
            textDecoration: "none",
            fontSize: "0.9rem",
            fontWeight: 500,
          }}
        >
          ← Back to {repo.full_name} Overview
        </Link>
      </div>

      {/* Header Banner */}
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
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.35rem" }}>
            <h1 style={{ fontSize: "1.6rem", fontWeight: 700, margin: 0, color: "#0f172a" }}>
              Graph & Static Analysis
            </h1>
            <span
              style={{
                backgroundColor: "#ecfdf5",
                color: "#065f46",
                fontSize: "0.75rem",
                fontWeight: 600,
                padding: "0.2rem 0.6rem",
                borderRadius: "4px",
                border: "1px solid #a7f3d0",
              }}
            >
              source: graph_derived
            </span>
            <span
              style={{
                backgroundColor: "#eff6ff",
                color: "#1e40af",
                fontSize: "0.75rem",
                fontWeight: 600,
                padding: "0.2rem 0.6rem",
                borderRadius: "4px",
                border: "1px solid #bfdbfe",
              }}
            >
              source: static
            </span>
          </div>
          <p style={{ margin: 0, color: "#64748b", fontSize: "0.9rem" }}>
            NetworkX dependency topology, reverse reachability change impact analysis, and Ruff static findings.
          </p>
        </div>

        <div style={{ display: "flex", gap: "0.75rem" }}>
          {activeTab === "graph" ? (
            <button
              onClick={() => rebuildGraphMutation.mutate()}
              disabled={rebuildGraphMutation.isPending}
              style={{
                backgroundColor: "#2563eb",
                color: "#ffffff",
                border: "none",
                padding: "0.5rem 1rem",
                borderRadius: "6px",
                fontWeight: 600,
                fontSize: "0.85rem",
                cursor: rebuildGraphMutation.isPending ? "not-allowed" : "pointer",
              }}
            >
              {rebuildGraphMutation.isPending ? "Rebuilding..." : "🔄 Rebuild Graph"}
            </button>
          ) : (
            <button
              onClick={() => scanStaticMutation.mutate()}
              disabled={scanStaticMutation.isPending}
              style={{
                backgroundColor: "#2563eb",
                color: "#ffffff",
                border: "none",
                padding: "0.5rem 1rem",
                borderRadius: "6px",
                fontWeight: 600,
                fontSize: "0.85rem",
                cursor: scanStaticMutation.isPending ? "not-allowed" : "pointer",
              }}
            >
              {scanStaticMutation.isPending ? "Scanning..." : "🔍 Run Static Scan"}
            </button>
          )}
        </div>
      </div>

      {/* Main Tab Navigation */}
      <div style={{ display: "flex", gap: "1rem", borderBottom: "2px solid #e2e8f0", marginBottom: "1.5rem" }}>
        <button
          onClick={() => setActiveTab("graph")}
          style={{
            background: "none",
            border: "none",
            padding: "0.75rem 1.25rem",
            fontWeight: 600,
            fontSize: "1rem",
            cursor: "pointer",
            color: activeTab === "graph" ? "#2563eb" : "#64748b",
            borderBottom: activeTab === "graph" ? "3px solid #2563eb" : "3px solid transparent",
            marginBottom: "-2px",
          }}
        >
          🕸️ Dependency Graph & Impact Analysis
        </button>
        <button
          onClick={() => setActiveTab("findings")}
          style={{
            background: "none",
            border: "none",
            padding: "0.75rem 1.25rem",
            fontWeight: 600,
            fontSize: "1rem",
            cursor: "pointer",
            color: activeTab === "findings" ? "#2563eb" : "#64748b",
            borderBottom: activeTab === "findings" ? "3px solid #2563eb" : "3px solid transparent",
            marginBottom: "-2px",
          }}
        >
          📋 Static Findings (Ruff)
          {findingsData && (
            <span
              style={{
                marginLeft: "0.5rem",
                backgroundColor: "#f1f5f9",
                color: "#475569",
                padding: "0.15rem 0.5rem",
                borderRadius: "9999px",
                fontSize: "0.75rem",
              }}
            >
              {findingsData.summary.total_findings}
            </span>
          )}
        </button>
      </div>

      {/* TAB 1: GRAPH & IMPACT ANALYSIS */}
      {activeTab === "graph" && (
        <div>
          {/* Graph KPI Summary Cards */}
          {graphData && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                gap: "1rem",
                marginBottom: "1.5rem",
              }}
            >
              <div
                style={{
                  backgroundColor: "#ffffff",
                  padding: "1.25rem",
                  borderRadius: "8px",
                  border: "1px solid #e2e8f0",
                }}
              >
                <div style={{ color: "#64748b", fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase" }}>
                  Indexed Modules
                </div>
                <div style={{ fontSize: "1.8rem", fontWeight: 700, color: "#0f172a", marginTop: "0.25rem" }}>
                  {graphData.summary.total_nodes}
                </div>
              </div>

              <div
                style={{
                  backgroundColor: "#ffffff",
                  padding: "1.25rem",
                  borderRadius: "8px",
                  border: "1px solid #e2e8f0",
                }}
              >
                <div style={{ color: "#64748b", fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase" }}>
                  Internal Edges
                </div>
                <div style={{ fontSize: "1.8rem", fontWeight: 700, color: "#2563eb", marginTop: "0.25rem" }}>
                  {graphData.summary.internal_edges_count}
                </div>
              </div>

              <div
                style={{
                  backgroundColor: "#ffffff",
                  padding: "1.25rem",
                  borderRadius: "8px",
                  border: "1px solid #e2e8f0",
                }}
              >
                <div style={{ color: "#64748b", fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase" }}>
                  Structure / Cycles
                </div>
                <div style={{ fontSize: "1.2rem", fontWeight: 700, color: graphData.summary.is_dag ? "#059669" : "#dc2626", marginTop: "0.5rem" }}>
                  {graphData.summary.is_dag ? "✓ Strict DAG (0 cycles)" : `⚠️ ${graphData.summary.cycles_count} cycle(s)`}
                </div>
              </div>

              <div
                style={{
                  backgroundColor: "#ffffff",
                  padding: "1.25rem",
                  borderRadius: "8px",
                  border: "1px solid #e2e8f0",
                }}
              >
                <div style={{ color: "#64748b", fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase" }}>
                  Graph Density
                </div>
                <div style={{ fontSize: "1.8rem", fontWeight: 700, color: "#7c3aed", marginTop: "0.25rem" }}>
                  {(graphData.summary.density * 100).toFixed(1)}%
                </div>
              </div>
            </div>
          )}

          {/* Interactive Split View: Left (Node Selection) | Right (Impact Blast Radius) */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1.3fr", gap: "1.5rem" }}>
            {/* Left Column: Module Nodes */}
            <div
              style={{
                backgroundColor: "#ffffff",
                borderRadius: "8px",
                border: "1px solid #e2e8f0",
                padding: "1.25rem",
                display: "flex",
                flexDirection: "column",
                height: "650px",
              }}
            >
              <div style={{ marginBottom: "1rem" }}>
                <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "1.1rem", fontWeight: 700, color: "#0f172a" }}>
                  Repository Modules
                </h3>
                <p style={{ margin: "0 0 0.75rem 0", color: "#64748b", fontSize: "0.85rem" }}>
                  Select a module to simulate modifications and compute its downstream affected set.
                </p>
                <input
                  type="text"
                  placeholder="Filter modules by path..."
                  value={nodeSearch}
                  onChange={(e) => setNodeSearch(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "0.5rem 0.75rem",
                    borderRadius: "6px",
                    border: "1px solid #cbd5e1",
                    fontSize: "0.85rem",
                    boxSizing: "border-box",
                  }}
                />
              </div>

              <div style={{ flex: 1, overflowY: "auto", borderTop: "1px solid #f1f5f9" }}>
                {graphLoading ? (
                  <p style={{ color: "#64748b", padding: "1rem", textAlign: "center" }}>Loading graph...</p>
                ) : filteredNodes.length === 0 ? (
                  <p style={{ color: "#94a3b8", padding: "1rem", textAlign: "center" }}>No modules found.</p>
                ) : (
                  filteredNodes.map((node) => {
                    const isSelected = selectedNode === node.file_path;
                    return (
                      <div
                        key={node.id}
                        onClick={() => setSelectedNode(node.file_path)}
                        style={{
                          padding: "0.75rem",
                          borderBottom: "1px solid #f1f5f9",
                          cursor: "pointer",
                          backgroundColor: isSelected ? "#eff6ff" : "transparent",
                          borderLeft: isSelected ? "4px solid #2563eb" : "4px solid transparent",
                          transition: "background-color 0.15s ease",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span
                            style={{
                              fontFamily: "monospace",
                              fontSize: "0.85rem",
                              fontWeight: isSelected ? 700 : 500,
                              color: isSelected ? "#1d4ed8" : "#1e293b",
                            }}
                          >
                            {node.file_path}
                          </span>
                          <div style={{ display: "flex", gap: "0.4rem" }}>
                            <span
                              title="Fan-in: modules importing this file"
                              style={{
                                fontSize: "0.75rem",
                                padding: "0.15rem 0.4rem",
                                borderRadius: "4px",
                                backgroundColor: node.in_degree > 0 ? "#fef3c7" : "#f1f5f9",
                                color: node.in_degree > 0 ? "#92400e" : "#64748b",
                                fontWeight: 600,
                              }}
                            >
                              in: {node.in_degree}
                            </span>
                            <span
                              title="Fan-out: modules this file imports"
                              style={{
                                fontSize: "0.75rem",
                                padding: "0.15rem 0.4rem",
                                borderRadius: "4px",
                                backgroundColor: "#f1f5f9",
                                color: "#64748b",
                                fontWeight: 500,
                              }}
                            >
                              out: {node.out_degree}
                            </span>
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* Right Column: Affected Set (Impact Blast Radius) */}
            <div
              style={{
                backgroundColor: "#ffffff",
                borderRadius: "8px",
                border: "1px solid #e2e8f0",
                padding: "1.25rem",
                display: "flex",
                flexDirection: "column",
                height: "650px",
              }}
            >
              <div style={{ borderBottom: "1px solid #f1f5f9", paddingBottom: "1rem", marginBottom: "1rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                  <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: "#0f172a" }}>
                    Impact Analysis (Blast Radius)
                  </h3>
                  <span
                    style={{
                      fontSize: "0.75rem",
                      fontWeight: 600,
                      backgroundColor: "#f1f5f9",
                      color: "#475569",
                      padding: "0.15rem 0.5rem",
                      borderRadius: "4px",
                    }}
                  >
                    source: graph_derived
                  </span>
                </div>

                {selectedNode ? (
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
                      <span style={{ fontSize: "0.85rem", color: "#64748b" }}>Simulating change in:</span>
                      <code
                        style={{
                          backgroundColor: "#fef3c7",
                          color: "#92400e",
                          padding: "0.2rem 0.5rem",
                          borderRadius: "4px",
                          fontWeight: 700,
                          fontSize: "0.85rem",
                        }}
                      >
                        {selectedNode}
                      </code>
                    </div>

                    {/* Depth Limit Selector */}
                    <div style={{ display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                        <label style={{ fontSize: "0.85rem", fontWeight: 600, color: "#334155" }}>Max Depth:</label>
                        {[1, 2, 3, 5].map((d) => (
                          <button
                            key={d}
                            onClick={() => setMaxDepth(d)}
                            style={{
                              padding: "0.25rem 0.6rem",
                              borderRadius: "4px",
                              border: "1px solid",
                              borderColor: maxDepth === d ? "#2563eb" : "#cbd5e1",
                              backgroundColor: maxDepth === d ? "#eff6ff" : "#ffffff",
                              color: maxDepth === d ? "#1d4ed8" : "#475569",
                              fontSize: "0.8rem",
                              fontWeight: 600,
                              cursor: "pointer",
                            }}
                          >
                            {d} {d === 1 ? "(direct)" : ""}
                          </button>
                        ))}
                      </div>

                      <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.8rem", color: "#64748b", cursor: "pointer" }}>
                        <input
                          type="checkbox"
                          checked={includeChanged}
                          onChange={(e) => setIncludeChanged(e.target.checked)}
                        />
                        Include seed (depth 0)
                      </label>
                    </div>
                  </div>
                ) : (
                  <p style={{ margin: 0, color: "#64748b", fontSize: "0.85rem" }}>
                    Select any file on the left to inspect which upstream modules would break or require testing upon modification.
                  </p>
                )}
              </div>

              {/* Impact Results Area */}
              <div style={{ flex: 1, overflowY: "auto" }}>
                {!selectedNode ? (
                  <div style={{ textAlign: "center", padding: "3rem 1rem", color: "#94a3b8" }}>
                    <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem" }}>🔍</div>
                    <div style={{ fontWeight: 600, fontSize: "0.95rem", color: "#475569" }}>
                      No Module Selected
                    </div>
                    <p style={{ fontSize: "0.85rem", maxWidth: "350px", margin: "0.5rem auto 0 auto" }}>
                      Click on any file in the left panel to run reverse reachability analysis across import edges.
                    </p>
                  </div>
                ) : impactLoading ? (
                  <p style={{ color: "#64748b", padding: "2rem", textAlign: "center" }}>
                    Computing reverse reachability impact...
                  </p>
                ) : impactData ? (
                  <div>
                    {/* Blast Radius KPI Bar */}
                    <div
                      style={{
                        backgroundColor: "#f8fafc",
                        padding: "0.75rem 1rem",
                        borderRadius: "6px",
                        marginBottom: "1rem",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <div>
                        <span style={{ fontSize: "0.85rem", color: "#64748b" }}>Total Affected: </span>
                        <strong style={{ fontSize: "1rem", color: "#0f172a" }}>
                          {impactData.total_affected_count} module(s)
                        </strong>
                        <span style={{ fontSize: "0.8rem", color: "#94a3b8", marginLeft: "0.5rem" }}>
                          ({(impactData.impact_ratio * 100).toFixed(1)}% of repo)
                        </span>
                      </div>
                      <div style={{ display: "flex", gap: "0.5rem", fontSize: "0.8rem" }}>
                        <span style={{ backgroundColor: "#e0f2fe", color: "#0369a1", padding: "0.15rem 0.4rem", borderRadius: "4px" }}>
                          Direct: {impactData.direct_affected_count}
                        </span>
                        <span style={{ backgroundColor: "#f3e8ff", color: "#7e22ce", padding: "0.15rem 0.4rem", borderRadius: "4px" }}>
                          Transitive: {impactData.transitive_affected_count}
                        </span>
                      </div>
                    </div>

                    {impactData.affected_files.length === 0 ? (
                      <div style={{ textAlign: "center", padding: "2rem", color: "#64748b" }}>
                        <p style={{ margin: 0, fontWeight: 600 }}>Zero Downstream Consumers</p>
                        <p style={{ fontSize: "0.85rem", color: "#94a3b8", marginTop: "0.25rem" }}>
                          No other internal module imports this file. Changes here have an isolated blast radius.
                        </p>
                      </div>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                        {impactData.affected_files.map((file) => (
                          <div
                            key={file.file_path}
                            style={{
                              border: "1px solid #e2e8f0",
                              borderRadius: "6px",
                              padding: "0.75rem",
                              backgroundColor: file.depth === 1 ? "#faf5ff" : "#ffffff",
                            }}
                          >
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.35rem" }}>
                              <span style={{ fontFamily: "monospace", fontSize: "0.85rem", fontWeight: 700, color: "#1e293b" }}>
                                {file.file_path}
                              </span>
                              <div style={{ display: "flex", gap: "0.4rem" }}>
                                <span
                                  style={{
                                    fontSize: "0.75rem",
                                    fontWeight: 700,
                                    padding: "0.1rem 0.45rem",
                                    borderRadius: "4px",
                                    backgroundColor:
                                      file.impact_tier === "changed"
                                        ? "#fef3c7"
                                        : file.impact_tier === "direct"
                                        ? "#e0e7ff"
                                        : "#f3e8ff",
                                    color:
                                      file.impact_tier === "changed"
                                        ? "#92400e"
                                        : file.impact_tier === "direct"
                                        ? "#3730a3"
                                        : "#6b21a8",
                                  }}
                                >
                                  {file.impact_tier} (depth {file.depth})
                                </span>
                              </div>
                            </div>

                            {/* Dependency Path / Chain */}
                            <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: "0.3rem" }}>
                              <span style={{ fontWeight: 600 }}>Path: </span>
                              {file.dependency_chain.map((step, idx) => (
                                <span key={idx}>
                                  <code style={{ backgroundColor: "#f1f5f9", padding: "0.1rem 0.3rem", borderRadius: "3px" }}>
                                    {step}
                                  </code>
                                  {idx < file.dependency_chain.length - 1 && " → "}
                                </span>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: STATIC FINDINGS TABLE WITH TRIAGE FILTER */}
      {activeTab === "findings" && (
        <div>
          {/* Findings KPI Summary Cards */}
          {findingsData && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                gap: "1rem",
                marginBottom: "1.5rem",
              }}
            >
              <div
                style={{
                  backgroundColor: "#ffffff",
                  padding: "1.25rem",
                  borderRadius: "8px",
                  border: "1px solid #e2e8f0",
                }}
              >
                <div style={{ color: "#64748b", fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase" }}>
                  Total Findings
                </div>
                <div style={{ fontSize: "1.8rem", fontWeight: 700, color: "#0f172a", marginTop: "0.25rem" }}>
                  {findingsData.summary.total_findings}
                </div>
              </div>

              <div
                style={{
                  backgroundColor: "#ffffff",
                  padding: "1.25rem",
                  borderRadius: "8px",
                  border: "1px solid #fee2e2",
                }}
              >
                <div style={{ color: "#991b1b", fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase" }}>
                  Errors (Security / Syntax)
                </div>
                <div style={{ fontSize: "1.8rem", fontWeight: 700, color: "#b91c1c", marginTop: "0.25rem" }}>
                  {findingsData.summary.error_count}
                </div>
              </div>

              <div
                style={{
                  backgroundColor: "#ffffff",
                  padding: "1.25rem",
                  borderRadius: "8px",
                  border: "1px solid #fef3c7",
                }}
              >
                <div style={{ color: "#92400e", fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase" }}>
                  Warnings (Bug Risk / Style)
                </div>
                <div style={{ fontSize: "1.8rem", fontWeight: 700, color: "#d97706", marginTop: "0.25rem" }}>
                  {findingsData.summary.warning_count}
                </div>
              </div>

              <div
                style={{
                  backgroundColor: "#ffffff",
                  padding: "1.25rem",
                  borderRadius: "8px",
                  border: "1px solid #e0f2fe",
                }}
              >
                <div style={{ color: "#075985", fontSize: "0.8rem", fontWeight: 600, textTransform: "uppercase" }}>
                  Info (Hints / Unused)
                </div>
                <div style={{ fontSize: "1.8rem", fontWeight: 700, color: "#0284c7", marginTop: "0.25rem" }}>
                  {findingsData.summary.info_count}
                </div>
              </div>
            </div>
          )}

          {/* Triage Filter Bar */}
          <div
            style={{
              backgroundColor: "#ffffff",
              padding: "1rem 1.25rem",
              borderRadius: "8px",
              border: "1px solid #e2e8f0",
              marginBottom: "1.5rem",
              display: "flex",
              flexWrap: "wrap",
              gap: "1rem",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            {/* Severity Tabs */}
            <div style={{ display: "flex", gap: "0.5rem" }}>
              {[
                { label: "All Severities", value: "" },
                { label: "Errors", value: "error" },
                { label: "Warnings", value: "warning" },
                { label: "Info", value: "info" },
              ].map((tab) => (
                <button
                  key={tab.value}
                  onClick={() => setSeverityFilter(tab.value)}
                  style={{
                    padding: "0.4rem 0.8rem",
                    borderRadius: "6px",
                    border: "1px solid",
                    borderColor: severityFilter === tab.value ? "#2563eb" : "#cbd5e1",
                    backgroundColor: severityFilter === tab.value ? "#eff6ff" : "#ffffff",
                    color: severityFilter === tab.value ? "#1d4ed8" : "#475569",
                    fontWeight: 600,
                    fontSize: "0.85rem",
                    cursor: "pointer",
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Triage Status & Search Filter */}
            <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
              <select
                value={triageStatusFilter}
                onChange={(e) => setTriageStatusFilter(e.target.value)}
                style={{
                  padding: "0.45rem 0.75rem",
                  borderRadius: "6px",
                  border: "1px solid #cbd5e1",
                  fontSize: "0.85rem",
                  backgroundColor: "#ffffff",
                  color: "#334155",
                }}
              >
                <option value="all">All Triage Statuses</option>
                <option value="active">Active (Unresolved)</option>
                <option value="ignored">Ignored</option>
                <option value="resolved">Resolved</option>
              </select>

              <input
                type="text"
                placeholder="Search rule, path, or message..."
                value={findingsSearch}
                onChange={(e) => setFindingsSearch(e.target.value)}
                style={{
                  padding: "0.45rem 0.75rem",
                  borderRadius: "6px",
                  border: "1px solid #cbd5e1",
                  fontSize: "0.85rem",
                  width: "260px",
                }}
              />
            </div>
          </div>

          {/* Findings Table */}
          <div
            style={{
              backgroundColor: "#ffffff",
              borderRadius: "8px",
              border: "1px solid #e2e8f0",
              overflow: "hidden",
            }}
          >
            {findingsLoading ? (
              <p style={{ padding: "2rem", color: "#64748b", textAlign: "center" }}>Loading static findings...</p>
            ) : filteredFindings.length === 0 ? (
              <div style={{ textAlign: "center", padding: "3rem 1rem", color: "#64748b" }}>
                <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>✨</div>
                <div style={{ fontWeight: 600, fontSize: "1rem" }}>No findings match your filter</div>
                <p style={{ fontSize: "0.85rem", color: "#94a3b8" }}>
                  Change severity or search terms, or run a new scan.
                </p>
              </div>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
                <thead>
                  <tr style={{ backgroundColor: "#f8fafc", borderBottom: "1px solid #e2e8f0" }}>
                    <th style={{ padding: "0.75rem 1rem", fontSize: "0.8rem", color: "#64748b", fontWeight: 600 }}>
                      SEVERITY
                    </th>
                    <th style={{ padding: "0.75rem 1rem", fontSize: "0.8rem", color: "#64748b", fontWeight: 600 }}>
                      RULE / CATEGORY
                    </th>
                    <th style={{ padding: "0.75rem 1rem", fontSize: "0.8rem", color: "#64748b", fontWeight: 600 }}>
                      LOCATION
                    </th>
                    <th style={{ padding: "0.75rem 1rem", fontSize: "0.8rem", color: "#64748b", fontWeight: 600 }}>
                      DESCRIPTION & FIX
                    </th>
                    <th style={{ padding: "0.75rem 1rem", fontSize: "0.8rem", color: "#64748b", fontWeight: 600 }}>
                      TRIAGE
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filteredFindings.map((finding) => {
                    const status = triageMap[finding.id] || "active";
                    const isError = finding.severity === "error";
                    const isWarning = finding.severity === "warning";

                    return (
                      <tr
                        key={finding.id}
                        style={{
                          borderBottom: "1px solid #f1f5f9",
                          opacity: status === "ignored" ? 0.6 : 1,
                        }}
                      >
                        {/* Severity */}
                        <td style={{ padding: "1rem", verticalAlign: "top" }}>
                          <span
                            style={{
                              display: "inline-block",
                              padding: "0.2rem 0.55rem",
                              borderRadius: "4px",
                              fontSize: "0.75rem",
                              fontWeight: 700,
                              textTransform: "uppercase",
                              backgroundColor: isError ? "#fee2e2" : isWarning ? "#fef3c7" : "#e0f2fe",
                              color: isError ? "#991b1b" : isWarning ? "#92400e" : "#0369a1",
                            }}
                          >
                            {finding.severity}
                          </span>
                        </td>

                        {/* Rule & Category */}
                        <td style={{ padding: "1rem", verticalAlign: "top" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                            {finding.rule_url ? (
                              <a
                                href={finding.rule_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{
                                  fontFamily: "monospace",
                                  fontWeight: 700,
                                  color: "#2563eb",
                                  textDecoration: "none",
                                }}
                              >
                                {finding.rule} ↗
                              </a>
                            ) : (
                              <code style={{ fontWeight: 700, color: "#1e293b" }}>{finding.rule}</code>
                            )}
                          </div>
                          <span
                            style={{
                              fontSize: "0.75rem",
                              color: "#64748b",
                              display: "block",
                              marginTop: "0.25rem",
                            }}
                          >
                            {finding.category}
                          </span>
                        </td>

                        {/* Location */}
                        <td style={{ padding: "1rem", verticalAlign: "top" }}>
                          <code style={{ fontSize: "0.85rem", color: "#334155" }}>
                            {finding.file_path}:{finding.line_number}
                          </code>
                          <span
                            style={{
                              display: "block",
                              fontSize: "0.7rem",
                              color: "#94a3b8",
                              marginTop: "0.15rem",
                            }}
                          >
                            source: {finding.source}
                          </span>
                        </td>

                        {/* Message & Fix */}
                        <td style={{ padding: "1rem", verticalAlign: "top", maxWidth: "450px" }}>
                          <div style={{ fontSize: "0.9rem", color: "#1e293b", fontWeight: 500 }}>
                            {finding.message}
                          </div>
                          {finding.fix_suggested && (
                            <div
                              style={{
                                marginTop: "0.4rem",
                                padding: "0.4rem 0.6rem",
                                backgroundColor: "#f0fdf4",
                                border: "1px solid #bbf7d0",
                                borderRadius: "4px",
                                fontSize: "0.8rem",
                                color: "#166534",
                                fontFamily: "monospace",
                              }}
                            >
                              💡 Fix: {finding.fix_suggested}
                            </div>
                          )}
                        </td>

                        {/* Triage Action */}
                        <td style={{ padding: "1rem", verticalAlign: "top" }}>
                          <select
                            value={status}
                            onChange={(e) => handleTriageChange(finding.id, e.target.value)}
                            style={{
                              padding: "0.3rem 0.5rem",
                              borderRadius: "4px",
                              border: "1px solid #cbd5e1",
                              fontSize: "0.8rem",
                              fontWeight: 600,
                              backgroundColor:
                                status === "active"
                                  ? "#ffffff"
                                  : status === "ignored"
                                  ? "#f1f5f9"
                                  : "#ecfdf5",
                              color:
                                status === "active"
                                  ? "#334155"
                                  : status === "ignored"
                                  ? "#64748b"
                                  : "#047857",
                            }}
                          >
                            <option value="active">Active</option>
                            <option value="ignored">Ignore</option>
                            <option value="resolved">Resolved</option>
                          </select>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

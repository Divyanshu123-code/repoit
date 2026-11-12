import React from "react";
import { Routes, Route, Link, Navigate } from "react-router-dom";
import { HealthPage } from "./pages/HealthPage";
import { RepositoriesPage } from "./pages/RepositoriesPage";
import { RepoOverviewPage } from "./pages/RepoOverviewPage";
import { RepoChatPage } from "./pages/RepoChatPage";
import { DefectRiskPage } from "./pages/DefectRiskPage";
import { GraphAnalysisPage } from "./pages/GraphAnalysisPage";

export const App: React.FC = () => {
  return (
    <div style={{ minHeight: "100vh", backgroundColor: "#f8fafc", color: "#0f172a" }}>
      {/* Top Header */}
      <header
        style={{
          borderBottom: "1px solid #e2e8f0",
          backgroundColor: "#ffffff",
          padding: "1rem 2rem",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <Link to="/" style={{ textDecoration: "none", fontSize: "1.25rem", fontWeight: 700, color: "#2563eb" }}>
            RepoPilot AI
          </Link>
          <span
            style={{
              backgroundColor: "#e0f2fe",
              color: "#0369a1",
              fontSize: "0.75rem",
              fontWeight: 600,
              padding: "0.15rem 0.5rem",
              borderRadius: "4px",
            }}
          >
            Phase 1
          </span>
        </div>
        <nav style={{ display: "flex", gap: "1.5rem" }}>
          <Link
            to="/"
            style={{
              textDecoration: "none",
              color: "#334155",
              fontWeight: 500,
              fontSize: "0.95rem",
            }}
          >
            Repositories
          </Link>
          <Link
            to="/health"
            style={{
              textDecoration: "none",
              color: "#334155",
              fontWeight: 500,
              fontSize: "0.95rem",
            }}
          >
            Health & Status
          </Link>
        </nav>
      </header>

      {/* Main Content Area */}
      <main>
        <Routes>
          <Route path="/" element={<RepositoriesPage />} />
          <Route path="/repositories/:id" element={<RepoOverviewPage />} />
          <Route path="/repositories/:id/chat" element={<RepoChatPage />} />
          <Route path="/repositories/:id/defect-risk" element={<DefectRiskPage />} />
          <Route path="/repositories/:id/graph" element={<GraphAnalysisPage />} />
          <Route path="/health" element={<HealthPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
};


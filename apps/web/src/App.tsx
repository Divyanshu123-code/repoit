import React from "react";
import { Routes, Route, Link, Navigate } from "react-router-dom";
import { HealthPage } from "./pages/HealthPage";

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
          <span style={{ fontSize: "1.25rem", fontWeight: 700, color: "#2563eb" }}>RepoPilot AI</span>
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
            Phase 0 Shell
          </span>
        </div>
        <nav style={{ display: "flex", gap: "1.5rem" }}>
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
          <Route path="/" element={<Navigate to="/health" replace />} />
          <Route path="/health" element={<HealthPage />} />
          <Route path="*" element={<Navigate to="/health" replace />} />
        </Routes>
      </main>
    </div>
  );
};


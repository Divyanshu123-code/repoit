import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchRepositories, registerRepository, uploadRepositoryZip, Repository } from "../api/client";

export const RepositoriesPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [githubUrl, setGithubUrl] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const { data: repositories, isLoading, error } = useQuery<Repository[]>({
    queryKey: ["repositories"],
    queryFn: fetchRepositories,
    refetchInterval: 5000,
  });

  const registerMutation = useMutation({
    mutationFn: registerRepository,
    onSuccess: (newRepo) => {
      setGithubUrl("");
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ["repositories"] });
      navigate(`/repositories/${newRepo.id}`);
    },
    onError: (err: Error) => {
      setFormError(err.message);
    },
  });

  const uploadMutation = useMutation({
    mutationFn: uploadRepositoryZip,
    onSuccess: (newRepo) => {
      setFormError(null);
      queryClient.invalidateQueries({ queryKey: ["repositories"] });
      navigate(`/repositories/${newRepo.id}`);
    },
    onError: (err: Error) => {
      setFormError(err.message);
    },
  });

  const handleRegisterUrl = (e: React.FormEvent) => {
    e.preventDefault();
    if (!githubUrl.trim()) {
      setFormError("Please enter a GitHub repository URL");
      return;
    }
    setFormError(null);
    registerMutation.mutate(githubUrl.trim());
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFormError(null);
    uploadMutation.mutate(file);
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, { bg: string; text: string; border: string }> = {
      ready: { bg: "#ecfdf5", text: "#047857", border: "#a7f3d0" },
      scanning: { bg: "#eff6ff", text: "#1d4ed8", border: "#bfdbfe" },
      registered: { bg: "#f8fafc", text: "#475569", border: "#cbd5e1" },
      failed: { bg: "#fef2f2", text: "#b91c1c", border: "#fecaca" },
    };
    const c = colors[status] || { bg: "#f8fafc", text: "#475569", border: "#cbd5e1" };
    return (
      <span
        style={{
          display: "inline-block",
          padding: "0.2rem 0.6rem",
          borderRadius: "9999px",
          fontSize: "0.75rem",
          fontWeight: 600,
          textTransform: "uppercase",
          backgroundColor: c.bg,
          color: c.text,
          border: `1px solid ${c.border}`,
        }}
      >
        {status}
      </span>
    );
  };

  return (
    <div style={{ maxWidth: "1100px", margin: "2rem auto", padding: "0 1.5rem" }}>
      {/* Title */}
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: "1.875rem", fontWeight: 700, margin: 0, color: "#0f172a" }}>
          Repository Hub
        </h1>
        <p style={{ color: "#64748b", margin: "0.5rem 0 0" }}>
          Connect a public GitHub repository or upload a ZIP archive for code indexing and defect risk analysis.
        </p>
      </div>

      {/* Registration Card */}
      <div
        style={{
          backgroundColor: "#ffffff",
          borderRadius: "8px",
          padding: "1.5rem",
          boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.1)",
          border: "1px solid #e2e8f0",
          marginBottom: "2rem",
        }}
      >
        <h2 style={{ fontSize: "1.15rem", fontWeight: 600, margin: "0 0 1rem" }}>Register New Repository</h2>

        {formError && (
          <div
            style={{
              padding: "0.75rem 1rem",
              backgroundColor: "#fef2f2",
              color: "#991b1b",
              borderRadius: "6px",
              marginBottom: "1rem",
              fontSize: "0.9rem",
              border: "1px solid #fecaca",
            }}
          >
            {formError}
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2rem" }}>
          {/* GitHub URL form */}
          <div>
            <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, color: "#475569", marginBottom: "0.5rem" }}>
              Public GitHub Repository URL
            </label>
            <form onSubmit={handleRegisterUrl} style={{ display: "flex", gap: "0.5rem" }}>
              <input
                type="text"
                placeholder="https://github.com/psf/requests"
                value={githubUrl}
                onChange={(e) => setGithubUrl(e.target.value)}
                style={{
                  flex: 1,
                  padding: "0.6rem 0.75rem",
                  borderRadius: "6px",
                  border: "1px solid #cbd5e1",
                  fontSize: "0.9rem",
                }}
              />
              <button
                type="submit"
                disabled={registerMutation.isPending}
                style={{
                  backgroundColor: "#2563eb",
                  color: "#ffffff",
                  padding: "0.6rem 1.2rem",
                  borderRadius: "6px",
                  border: "none",
                  fontWeight: 600,
                  fontSize: "0.9rem",
                  cursor: registerMutation.isPending ? "not-allowed" : "pointer",
                }}
              >
                {registerMutation.isPending ? "Registering..." : "Connect"}
              </button>
            </form>
          </div>

          {/* ZIP upload form */}
          <div>
            <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, color: "#475569", marginBottom: "0.5rem" }}>
              Or Upload ZIP Archive
            </label>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <input
                type="file"
                accept=".zip"
                onChange={handleFileUpload}
                disabled={uploadMutation.isPending}
                style={{
                  fontSize: "0.9rem",
                  padding: "0.45rem 0",
                }}
              />
              {uploadMutation.isPending && (
                <span style={{ fontSize: "0.85rem", color: "#64748b" }}>Uploading...</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Repositories List */}
      <div
        style={{
          backgroundColor: "#ffffff",
          borderRadius: "8px",
          boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.1)",
          border: "1px solid #e2e8f0",
          overflow: "hidden",
        }}
      >
        <div style={{ padding: "1rem 1.5rem", borderBottom: "1px solid #e2e8f0" }}>
          <h2 style={{ fontSize: "1.15rem", fontWeight: 600, margin: 0 }}>Registered Repositories</h2>
        </div>

        {isLoading ? (
          <div style={{ padding: "2rem", textAlign: "center", color: "#64748b" }}>Loading repositories...</div>
        ) : error ? (
          <div style={{ padding: "2rem", textAlign: "center", color: "#ef4444" }}>
            Failed to load repositories: {(error as Error).message}
          </div>
        ) : !repositories || repositories.length === 0 ? (
          <div style={{ padding: "3rem", textAlign: "center", color: "#64748b" }}>
            <p style={{ margin: "0 0 0.5rem", fontSize: "1rem" }}>No repositories registered yet.</p>
            <p style={{ margin: 0, fontSize: "0.85rem" }}>Add a public GitHub URL or upload a ZIP archive to get started.</p>
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
            <thead>
              <tr style={{ backgroundColor: "#f8fafc", borderBottom: "1px solid #e2e8f0", fontSize: "0.75rem", textTransform: "uppercase", color: "#64748b" }}>
                <th style={{ padding: "0.75rem 1.5rem" }}>Repository</th>
                <th style={{ padding: "0.75rem 1.5rem" }}>Source</th>
                <th style={{ padding: "0.75rem 1.5rem" }}>Branch</th>
                <th style={{ padding: "0.75rem 1.5rem" }}>Status</th>
                <th style={{ padding: "0.75rem 1.5rem" }}>Last Indexed</th>
                <th style={{ padding: "0.75rem 1.5rem", textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {repositories.map((repo) => (
                <tr
                  key={repo.id}
                  style={{ borderBottom: "1px solid #f1f5f9", fontSize: "0.9rem" }}
                >
                  <td style={{ padding: "1rem 1.5rem", fontWeight: 600, color: "#1e293b" }}>
                    <Link
                      to={`/repositories/${repo.id}`}
                      style={{ color: "#2563eb", textDecoration: "none" }}
                    >
                      {repo.full_name}
                    </Link>
                  </td>
                  <td style={{ padding: "1rem 1.5rem", color: "#64748b" }}>
                    <span style={{ fontSize: "0.8rem", textTransform: "capitalize" }}>{repo.source}</span>
                  </td>
                  <td style={{ padding: "1rem 1.5rem", color: "#64748b", fontFamily: "monospace" }}>
                    {repo.default_branch}
                  </td>
                  <td style={{ padding: "1rem 1.5rem" }}>{getStatusBadge(repo.status)}</td>
                  <td style={{ padding: "1rem 1.5rem", color: "#64748b", fontSize: "0.85rem" }}>
                    {repo.indexed_at ? new Date(repo.indexed_at).toLocaleString() : "Never"}
                  </td>
                  <td style={{ padding: "1rem 1.5rem", textAlign: "right" }}>
                    <Link
                      to={`/repositories/${repo.id}`}
                      style={{
                        backgroundColor: "#f1f5f9",
                        color: "#334155",
                        padding: "0.35rem 0.75rem",
                        borderRadius: "4px",
                        textDecoration: "none",
                        fontSize: "0.85rem",
                        fontWeight: 500,
                      }}
                    >
                      View Overview →
                    </Link>
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

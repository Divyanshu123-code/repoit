import React, { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { fetchRepository, askQuestion, RAGCitation, RAGResponse } from "../api/client";

interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  abstained?: boolean;
  citations?: RAGCitation[];
  source?: string;
  modelVersion?: string;
  timestamp: Date;
}

export const RepoChatPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [question, setQuestion] = useState("");
  const [expandedCitationIds, setExpandedCitationIds] = useState<Record<string, boolean>>({});
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome-1",
      sender: "assistant",
      text: "Hello! I am RepoPilot AI. Ask me anything about this repository's architecture, functions, metrics, or logic. Every statement I provide is grounded in verified citations from the codebase.",
      timestamp: new Date(),
      source: "llm_generated",
      modelVersion: "gpt-4o-mini",
    },
  ]);

  const { data: repo } = useQuery({
    queryKey: ["repository", id],
    queryFn: () => (id ? fetchRepository(id) : Promise.reject("No repo ID")),
    enabled: !!id,
  });

  const askMutation = useMutation({
    mutationFn: async (queryText: string) => {
      if (!id) throw new Error("No repository ID");
      return askQuestion(id, queryText);
    },
    onSuccess: (data: RAGResponse) => {
      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        sender: "assistant",
        text: data.answer,
        abstained: data.abstained,
        citations: data.citations,
        source: data.source,
        modelVersion: data.model_version,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    },
    onError: (err: any) => {
      const errorMessage: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: "assistant",
        text: `Error retrieving answer: ${err.message || "Failed to contact assistant"}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    },
  });

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || askMutation.isPending) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: "user",
      text: trimmed,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setQuestion("");
    askMutation.mutate(trimmed);
  };

  const toggleEvidencePanel = (messageId: string) => {
    setExpandedCitationIds((prev) => ({
      ...prev,
      [messageId]: !prev[messageId],
    }));
  };

  const handleQuickQuestion = (q: string) => {
    setQuestion(q);
  };

  return (
    <div style={{ maxWidth: "1100px", margin: "2rem auto", padding: "0 1.5rem" }}>
      {/* Navigation Header */}
      <div style={{ marginBottom: "1.5rem" }}>
        <Link
          to={`/repositories/${id}`}
          style={{ textDecoration: "none", color: "#2563eb", fontSize: "0.9rem", fontWeight: 500 }}
        >
          ← Back to Repository Overview
        </Link>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: "0.5rem" }}>
          <div>
            <h1 style={{ fontSize: "1.75rem", fontWeight: 700, margin: 0, color: "#0f172a" }}>
              Codebase RAG Assistant
            </h1>
            <p style={{ margin: "0.25rem 0 0 0", color: "#64748b", fontSize: "0.95rem" }}>
              Repository: <strong>{repo?.full_name || id}</strong>
            </p>
          </div>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <span
              style={{
                backgroundColor: "#e0f2fe",
                color: "#0369a1",
                fontSize: "0.75rem",
                fontWeight: 600,
                padding: "0.2rem 0.5rem",
                borderRadius: "4px",
              }}
            >
              source: llm_generated
            </span>
            <span
              style={{
                backgroundColor: "#f1f5f9",
                color: "#475569",
                fontSize: "0.75rem",
                fontWeight: 600,
                padding: "0.2rem 0.5rem",
                borderRadius: "4px",
              }}
            >
              source: static (citations)
            </span>
          </div>
        </div>
      </div>

      {/* Quick Prompts Bar */}
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "1rem" }}>
        <span style={{ fontSize: "0.85rem", color: "#64748b", alignSelf: "center", marginRight: "0.25rem" }}>
          Suggested:
        </span>
        {[
          "How is user authentication implemented?",
          "What database models and connections are configured?",
          "Where is the repository scan worker job defined?",
        ].map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => handleQuickQuestion(q)}
            style={{
              backgroundColor: "#ffffff",
              border: "1px solid #cbd5e1",
              borderRadius: "16px",
              padding: "0.35rem 0.8rem",
              fontSize: "0.8rem",
              color: "#334155",
              cursor: "pointer",
            }}
          >
            {q}
          </button>
        ))}
      </div>

      {/* Chat Messages Container */}
      <div
        style={{
          backgroundColor: "#ffffff",
          borderRadius: "8px",
          border: "1px solid #e2e8f0",
          minHeight: "500px",
          maxHeight: "650px",
          overflowY: "auto",
          padding: "1.5rem",
          display: "flex",
          flexDirection: "column",
          gap: "1.25rem",
        }}
      >
        {messages.map((msg) => (
          <div
            key={msg.id}
            style={{
              alignSelf: msg.sender === "user" ? "flex-end" : "flex-start",
              maxWidth: "85%",
            }}
          >
            {/* Message Bubble */}
            <div
              style={{
                backgroundColor: msg.sender === "user" ? "#2563eb" : "#f8fafc",
                color: msg.sender === "user" ? "#ffffff" : "#0f172a",
                border: msg.sender === "user" ? "none" : "1px solid #e2e8f0",
                borderRadius: "8px",
                padding: "1rem 1.25rem",
                fontSize: "0.95rem",
                lineHeight: "1.5",
              }}
            >
              {/* Abstention Warning Banner */}
              {msg.abstained && (
                <div
                  style={{
                    backgroundColor: "#fef3c7",
                    color: "#92400e",
                    padding: "0.5rem 0.75rem",
                    borderRadius: "4px",
                    fontSize: "0.85rem",
                    fontWeight: 600,
                    marginBottom: "0.75rem",
                    border: "1px solid #fde68a",
                  }}
                >
                  ⚠️ Abstention: Not enough evidence in codebase
                </div>
              )}

              <div style={{ whiteSpace: "pre-wrap" }}>{msg.text}</div>

              {/* Message Metadata Header */}
              {msg.sender === "assistant" && (
                <div
                  style={{
                    marginTop: "0.75rem",
                    paddingTop: "0.5rem",
                    borderTop: "1px solid #e2e8f0",
                    display: "flex",
                    gap: "0.75rem",
                    fontSize: "0.75rem",
                    color: "#64748b",
                  }}
                >
                  {msg.source && (
                    <span style={{ fontWeight: 600, color: "#0284c7" }}>source: {msg.source}</span>
                  )}
                  {msg.modelVersion && <span>model: {msg.modelVersion}</span>}
                </div>
              )}
            </div>

            {/* Expandable Evidence Panel (Acceptance Criteria P2-06) */}
            {msg.citations && msg.citations.length > 0 && (
              <div style={{ marginTop: "0.5rem" }}>
                <button
                  type="button"
                  onClick={() => toggleEvidencePanel(msg.id)}
                  style={{
                    backgroundColor: "transparent",
                    border: "1px solid #cbd5e1",
                    borderRadius: "6px",
                    padding: "0.3rem 0.6rem",
                    fontSize: "0.8rem",
                    color: "#2563eb",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "0.35rem",
                  }}
                >
                  <span>{expandedCitationIds[msg.id] ? "▼ Hide" : "▶ View"} Evidence & Citations ({msg.citations.length})</span>
                </button>

                {expandedCitationIds[msg.id] && (
                  <div
                    style={{
                      marginTop: "0.5rem",
                      display: "flex",
                      flexDirection: "column",
                      gap: "0.75rem",
                    }}
                  >
                    {msg.citations.map((c, idx) => (
                      <div
                        key={idx}
                        style={{
                          backgroundColor: "#f1f5f9",
                          borderRadius: "6px",
                          border: "1px solid #cbd5e1",
                          padding: "0.75rem",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            marginBottom: "0.5rem",
                            fontSize: "0.8rem",
                          }}
                        >
                          <div>
                            <span style={{ fontWeight: 700, color: "#1e293b" }}>{c.file_path}</span>
                            <span style={{ marginLeft: "0.5rem", color: "#64748b" }}>
                              #L{c.start_line}-L{c.end_line}
                            </span>
                            {c.symbol_name && (
                              <span
                                style={{
                                  marginLeft: "0.5rem",
                                  backgroundColor: "#e2e8f0",
                                  padding: "0.1rem 0.35rem",
                                  borderRadius: "4px",
                                  fontSize: "0.75rem",
                                }}
                              >
                                {c.symbol_name}
                              </span>
                            )}
                          </div>
                          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                            <span style={{ color: "#059669", fontWeight: 600 }}>
                              Match: {(c.similarity_score * 100).toFixed(1)}%
                            </span>
                            <span
                              style={{
                                backgroundColor: "#ffffff",
                                color: "#475569",
                                fontSize: "0.7rem",
                                fontWeight: 600,
                                padding: "0.1rem 0.35rem",
                                borderRadius: "4px",
                                border: "1px solid #cbd5e1",
                              }}
                            >
                              source: {c.source}
                            </span>
                          </div>
                        </div>
                        {/* Code Excerpt Box */}
                        <pre
                          style={{
                            backgroundColor: "#0f172a",
                            color: "#f8fafc",
                            padding: "0.6rem 0.75rem",
                            borderRadius: "4px",
                            fontSize: "0.8rem",
                            overflowX: "auto",
                            margin: 0,
                            fontFamily: "monospace",
                          }}
                        >
                          {c.content}
                        </pre>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {askMutation.isPending && (
          <div style={{ alignSelf: "flex-start", color: "#64748b", fontSize: "0.9rem" }}>
            Searching codebase and synthesizing verified answer...
          </div>
        )}
      </div>

      {/* Input Field and Send Button */}
      <form onSubmit={handleSend} style={{ display: "flex", gap: "0.75rem", marginTop: "1rem" }}>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about this repository's codebase..."
          disabled={askMutation.isPending}
          style={{
            flex: 1,
            padding: "0.75rem 1rem",
            fontSize: "0.95rem",
            border: "1px solid #cbd5e1",
            borderRadius: "6px",
          }}
        />
        <button
          type="submit"
          disabled={!question.trim() || askMutation.isPending}
          style={{
            backgroundColor: !question.trim() || askMutation.isPending ? "#94a3b8" : "#2563eb",
            color: "#ffffff",
            border: "none",
            borderRadius: "6px",
            padding: "0.75rem 1.5rem",
            fontSize: "0.95rem",
            fontWeight: 600,
            cursor: !question.trim() || askMutation.isPending ? "not-allowed" : "pointer",
          }}
        >
          {askMutation.isPending ? "Thinking..." : "Ask Assistant"}
        </button>
      </form>
    </div>
  );
};

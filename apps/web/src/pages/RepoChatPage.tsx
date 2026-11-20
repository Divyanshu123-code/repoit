import React, { useState, useEffect, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchRepository,
  createChatSession,
  listChatSessions,
  fetchChatSession,
  sendChatMessage,
  deleteChatSession,
  ChatSessionItem,
} from "../api/client";

// ---------------------------------------------------------------------------
// Zero-dependency Lightweight Markdown Renderer
// ---------------------------------------------------------------------------

const MarkdownContent: React.FC<{ content: string }> = ({ content }) => {
  const lines = content.split("\n");
  const renderedElements: React.ReactNode[] = [];

  let inCodeBlock = false;
  let codeBlockLines: string[] = [];
  let codeBlockLang = "";

  lines.forEach((line, index) => {
    // Code block boundary
    if (line.trim().startsWith("```")) {
      if (inCodeBlock) {
        renderedElements.push(
          <div
            key={`code-${index}`}
            style={{
              backgroundColor: "#0f172a",
              color: "#e2e8f0",
              borderRadius: "6px",
              padding: "0.85rem 1rem",
              margin: "0.6rem 0",
              fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
              fontSize: "0.85rem",
              overflowX: "auto",
              border: "1px solid #1e293b",
            }}
          >
            {codeBlockLang && (
              <div
                style={{
                  fontSize: "0.7rem",
                  color: "#94a3b8",
                  textTransform: "uppercase",
                  marginBottom: "0.4rem",
                  borderBottom: "1px solid #334155",
                  paddingBottom: "0.2rem",
                }}
              >
                {codeBlockLang}
              </div>
            )}
            <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
              {codeBlockLines.join("\n")}
            </pre>
          </div>
        );
        codeBlockLines = [];
        inCodeBlock = false;
        codeBlockLang = "";
      } else {
        inCodeBlock = true;
        codeBlockLang = line.trim().slice(3).trim();
        codeBlockLines = [];
      }
      return;
    }

    if (inCodeBlock) {
      codeBlockLines.push(line);
      return;
    }

    // Headers
    if (line.startsWith("#### ")) {
      renderedElements.push(
        <h5 key={index} style={{ fontSize: "0.95rem", fontWeight: 700, margin: "0.6rem 0 0.2rem 0", color: "#0f172a" }}>
          {renderInlineStyles(line.slice(5))}
        </h5>
      );
      return;
    }
    if (line.startsWith("### ")) {
      renderedElements.push(
        <h4 key={index} style={{ fontSize: "1.05rem", fontWeight: 700, margin: "0.8rem 0 0.3rem 0", color: "#0f172a" }}>
          {renderInlineStyles(line.slice(4))}
        </h4>
      );
      return;
    }
    if (line.startsWith("## ")) {
      renderedElements.push(
        <h3 key={index} style={{ fontSize: "1.2rem", fontWeight: 700, margin: "1rem 0 0.4rem 0", color: "#0f172a" }}>
          {renderInlineStyles(line.slice(3))}
        </h3>
      );
      return;
    }
    if (line.startsWith("# ")) {
      renderedElements.push(
        <h2 key={index} style={{ fontSize: "1.35rem", fontWeight: 700, margin: "1.2rem 0 0.5rem 0", color: "#0f172a" }}>
          {renderInlineStyles(line.slice(2))}
        </h2>
      );
      return;
    }

    // Blockquote
    if (line.startsWith("> ")) {
      renderedElements.push(
        <div
          key={index}
          style={{
            borderLeft: "3px solid #3b82f6",
            backgroundColor: "#eff6ff",
            color: "#1e3a8a",
            padding: "0.4rem 0.8rem",
            margin: "0.5rem 0",
            borderRadius: "0 4px 4px 0",
            fontSize: "0.88rem",
          }}
        >
          {renderInlineStyles(line.slice(2))}
        </div>
      );
      return;
    }

    // Unordered List item
    if (line.trim().startsWith("- ") || line.trim().startsWith("* ")) {
      const bulletText = line.trim().slice(2);
      renderedElements.push(
        <div
          key={index}
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: "0.5rem",
            margin: "0.25rem 0",
            fontSize: "0.92rem",
            lineHeight: "1.5",
          }}
        >
          <span style={{ color: "#3b82f6", fontWeight: "bold" }}>•</span>
          <div>{renderInlineStyles(bulletText)}</div>
        </div>
      );
      return;
    }

    // Numbered list item
    const numMatch = line.trim().match(/^(\d+)\.\s+(.*)$/);
    if (numMatch) {
      renderedElements.push(
        <div
          key={index}
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: "0.5rem",
            margin: "0.25rem 0",
            fontSize: "0.92rem",
            lineHeight: "1.5",
          }}
        >
          <span style={{ color: "#2563eb", fontWeight: 600, minWidth: "1.2rem" }}>
            {numMatch[1]}.
          </span>
          <div>{renderInlineStyles(numMatch[2])}</div>
        </div>
      );
      return;
    }

    // Empty lines
    if (!line.trim()) {
      renderedElements.push(<div key={index} style={{ height: "0.4rem" }} />);
      return;
    }

    // Regular paragraph
    renderedElements.push(
      <p key={index} style={{ margin: "0.3rem 0", fontSize: "0.92rem", lineHeight: "1.55" }}>
        {renderInlineStyles(line)}
      </p>
    );
  });

  return <div>{renderedElements}</div>;
};

// Simple inline parser for **bold**, `code`, and [citations]
function renderInlineStyles(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[[a-zA-Z0-9_\-\./]+:\d+(?:-\d+)?\])/g);

  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i} style={{ color: "#0f172a" }}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code
          key={i}
          style={{
            backgroundColor: "#f1f5f9",
            color: "#0f172a",
            padding: "0.15rem 0.35rem",
            borderRadius: "4px",
            fontSize: "0.85em",
            fontFamily: "ui-monospace, monospace",
            border: "1px solid #e2e8f0",
          }}
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    // Citation tag [path:lines]
    if (part.startsWith("[") && part.endsWith("]") && part.includes(":")) {
      return (
        <span
          key={i}
          style={{
            backgroundColor: "#dbeafe",
            color: "#1d4ed8",
            fontWeight: 600,
            fontSize: "0.8em",
            padding: "0.1rem 0.4rem",
            borderRadius: "4px",
            border: "1px solid #bfdbfe",
            margin: "0 0.15rem",
          }}
        >
          {part}
        </span>
      );
    }
    return part;
  });
}

// ---------------------------------------------------------------------------
// Main RepoChatPage Component
// ---------------------------------------------------------------------------

export const RepoChatPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [expandedCitationMap, setExpandedCitationMap] = useState<Record<string, boolean>>({});

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 1. Fetch Repository Details
  const { data: repo } = useQuery({
    queryKey: ["repository", id],
    queryFn: () => (id ? fetchRepository(id) : Promise.reject("No repo ID")),
    enabled: !!id,
  });

  // 2. Fetch Sessions List
  const { data: sessions, isLoading: isLoadingSessions } = useQuery({
    queryKey: ["chat-sessions", id],
    queryFn: () => (id ? listChatSessions(id) : Promise.reject("No repo ID")),
    enabled: !!id,
  });

  // 3. Select or auto-create active session
  useEffect(() => {
    if (sessions && sessions.length > 0 && !activeSessionId) {
      setActiveSessionId(sessions[0].id);
    }
  }, [sessions, activeSessionId]);

  // 4. Fetch Active Session details (with full messages history)
  const {
    data: activeSession,
    refetch: refetchActiveSession,
  } = useQuery({
    queryKey: ["chat-session", id, activeSessionId],
    queryFn: () =>
      id && activeSessionId
        ? fetchChatSession(id, activeSessionId)
        : Promise.reject("No session"),
    enabled: !!id && !!activeSessionId,
  });

  // Auto-scroll on new message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeSession?.messages]);

  // 5. Create Session Mutation
  const createSessionMutation = useMutation({
    mutationFn: async () => {
      if (!id) throw new Error("No repository ID");
      return createChatSession(id, "New Chat");
    },
    onSuccess: (newSession: ChatSessionItem) => {
      queryClient.invalidateQueries({ queryKey: ["chat-sessions", id] });
      setActiveSessionId(newSession.id);
    },
  });

  // 6. Delete Session Mutation
  const deleteSessionMutation = useMutation({
    mutationFn: async (sessionId: string) => {
      if (!id) throw new Error("No repository ID");
      return deleteChatSession(id, sessionId);
    },
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ["chat-sessions", id] });
      if (activeSessionId === deletedId) {
        setActiveSessionId(null);
      }
    },
  });

  // 7. Send Message Mutation
  const sendMessageMutation = useMutation({
    mutationFn: async ({ text, sessionId }: { text: string; sessionId: string }) => {
      if (!id) throw new Error("No repository ID");
      return sendChatMessage(id, sessionId, text);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat-sessions", id] });
      refetchActiveSession();
    },
  });

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || sendMessageMutation.isPending || !id) return;

    let targetSessionId = activeSessionId;

    // If no active session, create one first
    if (!targetSessionId) {
      try {
        const created = await createChatSession(id, trimmed.slice(0, 40));
        targetSessionId = created.id;
        setActiveSessionId(created.id);
        queryClient.invalidateQueries({ queryKey: ["chat-sessions", id] });
      } catch (err) {
        console.error("Failed to initialize session:", err);
        return;
      }
    }

    setQuestion("");
    sendMessageMutation.mutate({ text: trimmed, sessionId: targetSessionId });
  };

  const handleQuickPrompt = (promptText: string) => {
    setQuestion(promptText);
  };

  const toggleEvidencePanel = (msgId: string) => {
    setExpandedCitationMap((prev) => ({
      ...prev,
      [msgId]: !prev[msgId],
    }));
  };

  return (
    <div style={{ maxWidth: "1280px", margin: "1.5rem auto", padding: "0 1.5rem", fontFamily: "system-ui, -apple-system, sans-serif" }}>
      {/* Top Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.2rem" }}>
        <div>
          <Link
            to={`/repositories/${id}`}
            style={{ textDecoration: "none", color: "#2563eb", fontSize: "0.88rem", fontWeight: 500 }}
          >
            ← Back to Repository Overview
          </Link>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginTop: "0.4rem" }}>
            <h1 style={{ fontSize: "1.65rem", fontWeight: 800, margin: 0, color: "#0f172a" }}>
              RepoPilot AI Chat
            </h1>
            <span
              style={{
                backgroundColor: "#dbeafe",
                color: "#1e40af",
                fontSize: "0.75rem",
                fontWeight: 700,
                padding: "0.2rem 0.6rem",
                borderRadius: "12px",
              }}
            >
              ChatGPT for GitHub Repos
            </span>
          </div>
          <p style={{ margin: "0.2rem 0 0 0", color: "#64748b", fontSize: "0.9rem" }}>
            Repository: <strong>{repo?.full_name || id}</strong>
          </p>
        </div>

        {/* Source metadata badges upholding Hard Rule 5 */}
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <span
            style={{
              backgroundColor: "#f0fdf4",
              color: "#166534",
              fontSize: "0.75rem",
              fontWeight: 600,
              padding: "0.25rem 0.55rem",
              borderRadius: "4px",
              border: "1px solid #bbf7d0",
            }}
          >
            source: llm_generated
          </span>
          <span
            style={{
              backgroundColor: "#f8fafc",
              color: "#475569",
              fontSize: "0.75rem",
              fontWeight: 600,
              padding: "0.25rem 0.55rem",
              borderRadius: "4px",
              border: "1px solid #e2e8f0",
            }}
          >
            source: static (citations)
          </span>
        </div>
      </div>

      {/* Main Two-Column Container */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "260px 1fr",
          gap: "1.25rem",
          backgroundColor: "#ffffff",
          borderRadius: "12px",
          border: "1px solid #e2e8f0",
          boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
          minHeight: "680px",
          overflow: "hidden",
        }}
      >
        {/* Left Sidebar: Conversations & Sessions */}
        <div
          style={{
            borderRight: "1px solid #e2e8f0",
            backgroundColor: "#f8fafc",
            display: "flex",
            flexDirection: "column",
            padding: "1rem",
          }}
        >
          <button
            type="button"
            onClick={() => createSessionMutation.mutate()}
            disabled={createSessionMutation.isPending}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "0.5rem",
              backgroundColor: "#2563eb",
              color: "#ffffff",
              border: "none",
              borderRadius: "8px",
              padding: "0.65rem 1rem",
              fontWeight: 600,
              fontSize: "0.9rem",
              cursor: "pointer",
              marginBottom: "1rem",
            }}
          >
            <span>+</span> New Chat
          </button>

          <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "#64748b", textTransform: "uppercase", marginBottom: "0.5rem" }}>
            Chat History
          </div>

          <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "0.35rem" }}>
            {isLoadingSessions && <div style={{ fontSize: "0.85rem", color: "#94a3b8" }}>Loading chats...</div>}

            {sessions && sessions.length === 0 && (
              <div style={{ fontSize: "0.85rem", color: "#94a3b8", fontStyle: "italic", padding: "0.5rem 0" }}>
                No conversations yet. Start one!
              </div>
            )}

            {sessions?.map((sess) => {
              const isActive = sess.id === activeSessionId;
              return (
                <div
                  key={sess.id}
                  onClick={() => setActiveSessionId(sess.id)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "0.55rem 0.75rem",
                    borderRadius: "6px",
                    cursor: "pointer",
                    backgroundColor: isActive ? "#e2e8f0" : "transparent",
                    color: isActive ? "#0f172a" : "#475569",
                    fontWeight: isActive ? 600 : 400,
                    fontSize: "0.85rem",
                    transition: "all 0.15s ease",
                  }}
                >
                  <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
                    💬 {sess.title}
                  </div>
                  <button
                    type="button"
                    title="Delete Chat"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm("Delete this conversation?")) {
                        deleteSessionMutation.mutate(sess.id);
                      }
                    }}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#94a3b8",
                      cursor: "pointer",
                      fontSize: "0.8rem",
                      padding: "0 0.2rem",
                    }}
                  >
                    ×
                  </button>
                </div>
              );
            })}
          </div>

          {/* Assistant Info Footer */}
          <div
            style={{
              paddingTop: "0.75rem",
              borderTop: "1px solid #e2e8f0",
              fontSize: "0.75rem",
              color: "#94a3b8",
              display: "flex",
              justifyContent: "space-between",
            }}
          >
            <span>Model: gpt-4o-mini</span>
            <span>RAG Active</span>
          </div>
        </div>

        {/* Right Main Chat Area */}
        <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
          {/* Quick Prompts Bar */}
          <div
            style={{
              padding: "0.75rem 1.25rem",
              borderBottom: "1px solid #f1f5f9",
              backgroundColor: "#ffffff",
              display: "flex",
              gap: "0.5rem",
              overflowX: "auto",
              whiteSpace: "nowrap",
            }}
          >
            <span style={{ fontSize: "0.8rem", color: "#64748b", alignSelf: "center", fontWeight: 600 }}>
              Quick Ask:
            </span>
            {[
              "Explain the repository architecture and purpose",
              "Which file has the most lines of code and complexity?",
              "What are the highest defect risk modules?",
              "What are the main dependency hubs in this repo?",
              "How does user authentication work?",
            ].map((promptText) => (
              <button
                key={promptText}
                type="button"
                onClick={() => handleQuickPrompt(promptText)}
                style={{
                  backgroundColor: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  borderRadius: "16px",
                  padding: "0.3rem 0.75rem",
                  fontSize: "0.78rem",
                  color: "#334155",
                  cursor: "pointer",
                  whiteSpace: "nowrap",
                }}
              >
                {promptText}
              </button>
            ))}
          </div>

          {/* Messages Feed */}
          <div
            style={{
              flex: 1,
              overflowY: "auto",
              padding: "1.25rem 1.5rem",
              display: "flex",
              flexDirection: "column",
              gap: "1.25rem",
              backgroundColor: "#fcfdfe",
            }}
          >
            {/* Initial Welcome message */}
            {(!activeSession?.messages || activeSession.messages.length === 0) && (
              <div
                style={{
                  backgroundColor: "#ffffff",
                  border: "1px solid #e2e8f0",
                  borderRadius: "10px",
                  padding: "1.5rem",
                  maxWidth: "80%",
                  color: "#334155",
                  boxShadow: "0 1px 2px rgba(0,0,0,0.03)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
                  <span style={{ fontSize: "1.25rem" }}>🤖</span>
                  <strong style={{ fontSize: "1.05rem", color: "#0f172a" }}>RepoPilot AI Assistant</strong>
                </div>
                <p style={{ margin: "0 0 0.75rem 0", lineHeight: "1.5", fontSize: "0.92rem" }}>
                  Hello! I am your conversational GitHub repository expert. I have completely read and indexed{" "}
                  <strong>{repo?.full_name || "this repository"}</strong>.
                </p>
                <p style={{ margin: "0 0 0.5rem 0", fontSize: "0.88rem", color: "#64748b" }}>
                  Ask me anything about:
                </p>
                <ul style={{ margin: "0 0 1rem 1.25rem", padding: 0, fontSize: "0.88rem", color: "#475569" }}>
                  <li>Architecture overviews & design decisions</li>
                  <li>What specific files, classes, or functions do</li>
                  <li>Codebase metrics (LOC, cyclomatic complexity, maintainability)</li>
                  <li>Defect risk predictions and statistical drivers (ML model v2.0.0)</li>
                  <li>How to implement new features or refactor code</li>
                </ul>
                <div style={{ fontSize: "0.8rem", color: "#94a3b8" }}>
                  Every statement is grounded in verified code excerpts with bracketed citations.
                </div>
              </div>
            )}

            {/* Rendered Message List */}
            {activeSession?.messages?.map((msg) => {
              const isUser = msg.role === "user";
              return (
                <div
                  key={msg.id}
                  style={{
                    alignSelf: isUser ? "flex-end" : "flex-start",
                    maxWidth: "85%",
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.35rem",
                  }}
                >
                  {/* Sender label */}
                  <div
                    style={{
                      fontSize: "0.75rem",
                      fontWeight: 600,
                      color: isUser ? "#2563eb" : "#475569",
                      alignSelf: isUser ? "flex-end" : "flex-start",
                      display: "flex",
                      gap: "0.4rem",
                      alignItems: "center",
                    }}
                  >
                    <span>{isUser ? "You" : "🤖 RepoPilot AI"}</span>
                    <span style={{ fontWeight: 400, color: "#94a3b8" }}>
                      {new Date(msg.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>

                  {/* Message Bubble */}
                  <div
                    style={{
                      backgroundColor: isUser ? "#2563eb" : "#ffffff",
                      color: isUser ? "#ffffff" : "#0f172a",
                      border: isUser ? "none" : "1px solid #e2e8f0",
                      borderRadius: isUser ? "12px 12px 2px 12px" : "12px 12px 12px 2px",
                      padding: "1rem 1.25rem",
                      boxShadow: isUser ? "0 2px 4px rgba(37,99,235,0.15)" : "0 1px 3px rgba(0,0,0,0.05)",
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
                        ⚠️ Abstention: Not enough evidence in codebase to confirm.
                      </div>
                    )}

                    {/* Content */}
                    {isUser ? (
                      <div style={{ whiteSpace: "pre-wrap", fontSize: "0.95rem", lineHeight: "1.5" }}>
                        {msg.content}
                      </div>
                    ) : (
                      <MarkdownContent content={msg.content} />
                    )}

                    {/* Metadata footer */}
                    {!isUser && (
                      <div
                        style={{
                          marginTop: "0.75rem",
                          paddingTop: "0.5rem",
                          borderTop: "1px solid #f1f5f9",
                          display: "flex",
                          justifyContent: "space-between",
                          fontSize: "0.72rem",
                          color: "#94a3b8",
                        }}
                      >
                        <span>source: {msg.source}</span>
                        <span>model: {msg.model_version}</span>
                      </div>
                    )}
                  </div>

                  {/* Citations Accordion (Rule 5 & P2-06) */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div style={{ alignSelf: "flex-start", marginTop: "0.2rem" }}>
                      <button
                        type="button"
                        onClick={() => toggleEvidencePanel(msg.id)}
                        style={{
                          background: "none",
                          border: "1px solid #cbd5e1",
                          borderRadius: "6px",
                          padding: "0.25rem 0.6rem",
                          fontSize: "0.75rem",
                          color: "#2563eb",
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          gap: "0.35rem",
                          fontWeight: 600,
                        }}
                      >
                        <span>{expandedCitationMap[msg.id] ? "▼ Hide" : "▶ View"} Evidence & Citations ({msg.citations.length})</span>
                      </button>

                      {expandedCitationMap[msg.id] && (
                        <div
                          style={{
                            marginTop: "0.4rem",
                            display: "flex",
                            flexDirection: "column",
                            gap: "0.5rem",
                            maxWidth: "750px",
                          }}
                        >
                          {msg.citations.map((c, cIdx) => (
                            <div
                              key={cIdx}
                              style={{
                                backgroundColor: "#f8fafc",
                                border: "1px solid #cbd5e1",
                                borderRadius: "6px",
                                padding: "0.6rem 0.8rem",
                                fontSize: "0.78rem",
                              }}
                            >
                              <div
                                style={{
                                  display: "flex",
                                  justifyContent: "space-between",
                                  alignItems: "center",
                                  marginBottom: "0.35rem",
                                }}
                              >
                                <div>
                                  <strong style={{ color: "#0f172a" }}>{c.file_path}</strong>
                                  <span style={{ color: "#64748b", marginLeft: "0.4rem" }}>
                                    #L{c.start_line}-L{c.end_line}
                                  </span>
                                  {c.symbol_name && (
                                    <span
                                      style={{
                                        marginLeft: "0.4rem",
                                        backgroundColor: "#e2e8f0",
                                        padding: "0.1rem 0.3rem",
                                        borderRadius: "3px",
                                        fontSize: "0.72rem",
                                      }}
                                    >
                                      {c.symbol_name}
                                    </span>
                                  )}
                                </div>
                                <span style={{ color: "#059669", fontWeight: 600 }}>
                                  Match: {(c.similarity_score * 100).toFixed(1)}%
                                </span>
                              </div>
                              <pre
                                style={{
                                  backgroundColor: "#0f172a",
                                  color: "#f8fafc",
                                  padding: "0.5rem 0.6rem",
                                  borderRadius: "4px",
                                  fontSize: "0.75rem",
                                  margin: 0,
                                  overflowX: "auto",
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
              );
            })}

            {/* Pending assistant typing indicator */}
            {sendMessageMutation.isPending && (
              <div
                style={{
                  alignSelf: "flex-start",
                  backgroundColor: "#ffffff",
                  border: "1px solid #e2e8f0",
                  borderRadius: "12px 12px 12px 2px",
                  padding: "0.8rem 1.2rem",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.6rem",
                  color: "#64748b",
                  fontSize: "0.88rem",
                }}
              >
                <span>🤖 Thinking & searching codebase...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Bottom Chat Input Form */}
          <div
            style={{
              padding: "1rem 1.25rem",
              borderTop: "1px solid #e2e8f0",
              backgroundColor: "#ffffff",
            }}
          >
            <form onSubmit={handleSend} style={{ display: "flex", gap: "0.75rem" }}>
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask me anything about this repository (architecture, files, metrics, bugs)..."
                disabled={sendMessageMutation.isPending}
                style={{
                  flex: 1,
                  padding: "0.75rem 1rem",
                  fontSize: "0.95rem",
                  border: "1px solid #cbd5e1",
                  borderRadius: "8px",
                  outline: "none",
                }}
              />
              <button
                type="submit"
                disabled={!question.trim() || sendMessageMutation.isPending}
                style={{
                  backgroundColor: !question.trim() || sendMessageMutation.isPending ? "#94a3b8" : "#2563eb",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "8px",
                  padding: "0.75rem 1.5rem",
                  fontSize: "0.95rem",
                  fontWeight: 600,
                  cursor: !question.trim() || sendMessageMutation.isPending ? "not-allowed" : "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.4rem",
                }}
              >
                <span>{sendMessageMutation.isPending ? "Thinking..." : "Send"}</span>
                <span>➔</span>
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};

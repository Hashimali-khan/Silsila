"use client";

import { useState, useRef, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";
import { AppNav } from "@/components/AppNav";
import Link from "next/link";
import { ArrowLeft, Sparkles, MessageSquare, Search } from "lucide-react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

type QAState =
  | { status: "idle" }
  | { status: "searching"; message?: string }
  | { status: "answering"; answer: string; evidence: any[] }
  | { status: "done"; answer: string; evidence: any[] }
  | { status: "error"; message: string };

const SUGGESTIONS = [
  "When did we first start chatting?",
  "What was our biggest inside joke?",
  "What plans or trips did we discuss?",
  "Who sends the most messages and what are they about?",
];

export function QAClient({
  chatId,
  chatName,
  initialQuery = "",
}: {
  chatId: string;
  chatName?: string;
  initialQuery?: string;
}) {
  const { isLoaded, isSignedIn, getToken } = useAuth();

  const [query, setQuery] = useState(initialQuery);
  const [state, setState] = useState<QAState>({ status: "idle" });
  const [showEvidence, setShowEvidence] = useState(false);

  const endRef = useRef<HTMLDivElement>(null);
  const autoRanRef = useRef(false);

  useEffect(() => {
    if (state.status === "answering" || state.status === "done") {
      endRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [state]);

  const runQA = async (q: string) => {
    if (!q.trim()) return;
    setState({ status: "searching", message: "Searching chat memories..." });
    setShowEvidence(false);

    try {
      const token = await getToken();

      const response = await fetch(`${BACKEND_URL}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          query_text: q,
          chat_id: chatId,
        }),
      });

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({ detail: "Failed to query chat" }));
        throw new Error(errJson.detail || `Server error (${response.status})`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder("utf-8");

      if (!reader) {
        throw new Error("Stream not available");
      }

      let currentAnswer = "";
      let currentEvidence: any[] = [];
      let isAnswering = false;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const dataStr = line.substring(6).trim();
            if (!dataStr) continue;

            try {
              const data = JSON.parse(dataStr);
              if (data.type === "status") {
                if (!isAnswering) {
                  setState({ status: "searching", message: data.content });
                }
              } else if (data.type === "evidence") {
                currentEvidence = data.content;
              } else if (data.type === "token") {
                isAnswering = true;
                currentAnswer += data.content;
                setState({ status: "answering", answer: currentAnswer, evidence: currentEvidence });
              } else if (data.type === "error") {
                setState({ status: "error", message: data.content });
                return;
              } else if (data.type === "done") {
                setState({ status: "done", answer: currentAnswer, evidence: currentEvidence });
                return;
              }
            } catch (e) {
              console.error("Failed to parse SSE message:", dataStr, e);
            }
          }
        }
      }
    } catch (e) {
      setState({ status: "error", message: e instanceof Error ? e.message : "QA failed" });
    }
  };

  useEffect(() => {
    if (initialQuery && !autoRanRef.current) {
      autoRanRef.current = true;
      runQA(initialQuery);
    }
  }, [initialQuery]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    runQA(query);
  };

  return (
    <div style={{ minHeight: "100vh", background: "var(--background)", display: "flex", flexDirection: "column" }}>
      <AppNav />

      {/* Top Header */}
      <div
        style={{
          background: "var(--surface, #ffffff)",
          borderBottom: "1px solid var(--border, #e2e8f0)",
          padding: "0.75rem 1.5rem",
          position: "sticky",
          top: 0,
          zIndex: 20,
        }}
      >
        <div
          style={{
            maxWidth: "1100px",
            margin: "0 auto",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
            <Link
              href={`/chat/${chatId}`}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.375rem",
                color: "var(--text-secondary, #475569)",
                textDecoration: "none",
                fontSize: "0.875rem",
                fontWeight: 600,
                background: "var(--stone-100, #f1f5f9)",
                padding: "0.4rem 0.75rem",
                borderRadius: "0.5rem",
              }}
            >
              <ArrowLeft size={16} />
              <span>Back to Messages</span>
            </Link>

            {chatName && (
              <span
                style={{
                  fontWeight: 700,
                  fontSize: "0.9375rem",
                  color: "var(--text-primary, #0f172a)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  maxWidth: "350px",
                }}
              >
                {chatName}
              </span>
            )}
          </div>

          <div style={{ display: "flex", gap: "0.5rem" }}>
            <Link
              href={`/chat/${chatId}`}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.375rem",
                fontSize: "0.8125rem",
                fontWeight: 500,
                color: "var(--text-secondary, #64748b)",
                textDecoration: "none",
                padding: "0.375rem 0.75rem",
                borderRadius: "0.375rem",
                background: "var(--stone-100, #f1f5f9)",
              }}
            >
              <MessageSquare size={14} />
              <span>Messages</span>
            </Link>
            <Link
              href={`/chat/${chatId}/search`}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.375rem",
                fontSize: "0.8125rem",
                fontWeight: 500,
                color: "var(--text-secondary, #64748b)",
                textDecoration: "none",
                padding: "0.375rem 0.75rem",
                borderRadius: "0.375rem",
                background: "var(--stone-100, #f1f5f9)",
              }}
            >
              <Search size={14} />
              <span>Search</span>
            </Link>
          </div>
        </div>
      </div>

      <main style={{ maxWidth: "800px", width: "100%", margin: "0 auto", padding: "2rem 1.5rem", flex: 1 }}>
        {/* Title */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.875rem", marginBottom: "0.75rem" }}>
          <div
            style={{
              width: "2.75rem",
              height: "2.75rem",
              borderRadius: "0.75rem",
              background: "linear-gradient(135deg, #ea580c, #f97316)",
              color: "#ffffff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 4px 12px rgba(234, 88, 12, 0.3)",
              flexShrink: 0,
            }}
          >
            <Sparkles size={22} />
          </div>
          <div>
            <h1
              style={{
                fontFamily: "'Plus Jakarta Sans', sans-serif",
                fontWeight: 800,
                fontSize: "1.75rem",
                margin: 0,
                color: "var(--text-primary, #0f172a)",
              }}
            >
              AI Memory Detective
            </h1>
            <p style={{ color: "var(--text-secondary, #64748b)", margin: "0.25rem 0 0", fontSize: "0.875rem" }}>
              Ask natural language questions about your chat grounded in actual messages and timestamps.
            </p>
          </div>
        </div>

        {/* Search form */}
        <form onSubmit={handleSubmit} style={{ marginTop: "1.75rem", marginBottom: "1rem" }}>
          <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
            <div style={{ flex: 1, position: "relative" }}>
              <span
                style={{
                  position: "absolute",
                  left: "1rem",
                  top: "50%",
                  transform: "translateY(-50%)",
                  color: "#ea580c",
                  pointerEvents: "none",
                  fontSize: "1rem",
                }}
              >
                ✨
              </span>
              <input
                id="qa-query-input"
                type="text"
                className="search-input"
                style={{
                  width: "100%",
                  paddingLeft: "2.75rem",
                  paddingRight: "1rem",
                  paddingTop: "0.875rem",
                  paddingBottom: "0.875rem",
                  borderRadius: "0.75rem",
                  border: "1px solid var(--border, #cbd5e1)",
                  background: "#ffffff",
                  fontSize: "0.9375rem",
                  outline: "none",
                }}
                placeholder="E.g. What was our first argument about?"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                autoFocus
              />
            </div>
            <button
              type="submit"
              className="btn-primary"
              style={{
                padding: "0.875rem 1.5rem",
                background: "linear-gradient(135deg, #ea580c, #f97316)",
                color: "#ffffff",
                borderRadius: "0.75rem",
                fontWeight: 700,
                fontSize: "0.9375rem",
                border: "none",
                cursor: "pointer",
              }}
              disabled={!query.trim() || state.status === "searching" || state.status === "answering"}
            >
              {state.status === "searching" ? "Thinking…" : "Ask"}
            </button>
          </div>
        </form>

        {/* Suggestion pills */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginBottom: "2rem" }}>
          {SUGGESTIONS.map((s, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => {
                setQuery(s);
                runQA(s);
              }}
              style={{
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                borderRadius: "9999px",
                padding: "0.4rem 0.875rem",
                fontSize: "0.75rem",
                fontWeight: 500,
                color: "#475569",
                cursor: "pointer",
                transition: "all 0.15s",
              }}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Status */}
        {state.status === "searching" && (
          <div style={{ textAlign: "center", padding: "3rem 1rem", color: "#ea580c" }}>
            <div
              style={{
                width: "2rem",
                height: "2rem",
                border: "3px solid #fdba74",
                borderTopColor: "#ea580c",
                borderRadius: "50%",
                animation: "spin 1s linear infinite",
                margin: "0 auto 1rem",
              }}
            />
            <p style={{ fontWeight: 600, fontSize: "0.9375rem" }}>{state.message || "Searching memories..."}</p>
          </div>
        )}

        {/* Answer area */}
        {(state.status === "answering" || state.status === "done") && (
          <div
            style={{
              background: "#ffffff",
              padding: "1.75rem",
              borderRadius: "1rem",
              marginBottom: "2rem",
              border: "1px solid #fdba74",
              boxShadow: "0 4px 20px rgba(234, 88, 12, 0.08)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1rem" }}>
              <Sparkles size={20} color="#ea580c" />
              <h3 style={{ margin: 0, fontSize: "1.125rem", color: "var(--text-primary, #0f172a)", fontWeight: 800 }}>
                Answer & Analysis
              </h3>
            </div>
            <div
              style={{
                whiteSpace: "pre-wrap",
                lineHeight: 1.7,
                color: "var(--text-secondary, #334155)",
                fontSize: "0.9375rem",
              }}
            >
              {state.answer}
              {state.status === "answering" && <span style={{ color: "#ea580c", fontWeight: 700 }}> |</span>}
            </div>

            {state.evidence && state.evidence.length > 0 && (
              <div style={{ marginTop: "1.75rem", borderTop: "1px solid #f1f5f9", paddingTop: "1rem" }}>
                <button
                  onClick={() => setShowEvidence(!showEvidence)}
                  style={{
                    background: "none",
                    border: "none",
                    color: "#ea580c",
                    fontWeight: 700,
                    cursor: "pointer",
                    padding: "0.5rem 0",
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                    fontSize: "0.875rem",
                  }}
                >
                  {showEvidence ? "Hide Evidence ▴" : `View Evidence (${state.evidence.length} blocks) ▾`}
                </button>

                {showEvidence && (
                  <div style={{ marginTop: "1rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                    {state.evidence.map((block: any, idx: number) => (
                      <div
                        key={idx}
                        style={{
                          background: "#f8fafc",
                          padding: "1rem",
                          borderRadius: "0.5rem",
                          border: "1px solid #e2e8f0",
                          fontSize: "0.85rem",
                          overflowX: "auto",
                        }}
                      >
                        <div style={{ fontWeight: 600, marginBottom: "0.375rem", color: "#64748b" }}>
                          Thread Evidence
                        </div>
                        <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontFamily: "inherit" }}>
                          {block.content}
                        </pre>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
            <div ref={endRef} />
          </div>
        )}

        {/* Error state */}
        {state.status === "error" && (
          <div
            style={{
              background: "#fff1f2",
              border: "1px solid #fda4af",
              borderRadius: "0.75rem",
              padding: "1rem 1.25rem",
              color: "#be123c",
              fontSize: "0.9rem",
              fontWeight: 500,
            }}
          >
            ⚠️ {state.message}
          </div>
        )}
      </main>

      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

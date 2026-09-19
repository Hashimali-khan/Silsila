"use client";

import { useState, useRef, useEffect, Suspense } from "react";
import { useAuth } from "@clerk/nextjs";
import { AppNav } from "@/components/AppNav";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
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

function QAContent() {
  const params = useParams();
  const searchParams = useSearchParams();
  const chatId = params.chatId as string;
  const { getToken } = useAuth();

  const [query, setQuery] = useState(searchParams.get("q") || "");
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
        throw new Error("Failed to start QA session");
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
    const q = searchParams.get("q");
    if (q && !autoRanRef.current) {
      autoRanRef.current = true;
      runQA(q);
    }
  }, [searchParams]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    runQA(query);
  };

  return (
    <div style={{ minHeight: "100vh", background: "var(--background)" }}>
      <AppNav />

      {/* Chat header bar */}
      <div
        style={{
          background: "var(--surface, #ffffff)",
          borderBottom: "1px solid var(--border, #e2e8f0)",
          padding: "0.75rem 1.5rem",
        }}
      >
        <div
          style={{
            maxWidth: "1000px",
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
                fontWeight: 500,
                background: "var(--stone-100, #f1f5f9)",
                padding: "0.375rem 0.75rem",
                borderRadius: "0.5rem",
              }}
            >
              <ArrowLeft size={16} />
              <span>Back to Messages</span>
            </Link>
          </div>

          <div style={{ display: "flex", gap: "0.75rem" }}>
            <Link
              href={`/chat/${chatId}`}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.375rem",
                fontSize: "0.8125rem",
                color: "var(--text-secondary)",
                textDecoration: "none",
                padding: "0.375rem 0.625rem",
                borderRadius: "0.375rem",
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
                color: "var(--text-secondary)",
                textDecoration: "none",
                padding: "0.375rem 0.625rem",
                borderRadius: "0.375rem",
              }}
            >
              <Search size={14} />
              <span>Search</span>
            </Link>
          </div>
        </div>
      </div>

      <main style={{ maxWidth: "800px", margin: "0 auto", padding: "2rem 1.5rem" }}>
        {/* Title */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.5rem" }}>
          <div
            style={{
              width: "2.5rem",
              height: "2.5rem",
              borderRadius: "0.75rem",
              background: "linear-gradient(135deg, #ea580c, #f97316)",
              color: "#ffffff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 2px 8px rgba(234, 88, 12, 0.3)",
            }}
          >
            <Sparkles size={20} />
          </div>
          <div>
            <h1
              style={{
                fontFamily: "'Plus Jakarta Sans', sans-serif",
                fontWeight: 800,
                fontSize: "1.75rem",
                margin: 0,
              }}
            >
              AI Memory Detective
            </h1>
            <p style={{ color: "var(--text-secondary)", margin: 0, fontSize: "0.875rem" }}>
              Ask natural language questions about your chat grounded in actual messages and timestamps.
            </p>
          </div>
        </div>

        {/* Search form */}
        <form onSubmit={handleSubmit} style={{ marginTop: "1.5rem", marginBottom: "1rem" }}>
          <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
            <div style={{ flex: 1, position: "relative" }}>
              <span
                style={{
                  position: "absolute",
                  left: "1rem",
                  top: "50%",
                  transform: "translateY(-50%)",
                  color: "var(--text-muted)",
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
                placeholder="E.g. What was our first argument about?"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                autoFocus
              />
            </div>
            <button
              type="submit"
              className="btn-primary"
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
                background: "var(--surface, #ffffff)",
                border: "1px solid var(--border, #e2e8f0)",
                borderRadius: "9999px",
                padding: "0.375rem 0.875rem",
                fontSize: "0.75rem",
                fontWeight: 500,
                color: "var(--text-secondary, #475569)",
                cursor: "pointer",
                transition: "all 0.15s",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "#ea580c";
                e.currentTarget.style.color = "#ea580c";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "var(--border, #e2e8f0)";
                e.currentTarget.style.color = "var(--text-secondary, #475569)";
              }}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Status */}
        {state.status === "searching" && (
          <div style={{ textAlign: "center", padding: "2.5rem", color: "var(--orange-600)" }}>
            <div className="spinner" style={{ marginBottom: "1rem", margin: "0 auto" }}></div>
            <p style={{ fontWeight: 500 }}>{state.message || "Searching memories..."}</p>
          </div>
        )}

        {/* Answer area */}
        {(state.status === "answering" || state.status === "done") && (
          <div className="card fade-in" style={{ padding: "1.75rem", marginBottom: "2rem", border: "1px solid #fdba74" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1rem" }}>
              <Sparkles size={18} color="#ea580c" />
              <h3 style={{ margin: 0, fontSize: "1.1rem", color: "var(--text-primary)", fontWeight: 700 }}>
                Answer & Analysis
              </h3>
            </div>
            <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.7, color: "var(--text-secondary)", fontSize: "0.9375rem" }}>
              {state.answer}
              {state.status === "answering" && <span className="blinking-cursor">|</span>}
            </div>

            {state.evidence && state.evidence.length > 0 && (
              <div style={{ marginTop: "2rem", borderTop: "1px solid var(--border-light)", paddingTop: "1rem" }}>
                <button
                  onClick={() => setShowEvidence(!showEvidence)}
                  style={{
                    background: "none",
                    border: "none",
                    color: "var(--orange-600)",
                    fontWeight: 600,
                    cursor: "pointer",
                    padding: "0.5rem 0",
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                  }}
                >
                  {showEvidence ? "Hide Evidence ▴" : `View Evidence (${state.evidence.length} blocks) ▾`}
                </button>

                {showEvidence && (
                  <div style={{ marginTop: "1rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
                    {state.evidence.map((block: any, idx: number) => (
                      <div key={idx} style={{ background: "var(--background-alt)", padding: "1rem", borderRadius: "var(--radius-md)", fontSize: "0.85rem", overflowX: "auto" }}>
                        <div style={{ fontWeight: 600, marginBottom: "0.5rem", color: "var(--text-muted)" }}>Thread Context</div>
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
              borderRadius: "var(--radius-md)",
              padding: "1rem 1.25rem",
              color: "#be123c",
              fontSize: "0.9rem",
            }}
          >
            ⚠️ {state.message}
          </div>
        )}
      </main>
    </div>
  );
}

export default function QAPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: "100vh", background: "var(--background)" }}><AppNav /></div>}>
      <QAContent />
    </Suspense>
  );
}

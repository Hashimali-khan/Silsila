"use client";

import { useState, useCallback } from "react";
import { useAuth } from "@clerk/nextjs";
import { AppNav } from "@/components/AppNav";
import type { SearchResponse } from "@/lib/types";
import { formatTime, formatDate } from "@/lib/utils";
import Link from "next/link";
import { useParams } from "next/navigation";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

type SearchState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "results"; data: SearchResponse }
  | { status: "error"; message: string };

export default function SearchPage() {
  const params = useParams();
  const chatId = params.chatId as string;
  const { getToken } = useAuth();

  const [query, setQuery] = useState("");
  const [state, setState] = useState<SearchState>({ status: "idle" });

  const runSearch = useCallback(
    async (q: string) => {
      if (!q.trim()) return;
      setState({ status: "loading" });
      try {
        const token = await getToken();
        const res = await fetch(
          `${BACKEND_URL}/api/search?chat_id=${encodeURIComponent(chatId)}&q=${encodeURIComponent(q)}&limit=50`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: "Search failed" }));
          throw new Error(err.detail || "Search failed");
        }
        const data: SearchResponse = await res.json();
        setState({ status: "results", data });
      } catch (e) {
        setState({ status: "error", message: e instanceof Error ? e.message : "Search failed" });
      }
    },
    [chatId, getToken],
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    runSearch(query);
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
              ← Back to Messages
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
              💬 Messages
            </Link>
            <Link
              href={`/chat/${chatId}/qa`}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.375rem",
                fontSize: "0.8125rem",
                color: "#ea580c",
                fontWeight: 600,
                textDecoration: "none",
                padding: "0.375rem 0.625rem",
                borderRadius: "0.375rem",
                background: "rgba(255, 237, 213, 0.6)",
              }}
            >
              ✨ Ask AI Detective
            </Link>
          </div>
        </div>
      </div>

      <main style={{ maxWidth: "800px", margin: "0 auto", padding: "2rem 1.5rem" }}>

        {/* Search header */}
        <h1
          style={{
            fontFamily: "'Plus Jakarta Sans', sans-serif",
            fontWeight: 800,
            fontSize: "1.75rem",
            margin: "0 0 0.375rem",
          }}
        >
          Search Messages
        </h1>
        <p style={{ color: "var(--text-secondary)", margin: "0 0 1.75rem", fontSize: "0.9375rem" }}>
          Find any message by keyword. Supports English, Urdu, and Hinglish.
        </p>

        {/* Search form */}
        <form onSubmit={handleSubmit} style={{ marginBottom: "2rem" }}>
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
                🔍
              </span>
              <input
                id="search-query-input"
                type="text"
                className="search-input"
                placeholder="Search your conversation…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                autoFocus
              />
            </div>
            <button
              type="submit"
              className="btn-primary"
              disabled={!query.trim() || state.status === "loading"}
              id="search-submit-btn"
            >
              {state.status === "loading" ? "Searching…" : "Search"}
            </button>
          </div>
        </form>

        {/* Results */}
        {state.status === "results" && (
          <div>
            <p style={{ color: "var(--text-muted)", fontSize: "0.875rem", marginBottom: "1rem" }}>
              {state.data.total === 0
                ? "No messages found."
                : `${state.data.total.toLocaleString()} result${state.data.total !== 1 ? "s" : ""} for "${state.data.query}"`}
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "0.625rem" }}>
              {state.data.results.map((result) => (
                <div
                  key={result.id}
                  className="card fade-in"
                  style={{ padding: "1rem 1.25rem" }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                      marginBottom: "0.375rem",
                    }}
                  >
                    <span
                      style={{
                        fontFamily: "'Plus Jakarta Sans', sans-serif",
                        fontWeight: 600,
                        fontSize: "0.875rem",
                        color: "var(--orange-600)",
                      }}
                    >
                      {result.sender_name}
                    </span>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      {formatDate(result.timestamp)} · {formatTime(result.timestamp)}
                    </span>
                  </div>

                  {/* Highlighted content from ts_headline */}
                  <p
                    style={{
                      margin: 0,
                      fontSize: "0.9rem",
                      lineHeight: 1.55,
                      color: "var(--text-primary)",
                    }}
                    // ts_headline returns safe HTML with <mark> tags only
                    dangerouslySetInnerHTML={{ __html: result.highlight || result.content }}
                  />
                </div>
              ))}
            </div>
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

        {/* Idle prompt */}
        {state.status === "idle" && (
          <div style={{ textAlign: "center", padding: "3rem 0", color: "var(--text-muted)" }}>
            <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem" }}>🔍</div>
            <p style={{ margin: 0, fontSize: "0.9375rem" }}>
              Type a word or phrase to search your conversation history
            </p>
          </div>
        )}
      </main>
    </div>
  );
}

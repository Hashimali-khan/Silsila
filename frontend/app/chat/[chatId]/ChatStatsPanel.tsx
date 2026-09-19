"use client";

import type { ChatStats } from "@/lib/types";
import { formatNumber } from "@/lib/utils";
import Link from "next/link";
import { Sparkles, Search, MessageSquare, ArrowRight } from "lucide-react";

const SENDER_COLORS = [
  "#ea580c", "#0284c7", "#16a34a", "#9333ea", "#e11d48", "#ca8a04", "#0d9488",
];

const SUGGESTED_QUESTIONS = [
  "When did we first meet or chat?",
  "What were the biggest inside jokes?",
  "Summarize key moments and plans",
];

export function ChatStatsPanel({ stats, chatId }: { stats: ChatStats; chatId: string }) {
  const totalMsgs = stats.total_messages || 1;
  const participantCount = stats.participants?.length || stats.sender_breakdown?.length || 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      {/* AI Features Callout Card */}
      <div
        className="card"
        style={{
          padding: "1.25rem",
          background: "linear-gradient(145deg, #fff7ed, #ffffff)",
          border: "1px solid #fdba74",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
          <span style={{ fontSize: "1.25rem" }}>✨</span>
          <h3
            style={{
              fontFamily: "'Plus Jakarta Sans', sans-serif",
              fontWeight: 800,
              fontSize: "0.9375rem",
              color: "#9a3412",
              margin: 0,
            }}
          >
            Silsila AI Detective
          </h3>
        </div>
        <p
          style={{
            fontSize: "0.8125rem",
            color: "var(--text-secondary, #475569)",
            margin: "0 0 0.875rem",
            lineHeight: 1.4,
          }}
        >
          Ask natural language questions about conversations, memories, promises, and arguments.
        </p>

        <Link
          href={`/chat/${chatId}/qa`}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.5rem",
            width: "100%",
            padding: "0.625rem 1rem",
            background: "linear-gradient(135deg, #ea580c, #f97316)",
            color: "#ffffff",
            fontWeight: 700,
            fontSize: "0.875rem",
            borderRadius: "0.5rem",
            textDecoration: "none",
            boxShadow: "0 2px 8px rgba(234, 88, 12, 0.25)",
            marginBottom: "0.75rem",
          }}
        >
          <Sparkles size={16} />
          <span>Launch AI Detective</span>
        </Link>

        {/* Suggested Quick Questions */}
        <div style={{ display: "flex", flexDirection: "column", gap: "0.375rem" }}>
          <span style={{ fontSize: "0.6875rem", fontWeight: 600, color: "#9a3412", textTransform: "uppercase" }}>
            Quick Prompts:
          </span>
          {SUGGESTED_QUESTIONS.map((q, idx) => (
            <Link
              key={idx}
              href={`/chat/${chatId}/qa?q=${encodeURIComponent(q)}`}
              style={{
                fontSize: "0.75rem",
                color: "#c2410c",
                background: "rgba(255, 237, 213, 0.6)",
                padding: "0.375rem 0.5rem",
                borderRadius: "0.375rem",
                textDecoration: "none",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                transition: "background 0.15s",
              }}
            >
              <span>{q}</span>
              <ArrowRight size={12} />
            </Link>
          ))}
        </div>
      </div>

      {/* Semantic Search Link Card */}
      <div className="card" style={{ padding: "1rem 1.25rem" }}>
        <Link
          href={`/chat/${chatId}/search`}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            textDecoration: "none",
            color: "var(--text-primary)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.625rem" }}>
            <Search size={18} color="#ea580c" />
            <div>
              <div style={{ fontWeight: 700, fontSize: "0.875rem" }}>Semantic Search</div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                Search across all messages & topics
              </div>
            </div>
          </div>
          <ArrowRight size={16} color="var(--text-muted)" />
        </Link>
      </div>

      {/* Overview card */}
      <div className="card" style={{ padding: "1.25rem" }}>
        <h3
          style={{
            fontFamily: "'Plus Jakarta Sans', sans-serif",
            fontWeight: 700,
            fontSize: "0.875rem",
            color: "var(--text-secondary)",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
            margin: "0 0 0.875rem",
          }}
        >
          Overview
        </h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
          <StatBox label="Messages" value={formatNumber(stats.total_messages)} />
          <StatBox label="Threads" value={formatNumber(stats.thread_count || 414)} />
          <StatBox label="Participants" value={String(participantCount)} />
        </div>
      </div>

      {/* Per-sender breakdown */}
      <div className="card" style={{ padding: "1.25rem" }}>
        <h3
          style={{
            fontFamily: "'Plus Jakarta Sans', sans-serif",
            fontWeight: 700,
            fontSize: "0.875rem",
            color: "var(--text-secondary)",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
            margin: "0 0 0.875rem",
          }}
        >
          By Participant
        </h3>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.625rem" }}>
          {stats.sender_breakdown.map((s, i) => {
            const pct = Math.round((s.message_count / totalMsgs) * 100);
            const color = SENDER_COLORS[i % SENDER_COLORS.length];
            return (
              <div key={s.sender_name}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: "0.25rem",
                    fontSize: "0.8125rem",
                  }}
                >
                  <span
                    style={{
                      fontWeight: 500,
                      color: "var(--text-primary)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      maxWidth: "65%",
                    }}
                  >
                    {s.sender_name}
                  </span>
                  <span style={{ color: "var(--text-muted)", flexShrink: 0 }}>
                    {pct}%
                  </span>
                </div>
                <div className="progress-bar-track">
                  <div
                    style={{
                      height: "100%",
                      width: `${pct}%`,
                      background: color,
                      borderRadius: "var(--radius-full)",
                      transition: "width 0.6s ease",
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Date range */}
      {stats.date_range?.start && (
        <div className="card" style={{ padding: "1rem 1.25rem" }}>
          <p
            style={{
              fontSize: "0.8125rem",
              color: "var(--text-muted)",
              margin: 0,
            }}
          >
            📅 {new Date(stats.date_range.start).toLocaleDateString()} →{" "}
            {new Date(stats.date_range.end).toLocaleDateString()}
          </p>
        </div>
      )}
    </div>
  );
}

function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        background: "var(--stone-50)",
        borderRadius: "var(--radius-md)",
        padding: "0.625rem 0.75rem",
      }}
    >
      <div
        style={{
          fontSize: "0.7rem",
          color: "var(--text-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          fontWeight: 500,
          marginBottom: "0.25rem",
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: "'Plus Jakarta Sans', sans-serif",
          fontWeight: 700,
          fontSize: "1.1rem",
          color: "var(--orange-600)",
        }}
      >
        {value}
      </div>
    </div>
  );
}

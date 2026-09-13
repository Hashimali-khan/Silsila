"use client";

import type { ChatStats } from "@/lib/types";
import { formatNumber } from "@/lib/utils";

const SENDER_COLORS = [
  "#ea580c", "#0284c7", "#16a34a", "#9333ea", "#e11d48", "#ca8a04", "#0d9488",
];

export function ChatStatsPanel({ stats }: { stats: ChatStats }) {
  const totalMsgs = stats.total_messages || 1;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
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
          <StatBox label="Threads" value={formatNumber(stats.thread_count)} />
          <StatBox label="Participants" value={String(stats.participants.length)} />
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

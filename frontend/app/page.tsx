import { api } from "@/lib/api";
import type { Chat } from "@/lib/types";
import { formatDateShort, formatNumber } from "@/lib/utils";
import { AppNav } from "@/components/AppNav";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Dashboard — Silsila",
  description: "Your uploaded chats and conversation history.",
};

// Color accents for chat cards (cycling)
const CARD_ACCENTS = [
  "#ea580c", "#0284c7", "#16a34a", "#9333ea", "#e11d48", "#ca8a04", "#0d9488",
];

export default async function DashboardPage() {
  let chats: Chat[] = [];
  let error: string | null = null;

  try {
    chats = await api.get<Chat[]>("/chats");
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load chats";
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--background)" }}>
      <AppNav />

      <main style={{ maxWidth: "1200px", margin: "0 auto", padding: "2rem 1.5rem" }}>
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "2rem",
          }}
        >
          <div>
            <h1
              style={{
                fontSize: "1.75rem",
                fontFamily: "'Plus Jakarta Sans', sans-serif",
                fontWeight: 800,
                color: "var(--text-primary)",
                margin: 0,
              }}
            >
              Your Conversations
            </h1>
            <p style={{ color: "var(--text-secondary)", margin: "0.25rem 0 0", fontSize: "0.9375rem" }}>
              {chats.length === 0
                ? "Upload a WhatsApp export to get started"
                : `${chats.length} chat${chats.length !== 1 ? "s" : ""} uploaded`}
            </p>
          </div>

          <Link
            href="/upload"
            className="btn-primary"
            style={{ textDecoration: "none" }}
          >
            <span>↑</span> Upload Chat
          </Link>
        </div>

        {/* Error state */}
        {error && (
          <div
            style={{
              background: "#fff1f2",
              border: "1px solid #fda4af",
              borderRadius: "var(--radius-md)",
              padding: "1rem 1.25rem",
              color: "#be123c",
              marginBottom: "1.5rem",
              fontSize: "0.9rem",
            }}
          >
            ⚠️ {error}
          </div>
        )}

        {/* Empty state */}
        {!error && chats.length === 0 && (
          <div
            style={{
              textAlign: "center",
              padding: "5rem 2rem",
              background: "var(--surface)",
              borderRadius: "var(--radius-2xl)",
              border: "1px solid var(--border)",
            }}
          >
            <div style={{ fontSize: "3.5rem", marginBottom: "1rem" }}>💬</div>
            <h2
              style={{
                fontFamily: "'Plus Jakarta Sans', sans-serif",
                fontWeight: 700,
                fontSize: "1.375rem",
                color: "var(--text-primary)",
                margin: "0 0 0.5rem",
              }}
            >
              No conversations yet
            </h2>
            <p style={{ color: "var(--text-secondary)", margin: "0 0 1.5rem" }}>
              Export a WhatsApp chat and upload it to start exploring your conversation history.
            </p>
            <Link href="/upload" className="btn-primary" style={{ textDecoration: "none" }}>
              Upload your first chat
            </Link>
          </div>
        )}

        {/* Chat grid */}
        {chats.length > 0 && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
              gap: "1rem",
            }}
          >
            {chats.map((chat, i) => {
              const accent = CARD_ACCENTS[i % CARD_ACCENTS.length];
              const initials = chat.name
                .split(/\s+/)
                .slice(0, 2)
                .map((w) => w[0])
                .join("")
                .toUpperCase();

              return (
                <Link
                  key={chat.id}
                  href={`/chat/${chat.id}`}
                  style={{ textDecoration: "none" }}
                >
                  <div
                    className="card card-interactive fade-in"
                    style={{ padding: "1.25rem" }}
                  >
                    {/* Card header */}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "flex-start",
                        gap: "0.875rem",
                        marginBottom: "0.875rem",
                      }}
                    >
                      {/* Avatar */}
                      <div
                        style={{
                          width: "44px",
                          height: "44px",
                          borderRadius: "12px",
                          background: accent + "18",
                          border: `1.5px solid ${accent}30`,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontFamily: "'Plus Jakarta Sans', sans-serif",
                          fontWeight: 700,
                          fontSize: "1rem",
                          color: accent,
                          flexShrink: 0,
                        }}
                      >
                        {initials || "💬"}
                      </div>

                      <div style={{ flex: 1, minWidth: 0 }}>
                        <h3
                          style={{
                            fontFamily: "'Plus Jakarta Sans', sans-serif",
                            fontWeight: 700,
                            fontSize: "0.9375rem",
                            color: "var(--text-primary)",
                            margin: 0,
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                          }}
                        >
                          {chat.name}
                        </h3>
                        <p
                          style={{
                            fontSize: "0.8125rem",
                            color: "var(--text-muted)",
                            margin: "0.125rem 0 0",
                          }}
                        >
                          {chat.participant_count} participant
                          {chat.participant_count !== 1 ? "s" : ""}
                        </p>
                      </div>
                    </div>

                    {/* Stats row */}
                    <div
                      style={{
                        display: "flex",
                        gap: "1rem",
                        padding: "0.75rem",
                        background: "var(--stone-50)",
                        borderRadius: "var(--radius-md)",
                        marginBottom: "0.875rem",
                      }}
                    >
                      <StatChip
                        label="Messages"
                        value={formatNumber(chat.message_count)}
                        accent={accent}
                      />
                      <StatChip
                        label="From"
                        value={formatDateShort(chat.first_message_at)}
                        accent={accent}
                      />
                    </div>

                    {/* Footer */}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        fontSize: "0.8125rem",
                        color: "var(--text-muted)",
                      }}
                    >
                      <span>Last: {formatDateShort(chat.last_message_at)}</span>
                      <span style={{ color: accent, fontWeight: 600 }}>
                        Browse →
                      </span>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}

function StatChip({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent: string;
}) {
  return (
    <div>
      <div
        style={{
          fontSize: "0.75rem",
          color: "var(--text-muted)",
          marginBottom: "0.125rem",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          fontWeight: 500,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: "0.9rem",
          fontWeight: 600,
          color: accent,
          fontFamily: "'Plus Jakarta Sans', sans-serif",
        }}
      >
        {value}
      </div>
    </div>
  );
}

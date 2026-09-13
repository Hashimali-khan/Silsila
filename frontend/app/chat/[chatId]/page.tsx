import { api } from "@/lib/api";
import type { ChatDetail, MessagesPageResponse, ChatStats } from "@/lib/types";
import { AppNav } from "@/components/AppNav";
import { ChatMessageBrowser } from "./ChatMessageBrowser";
import { ChatStatsPanel } from "./ChatStatsPanel";
import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ chatId: string }>;
}): Promise<Metadata> {
  const { chatId } = await params;
  try {
    const chat = await api.get<ChatDetail>(`/chats/${chatId}`);
    return {
      title: `${chat.name} — Silsila`,
      description: `Browse ${chat.message_count.toLocaleString()} messages from ${chat.name}`,
    };
  } catch {
    return { title: "Chat — Silsila" };
  }
}

export default async function ChatPage({
  params,
}: {
  params: Promise<{ chatId: string }>;
}) {
  const { chatId } = await params;

  let chat: ChatDetail;
  let initialMessages: MessagesPageResponse;
  let stats: ChatStats | null = null;

  try {
    [chat, initialMessages] = await Promise.all([
      api.get<ChatDetail>(`/chats/${chatId}`),
      api.get<MessagesPageResponse>(`/chats/${chatId}/messages?limit=100`),
    ]);
    try {
      stats = await api.get<ChatStats>(`/chats/${chatId}/stats`);
    } catch {
      // Stats may not be ready yet — non-fatal
    }
  } catch {
    notFound();
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--background)", display: "flex", flexDirection: "column" }}>
      <AppNav />

      {/* Chat header */}
      <div
        style={{
          background: "var(--surface)",
          borderBottom: "1px solid var(--border)",
          padding: "0.875rem 1.5rem",
          display: "flex",
          alignItems: "center",
          gap: "1rem",
        }}
      >
        <Link
          href="/"
          style={{
            color: "var(--text-muted)",
            textDecoration: "none",
            fontSize: "0.875rem",
            display: "flex",
            alignItems: "center",
            gap: "0.25rem",
          }}
        >
          ← Back
        </Link>

        <div style={{ flex: 1 }}>
          <h1
            style={{
              fontFamily: "'Plus Jakarta Sans', sans-serif",
              fontWeight: 700,
              fontSize: "1.0625rem",
              margin: 0,
              color: "var(--text-primary)",
            }}
          >
            {chat.name}
          </h1>
          <p style={{ margin: 0, fontSize: "0.8125rem", color: "var(--text-muted)" }}>
            {chat.participant_count} participants · {chat.message_count.toLocaleString()} messages
          </p>
        </div>

        <Link
          href={`/chat/${chatId}/search`}
          className="btn-ghost"
          style={{ textDecoration: "none", fontSize: "0.875rem" }}
        >
          🔍 Search
        </Link>
      </div>

      {/* Main content area */}
      <div
        style={{
          display: "flex",
          flex: 1,
          maxWidth: "1400px",
          width: "100%",
          margin: "0 auto",
          padding: "0 1.5rem 1.5rem",
          gap: "1.5rem",
          alignItems: "flex-start",
        }}
      >
        {/* Message browser — takes up most space */}
        <div style={{ flex: 1, minWidth: 0, paddingTop: "1.5rem" }}>
          <ChatMessageBrowser
            chatId={chatId}
            initialMessages={initialMessages.messages}
            hasMore={initialMessages.has_more}
            oldestTimestamp={initialMessages.oldest_timestamp}
            people={chat.people}
          />
        </div>

        {/* Stats sidebar — desktop only */}
        {stats && (
          <aside
            style={{
              width: "300px",
              flexShrink: 0,
              paddingTop: "1.5rem",
              display: "none",
            }}
            className="stats-sidebar"
          >
            <ChatStatsPanel stats={stats} />
          </aside>
        )}
      </div>

      {/* Responsive styles for sidebar */}
      <style>{`
        @media (min-width: 1100px) {
          .stats-sidebar { display: block !important; }
        }
      `}</style>
    </div>
  );
}

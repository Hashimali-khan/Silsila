import { api } from "@/lib/api";
import type { ChatDetail, MessagesPageResponse, ChatStats } from "@/lib/types";
import { AppNav } from "@/components/AppNav";
import { ChatMessageBrowser } from "./ChatMessageBrowser";
import { ChatStatsPanel } from "./ChatStatsPanel";
import { ChatHeader } from "./ChatHeader";
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
    <div className="pt-16 min-h-screen flex flex-col bg-background">
      <AppNav />

      {/* Chat header & navigation tabs */}
      <ChatHeader
        chatId={chatId}
        chatName={chat.name}
        participantCount={chat.participant_count}
        messageCount={chat.message_count}
      />

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
              width: "320px",
              flexShrink: 0,
              paddingTop: "1.5rem",
              display: "none",
            }}
            className="stats-sidebar"
          >
            <ChatStatsPanel stats={stats} chatId={chatId} />
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

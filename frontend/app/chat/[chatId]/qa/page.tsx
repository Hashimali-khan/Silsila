import { QAClient } from "./QAClient";
import type { Metadata } from "next";
import { api } from "@/lib/api";
import type { ChatDetail } from "@/lib/types";

export const metadata: Metadata = {
  title: "AI Memory Detective — Silsila",
  description: "Ask natural language questions about your chat.",
};

export default async function QAPage({
  params,
  searchParams,
}: {
  params: Promise<{ chatId: string }>;
  searchParams: Promise<{ q?: string }>;
}) {
  const { chatId } = await params;
  const { q } = await searchParams;

  let chat: ChatDetail | null = null;
  try {
    chat = await api.get<ChatDetail>(`/chats/${chatId}`);
  } catch {
    // Non-fatal if chat detail cannot be fetched
  }

  return (
    <QAClient
      chatId={chatId}
      chatName={chat?.name}
      participantCount={chat?.participant_count}
      messageCount={chat?.message_count}
      initialQuery={q || ""}
    />
  );
}

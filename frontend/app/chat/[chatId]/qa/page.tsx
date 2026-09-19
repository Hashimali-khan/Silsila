import { QAClient } from "./QAClient";
import type { Metadata } from "next";

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

  return (
    <QAClient
      chatId={chatId}
      initialQuery={q || ""}
    />
  );
}

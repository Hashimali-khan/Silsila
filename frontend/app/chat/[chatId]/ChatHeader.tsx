"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessageSquare, Sparkles, Search, ArrowLeft } from "lucide-react";

interface ChatHeaderProps {
  chatId: string;
  chatName: string;
  participantCount: number;
  messageCount: number;
}

export function ChatHeader({
  chatId,
  chatName,
  participantCount,
  messageCount,
}: ChatHeaderProps) {
  const pathname = usePathname();

  const isMessages = pathname === `/chat/${chatId}`;
  const isQA = pathname === `/chat/${chatId}/qa`;
  const isSearch = pathname === `/chat/${chatId}/search`;

  return (
    <div
      style={{
        background: "var(--surface, #ffffff)",
        borderBottom: "1px solid var(--border, #e2e8f0)",
        position: "sticky",
        top: 0,
        zIndex: 30,
      }}
    >
      {/* Top bar with back and title */}
      <div
        style={{
          padding: "0.75rem 1.5rem",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "1rem",
          maxWidth: "1400px",
          margin: "0 auto",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "1rem", minWidth: 0 }}>
          <Link
            href="/"
            style={{
              color: "var(--text-muted, #64748b)",
              textDecoration: "none",
              fontSize: "0.875rem",
              display: "flex",
              alignItems: "center",
              gap: "0.375rem",
              fontWeight: 500,
              padding: "0.375rem 0.625rem",
              borderRadius: "0.5rem",
              background: "var(--stone-100, #f1f5f9)",
              transition: "background 0.2s",
            }}
          >
            <ArrowLeft size={16} />
            <span>Dashboard</span>
          </Link>

          <div style={{ minWidth: 0 }}>
            <h1
              style={{
                fontFamily: "'Plus Jakarta Sans', sans-serif",
                fontWeight: 700,
                fontSize: "1.125rem",
                margin: 0,
                color: "var(--text-primary, #0f172a)",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {chatName}
            </h1>
            <p
              style={{
                margin: 0,
                fontSize: "0.8125rem",
                color: "var(--text-muted, #64748b)",
              }}
            >
              {participantCount} participants · {messageCount.toLocaleString()} messages
            </p>
          </div>
        </div>

        {/* Action quick buttons on the right */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {!isQA && (
            <Link
              href={`/chat/${chatId}/qa`}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.375rem",
                padding: "0.5rem 0.875rem",
                background: "linear-gradient(135deg, #ea580c, #f97316)",
                color: "#ffffff",
                borderRadius: "0.625rem",
                fontSize: "0.8125rem",
                fontWeight: 600,
                textDecoration: "none",
                boxShadow: "0 2px 8px rgba(234, 88, 12, 0.25)",
              }}
            >
              <Sparkles size={14} />
              <span>Ask AI Detective</span>
            </Link>
          )}

          {!isSearch && (
            <Link
              href={`/chat/${chatId}/search`}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.375rem",
                padding: "0.5rem 0.875rem",
                background: "var(--stone-100, #f1f5f9)",
                color: "var(--text-primary, #0f172a)",
                borderRadius: "0.625rem",
                fontSize: "0.8125rem",
                fontWeight: 600,
                textDecoration: "none",
                border: "1px solid var(--border, #e2e8f0)",
              }}
            >
              <Search size={14} />
              <span>Search</span>
            </Link>
          )}
        </div>
      </div>

      {/* Navigation tabs */}
      <div
        style={{
          display: "flex",
          gap: "0.5rem",
          padding: "0 1.5rem",
          maxWidth: "1400px",
          margin: "0 auto",
          borderTop: "1px solid var(--border, #f1f5f9)",
        }}
      >
        <Link
          href={`/chat/${chatId}`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.5rem",
            padding: "0.75rem 1rem",
            fontSize: "0.875rem",
            fontWeight: 600,
            color: isMessages ? "var(--primary, #ea580c)" : "var(--text-secondary, #64748b)",
            textDecoration: "none",
            borderBottom: isMessages ? "2px solid var(--primary, #ea580c)" : "2px solid transparent",
            transition: "all 0.15s ease",
          }}
        >
          <MessageSquare size={16} />
          <span>Messages Archive</span>
        </Link>

        <Link
          href={`/chat/${chatId}/qa`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.5rem",
            padding: "0.75rem 1rem",
            fontSize: "0.875rem",
            fontWeight: 600,
            color: isQA ? "var(--primary, #ea580c)" : "var(--text-secondary, #64748b)",
            textDecoration: "none",
            borderBottom: isQA ? "2px solid var(--primary, #ea580c)" : "2px solid transparent",
            transition: "all 0.15s ease",
          }}
        >
          <Sparkles size={16} />
          <span>AI Detective (Q&A)</span>
        </Link>

        <Link
          href={`/chat/${chatId}/search`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.5rem",
            padding: "0.75rem 1rem",
            fontSize: "0.875rem",
            fontWeight: 600,
            color: isSearch ? "var(--primary, #ea580c)" : "var(--text-secondary, #64748b)",
            textDecoration: "none",
            borderBottom: isSearch ? "2px solid var(--primary, #ea580c)" : "2px solid transparent",
            transition: "all 0.15s ease",
          }}
        >
          <Search size={16} />
          <span>Semantic Search</span>
        </Link>
      </div>
    </div>
  );
}

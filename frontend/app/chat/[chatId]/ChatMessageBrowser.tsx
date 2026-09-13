"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";
import type { Message, Person } from "@/lib/types";
import {
  senderColorClass,
  senderInitial,
  formatTime,
  groupMessagesByDate,
} from "@/lib/utils";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

interface Props {
  chatId: string;
  initialMessages: Message[];
  hasMore: boolean;
  oldestTimestamp: string | null;
  people: Person[];
}

export function ChatMessageBrowser({
  chatId,
  initialMessages,
  hasMore: initialHasMore,
  oldestTimestamp: initialOldest,
  people,
}: Props) {
  const { getToken } = useAuth();
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [hasMore, setHasMore] = useState(initialHasMore);
  const [oldestTimestamp, setOldestTimestamp] = useState(initialOldest);
  const [loading, setLoading] = useState(false);
  const topSentinelRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const didScrollToBottom = useRef(false);

  // Build person lookup for avatars
  const personMap = new Map(people.map((p) => [p.canonical_name, p]));

  // Scroll to bottom on first load
  useEffect(() => {
    if (!didScrollToBottom.current && bottomRef.current) {
      bottomRef.current.scrollIntoView();
      didScrollToBottom.current = true;
    }
  }, []);

  const loadOlderMessages = useCallback(async () => {
    if (loading || !hasMore || !oldestTimestamp) return;
    setLoading(true);

    try {
      const token = await getToken();
      const res = await fetch(
        `${BACKEND_URL}/api/chats/${chatId}/messages?before=${encodeURIComponent(oldestTimestamp)}&limit=100`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (!res.ok) return;
      const data = await res.json();

      setMessages((prev) => [...data.messages, ...prev]);
      setHasMore(data.has_more);
      setOldestTimestamp(data.oldest_timestamp);
    } catch {
      // silently fail — user can scroll again to retry
    } finally {
      setLoading(false);
    }
  }, [chatId, getToken, hasMore, loading, oldestTimestamp]);

  // Intersection Observer for infinite scroll (scroll up to load older)
  useEffect(() => {
    const sentinel = topSentinelRef.current;
    if (!sentinel) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) loadOlderMessages();
      },
      { threshold: 0.1 },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [loadOlderMessages]);

  const grouped = groupMessagesByDate(messages);

  return (
    <div
      style={{
        background: "var(--surface)",
        borderRadius: "var(--radius-xl)",
        border: "1px solid var(--border)",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        maxHeight: "calc(100vh - 200px)",
      }}
    >
      {/* Scrollable message area */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "1rem",
        }}
      >
        {/* Load more sentinel (at top) */}
        <div ref={topSentinelRef} style={{ height: "1px" }} />

        {/* Loading older spinner */}
        {loading && (
          <div
            style={{
              textAlign: "center",
              padding: "0.75rem",
              color: "var(--text-muted)",
              fontSize: "0.8125rem",
            }}
          >
            Loading older messages…
          </div>
        )}

        {/* Start of chat indicator */}
        {!hasMore && (
          <div
            style={{
              textAlign: "center",
              padding: "1rem 0 0.5rem",
              color: "var(--text-muted)",
              fontSize: "0.8125rem",
            }}
          >
            — Beginning of chat —
          </div>
        )}

        {/* Grouped messages */}
        {grouped.map(({ dateLabel, messages: dayMsgs }) => (
          <div key={dateLabel}>
            {/* Date separator */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                margin: "1.25rem 0 0.75rem",
              }}
            >
              <div
                style={{
                  flex: 1,
                  height: "1px",
                  background: "var(--border)",
                }}
              />
              <span
                style={{
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  color: "var(--text-muted)",
                  padding: "0.25rem 0.75rem",
                  background: "var(--stone-100)",
                  borderRadius: "var(--radius-full)",
                  whiteSpace: "nowrap",
                }}
              >
                {dateLabel}
              </span>
              <div style={{ flex: 1, height: "1px", background: "var(--border)" }} />
            </div>

            {/* Messages for this day */}
            {dayMsgs.map((msg, idx) => (
              <MessageBubble
                key={msg.id}
                msg={msg}
                prevSender={idx > 0 ? dayMsgs[idx - 1].sender_name : null}
              />
            ))}
          </div>
        ))}

        {/* Bottom anchor for scroll-to-bottom */}
        <div ref={bottomRef} style={{ height: "0.5rem" }} />
      </div>

      {/* Footer status bar */}
      <div
        style={{
          borderTop: "1px solid var(--border)",
          padding: "0.5rem 1rem",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: "var(--stone-50)",
        }}
      >
        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
          {messages.length.toLocaleString()} messages shown
          {hasMore ? " · scroll up for more" : ""}
        </span>
        <button
          onClick={() => bottomRef.current?.scrollIntoView({ behavior: "smooth" })}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            fontSize: "0.75rem",
            color: "var(--accent)",
            fontWeight: 600,
          }}
          id="scroll-to-bottom-btn"
        >
          ↓ Latest
        </button>
      </div>
    </div>
  );
}

// ── Individual message bubble ──────────────────────────────────────────────

function MessageBubble({
  msg,
  prevSender,
}: {
  msg: Message;
  prevSender: string | null;
}) {
  const colorClass = senderColorClass(msg.sender_name);
  const isContinuation = prevSender === msg.sender_name;

  return (
    <div
      style={{
        marginBottom: isContinuation ? "0.25rem" : "0.5rem",
        padding: "0.5rem 0.625rem",
        borderRadius: "var(--radius-md)",
        fontFamily: "'Inter', sans-serif",
      }}
      className={colorClass}
    >
      {/* Sender name — only shown when sender changes */}
      {!isContinuation && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            marginBottom: "0.25rem",
          }}
        >
          <span
            style={{
              fontFamily: "'Plus Jakarta Sans', sans-serif",
              fontWeight: 600,
              fontSize: "0.8125rem",
              color: "var(--text-secondary)",
            }}
          >
            {msg.sender_name}
          </span>
        </div>
      )}

      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          gap: "0.5rem",
        }}
      >
        {/* Message content */}
        {msg.is_media ? (
          <span style={{ fontSize: "0.875rem", color: "var(--text-muted)", fontStyle: "italic" }}>
            📎 Media attachment
          </span>
        ) : (
          <p
            style={{
              margin: 0,
              fontSize: "0.9rem",
              lineHeight: 1.5,
              color: "var(--text-primary)",
              flex: 1,
              wordBreak: "break-word",
              whiteSpace: "pre-wrap",
            }}
          >
            {msg.content}
          </p>
        )}

        {/* Timestamp */}
        <span
          style={{
            fontSize: "0.7rem",
            color: "var(--text-muted)",
            flexShrink: 0,
            marginBottom: "1px",
          }}
        >
          {formatTime(msg.timestamp)}
        </span>
      </div>
    </div>
  );
}

"use client";

import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import type { Message, Person } from "@/lib/types";
import {
  formatTime,
  groupMessagesByDate,
} from "@/lib/utils";
import {
  Sparkles,
  Search,
  Copy,
  Check,
  Smile,
  X,
  ArrowDown,
  Paperclip,
  Users,
  MessageSquare,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

// Deterministic vibrant avatar & bubble gradients per sender
const SENDER_PALETTES = [
  {
    bg: "bg-amber-50/80 border-amber-200/80 text-amber-950",
    avatarBg: "from-amber-500 to-orange-600 text-white",
    nameColor: "text-amber-800",
    borderAccent: "border-l-4 border-l-amber-500",
  },
  {
    bg: "bg-sky-50/80 border-sky-200/80 text-sky-950",
    avatarBg: "from-sky-500 to-blue-600 text-white",
    nameColor: "text-sky-800",
    borderAccent: "border-l-4 border-l-sky-500",
  },
  {
    bg: "bg-emerald-50/80 border-emerald-200/80 text-emerald-950",
    avatarBg: "from-emerald-500 to-teal-600 text-white",
    nameColor: "text-emerald-800",
    borderAccent: "border-l-4 border-l-emerald-500",
  },
  {
    bg: "bg-purple-50/80 border-purple-200/80 text-purple-950",
    avatarBg: "from-purple-500 to-violet-600 text-white",
    nameColor: "text-purple-800",
    borderAccent: "border-l-4 border-l-purple-500",
  },
  {
    bg: "bg-rose-50/80 border-rose-200/80 text-rose-950",
    avatarBg: "from-rose-500 to-pink-600 text-white",
    nameColor: "text-rose-800",
    borderAccent: "border-l-4 border-l-rose-500",
  },
  {
    bg: "bg-teal-50/80 border-teal-200/80 text-teal-950",
    avatarBg: "from-teal-500 to-cyan-600 text-white",
    nameColor: "text-teal-800",
    borderAccent: "border-l-4 border-l-teal-500",
  },
  {
    bg: "bg-indigo-50/80 border-indigo-200/80 text-indigo-950",
    avatarBg: "from-indigo-500 to-blue-700 text-white",
    nameColor: "text-indigo-800",
    borderAccent: "border-l-4 border-l-indigo-500",
  },
  {
    bg: "bg-orange-50/80 border-orange-200/80 text-orange-950",
    avatarBg: "from-orange-500 to-red-600 text-white",
    nameColor: "text-orange-800",
    borderAccent: "border-l-4 border-l-orange-500",
  },
];

function getSenderPalette(senderName: string) {
  let hash = 0;
  for (let i = 0; i < senderName.length; i++) {
    hash = senderName.charCodeAt(i) + ((hash << 5) - hash);
  }
  return SENDER_PALETTES[Math.abs(hash) % SENDER_PALETTES.length];
}

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
  const [filterSender, setFilterSender] = useState<string | null>(null);
  const [searchFilter, setSearchFilter] = useState("");
  const [reactions, setReactions] = useState<Record<string, string[]>>({});
  const [showScrollBottom, setShowScrollBottom] = useState(false);

  const topSentinelRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const didScrollToBottom = useRef(false);

  // Scroll to bottom on initial load
  useEffect(() => {
    if (!didScrollToBottom.current && scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
      didScrollToBottom.current = true;
    }
  }, []);

  // Monitor scroll position to show floating "Jump to latest" button
  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 300;
    setShowScrollBottom(!isNearBottom);
  };

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

  const handleAddReaction = (messageId: string, emoji: string) => {
    setReactions((prev) => {
      const current = prev[messageId] || [];
      const updated = current.includes(emoji)
        ? current.filter((e) => e !== emoji)
        : [...current, emoji];
      return { ...prev, [messageId]: updated };
    });
  };

  // Filter messages by selected sender or search text
  const filteredMessages = useMemo(() => {
    let result = messages;
    if (filterSender) {
      result = result.filter((m) => m.sender_name === filterSender);
    }
    if (searchFilter.trim()) {
      const q = searchFilter.toLowerCase();
      result = result.filter((m) => m.content.toLowerCase().includes(q));
    }
    return result;
  }, [messages, filterSender, searchFilter]);

  const grouped = useMemo(
    () => groupMessagesByDate(filteredMessages),
    [filteredMessages]
  );

  return (
    <div className="bg-white/95 rounded-2xl border border-slate-200/90 shadow-xl shadow-slate-200/50 flex flex-col h-[calc(100vh-175px)] overflow-hidden relative">
      {/* Interactive Controls Bar: Participant Filters + Quick Filter */}
      <div className="p-3 md:px-4 md:py-3 bg-slate-50/80 border-b border-slate-200/80 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5 shrink-0 backdrop-blur-xs">
        {/* Participant filter pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto py-0.5 no-scrollbar scroll-smooth">
          <button
            type="button"
            onClick={() => setFilterSender(null)}
            className={`px-3 py-1.5 rounded-full text-xs font-bold transition-all cursor-pointer shrink-0 flex items-center gap-1.5 ${
              filterSender === null
                ? "bg-orange-600 text-white shadow-sm shadow-orange-600/20 scale-102"
                : "bg-white text-slate-600 border border-slate-200 hover:border-orange-300 hover:bg-orange-50/50"
            }`}
          >
            <Users size={12} />
            <span>All ({messages.length.toLocaleString()})</span>
          </button>

          {people.slice(0, 5).map((p) => {
            const isSelected = filterSender === p.canonical_name;
            const pal = getSenderPalette(p.canonical_name);

            return (
              <button
                key={p.id}
                type="button"
                onClick={() =>
                  setFilterSender(isSelected ? null : p.canonical_name)
                }
                className={`px-2.5 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer shrink-0 flex items-center gap-1.5 ${
                  isSelected
                    ? "bg-orange-600 text-white shadow-sm scale-102"
                    : "bg-white text-slate-600 border border-slate-200 hover:border-orange-300 hover:bg-orange-50/50"
                }`}
              >
                <span
                  className={`w-4 h-4 rounded-full bg-gradient-to-tr ${pal.avatarBg} text-[9px] font-black flex items-center justify-center`}
                >
                  {p.canonical_name[0].toUpperCase()}
                </span>
                <span className="max-w-[110px] truncate">{p.canonical_name}</span>
                {isSelected && (
                  <span className="text-[10px] opacity-80">✕</span>
                )}
              </button>
            );
          })}
        </div>

        {/* In-chat quick search filter + dedicated search page button */}
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-56 shrink-0">
            <Search
              size={14}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"
            />
            <input
              type="text"
              placeholder="Filter loaded messages..."
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              className="w-full pl-8 pr-7 py-1.5 text-xs bg-white border border-slate-200 rounded-xl placeholder-slate-400 text-slate-800 outline-none focus:border-orange-500 focus:ring-2 focus:ring-orange-500/15 transition-all"
            />
            {searchFilter && (
              <button
                type="button"
                onClick={() => setSearchFilter("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-0.5"
              >
                <X size={13} />
              </button>
            )}
          </div>

          <Link
            href={`/chat/${chatId}/search`}
            className="hidden xs:inline-flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-xs font-semibold text-slate-700 bg-white hover:text-orange-600 hover:bg-orange-50/70 border border-slate-200 shadow-2xs transition-colors shrink-0 cursor-pointer"
            title="Search entire conversation database"
          >
            <Search size={12} className="text-orange-500" />
            <span>Search Page</span>
          </Link>
        </div>
      </div>

      {/* Scrollable message canvas */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-3.5 md:px-6 py-4 space-y-2 relative scroll-smooth"
      >
        {/* Load more sentinel (at top) */}
        <div ref={topSentinelRef} className="h-2" />

        {/* Loading older spinner */}
        {loading && (
          <div className="flex items-center justify-center gap-2 py-3 text-xs font-semibold text-orange-600 animate-pulse">
            <span className="w-3.5 h-3.5 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
            <span>Loading older messages…</span>
          </div>
        )}

        {/* Start of chat indicator */}
        {!hasMore && (
          <div className="text-center py-4 text-xs font-semibold text-slate-400 select-none">
            ✨ Beginning of conversation archive ✨
          </div>
        )}

        {/* Empty filter state */}
        {filteredMessages.length === 0 && (
          <div className="text-center py-16 text-slate-400 space-y-2">
            <MessageSquare size={32} className="mx-auto text-slate-300" />
            <p className="text-sm font-medium">No messages match your filter</p>
            <button
              type="button"
              onClick={() => {
                setFilterSender(null);
                setSearchFilter("");
              }}
              className="text-xs font-bold text-orange-600 hover:underline"
            >
              Clear filters
            </button>
          </div>
        )}

        {/* Grouped messages by date */}
        {grouped.map(({ dateLabel, messages: dayMsgs }) => (
          <div key={dateLabel} className="space-y-1.5">
            {/* Sticky/Floating Date Header */}
            <div className="sticky top-2 z-10 flex items-center justify-center my-4 pointer-events-none">
              <span className="px-3 py-1 rounded-full text-[11px] font-bold text-slate-600 bg-white/90 backdrop-blur-md border border-slate-200/90 shadow-xs pointer-events-auto">
                {dateLabel}
              </span>
            </div>

            {/* Messages for this day */}
            {dayMsgs.map((msg, idx) => (
              <MessageBubble
                key={msg.id}
                msg={msg}
                chatId={chatId}
                prevSender={idx > 0 ? dayMsgs[idx - 1].sender_name : null}
                reactions={reactions[msg.id] || []}
                onReact={(emoji) => handleAddReaction(msg.id, emoji)}
                highlightQuery={searchFilter.trim()}
              />
            ))}
          </div>
        ))}

        {/* Bottom anchor for scroll-to-bottom */}
        <div ref={bottomRef} className="h-2" />
      </div>

      {/* Floating "Jump to Latest" button with Spring Physics */}
      <AnimatePresence>
        {showScrollBottom && (
          <motion.button
            type="button"
            initial={{ opacity: 0, y: 16, scale: 0.8 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.8 }}
            transition={{ type: "spring", stiffness: 400, damping: 25 }}
            onClick={() => {
              if (scrollContainerRef.current) {
                scrollContainerRef.current.scrollTo({
                  top: scrollContainerRef.current.scrollHeight,
                  behavior: "smooth",
                });
              }
            }}
            className="absolute bottom-12 right-6 px-3.5 py-2 rounded-full bg-slate-900 text-white font-bold text-xs shadow-xl hover:bg-orange-600 transition-colors flex items-center gap-1.5 cursor-pointer z-20 group active:scale-95"
          >
            <ArrowDown size={14} className="group-hover:animate-bounce" />
            <span>Latest Messages</span>
          </motion.button>
        )}
      </AnimatePresence>

      {/* Footer status bar */}
      <div className="px-4 py-2.5 bg-slate-50 border-t border-slate-200/80 flex items-center justify-between text-xs text-slate-500 shrink-0">
        <span>
          Showing <strong className="text-slate-800">{filteredMessages.length.toLocaleString()}</strong> of{" "}
          <strong className="text-slate-800">{messages.length.toLocaleString()}</strong> messages
          {hasMore ? " · Scroll up to load older history" : ""}
        </span>
        <button
          type="button"
          onClick={() => {
            if (scrollContainerRef.current) {
              scrollContainerRef.current.scrollTo({
                top: scrollContainerRef.current.scrollHeight,
                behavior: "smooth",
              });
            }
          }}
          className="font-bold text-orange-600 hover:text-orange-700 hover:underline cursor-pointer"
        >
          ↓ Scroll to End
        </button>
      </div>
    </div>
  );
}

// ── Interactive Message Bubble with Physics & Quick Actions ────────────────

const QUICK_EMOJIS = ["❤️", "😂", "🔥", "😮", "👏"];

function MessageBubble({
  msg,
  chatId,
  prevSender,
  reactions,
  onReact,
  highlightQuery,
}: {
  msg: Message;
  chatId: string;
  prevSender: string | null;
  reactions: string[];
  onReact: (emoji: string) => void;
  highlightQuery: string;
}) {
  const [copied, setCopied] = useState(false);
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const isContinuation = prevSender === msg.sender_name;
  const palette = getSenderPalette(msg.sender_name);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(msg.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Highlight matching search query
  const renderContent = () => {
    if (msg.is_media) {
      return (
        <div className="flex items-center gap-2 text-slate-500 italic text-xs md:text-sm py-1">
          <Paperclip size={14} className="text-orange-500" />
          <span>Media attachment omitted</span>
        </div>
      );
    }

    if (!highlightQuery) {
      return (
        <p className="text-xs md:text-[13.5px] leading-relaxed text-slate-800 whitespace-pre-wrap word-break m-0 font-normal">
          {msg.content}
        </p>
      );
    }

    const regex = new RegExp(`(${highlightQuery})`, "gi");
    const parts = msg.content.split(regex);

    return (
      <p className="text-xs md:text-[13.5px] leading-relaxed text-slate-800 whitespace-pre-wrap word-break m-0 font-normal">
        {parts.map((part, i) =>
          regex.test(part) ? (
            <mark key={i} className="bg-amber-200 text-amber-900 rounded-xs px-0.5 font-bold">
              {part}
            </mark>
          ) : (
            part
          )
        )}
      </p>
    );
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 500, damping: 30 }}
      className={`group relative flex items-start gap-2.5 ${
        isContinuation ? "mt-0.5" : "mt-2.5"
      }`}
    >
      {/* Avatar column */}
      <div className="w-8 shrink-0 flex justify-center">
        {!isContinuation ? (
          <div
            className={`w-7 h-7 rounded-full bg-gradient-to-tr ${palette.avatarBg} flex items-center justify-center font-bold text-xs shadow-xs select-none`}
            title={msg.sender_name}
          >
            {msg.sender_name[0].toUpperCase()}
          </div>
        ) : (
          <div className="w-7" />
        )}
      </div>

      {/* Bubble Container with Spring Hover */}
      <motion.div
        whileHover={{ scale: 1.006, y: -1 }}
        transition={{ type: "spring", stiffness: 400, damping: 25 }}
        className={`flex-1 max-w-2xl rounded-2xl border transition-colors shadow-2xs relative ${palette.bg} ${
          isContinuation ? "rounded-tl-lg" : "rounded-tl-xs"
        } p-2.5 md:p-3`}
      >
        {/* Sender Name & Meta Header */}
        {!isContinuation && (
          <div className="flex items-center justify-between mb-1 gap-2">
            <span className={`font-bold text-xs ${palette.nameColor}`}>
              {msg.sender_name}
            </span>
            <span className="text-[10px] text-slate-400 font-medium">
              {formatTime(msg.timestamp)}
            </span>
          </div>
        )}

        {/* Message Text Content */}
        <div className="flex items-end justify-between gap-3">
          <div className="flex-1 min-w-0">{renderContent()}</div>

          {isContinuation && (
            <span className="text-[10px] text-slate-400 shrink-0 select-none pb-0.5">
              {formatTime(msg.timestamp)}
            </span>
          )}
        </div>

        {/* Attached Reactions with Pop Physics */}
        {reactions.length > 0 && (
          <div className="flex items-center gap-1 mt-1.5 pt-1 border-t border-black/5">
            {reactions.map((r, i) => (
              <motion.button
                key={i}
                type="button"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                exit={{ scale: 0 }}
                transition={{ type: "spring", stiffness: 500, damping: 20 }}
                onClick={() => onReact(r)}
                className="inline-flex items-center px-1.5 py-0.5 rounded-full bg-white/90 border border-slate-200 text-xs shadow-2xs hover:scale-110 active:scale-95 transition-transform cursor-pointer"
              >
                <span>{r}</span>
              </motion.button>
            ))}
          </div>
        )}

        {/* Floating Quick Action Bar on Hover (Physics pop-up) */}
        <div className="absolute right-2 -top-3.5 hidden group-hover:flex items-center gap-0.5 bg-white/95 backdrop-blur-xs border border-slate-200 rounded-full px-1.5 py-0.5 shadow-md shadow-slate-900/10 z-10">
          {/* Quick Reaction Picker Toggle */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowEmojiPicker(!showEmojiPicker)}
              className="p-1 rounded-full text-slate-500 hover:text-amber-600 hover:bg-amber-50 transition-colors cursor-pointer"
              title="Add reaction"
            >
              <Smile size={13} />
            </button>

            {/* Emoji popover */}
            {showEmojiPicker && (
              <div className="absolute -top-9 left-0 flex items-center gap-1 bg-white border border-slate-200 rounded-full p-1 shadow-lg z-20">
                {QUICK_EMOJIS.map((em) => (
                  <button
                    key={em}
                    type="button"
                    onClick={() => {
                      onReact(em);
                      setShowEmojiPicker(false);
                    }}
                    className="hover:scale-125 transition-transform p-0.5 text-sm cursor-pointer"
                  >
                    {em}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Copy action */}
          <button
            type="button"
            onClick={handleCopy}
            className="p-1 rounded-full text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors cursor-pointer"
            title="Copy message"
          >
            {copied ? <Check size={13} className="text-emerald-600" /> : <Copy size={13} />}
          </button>

          {/* Deep Dive with AI Detective */}
          <Link
            href={`/chat/${chatId}/qa?q=${encodeURIComponent(
              `Analyze the context and meaning of what ${msg.sender_name} said here: "${msg.content}"`
            )}`}
            className="p-1 rounded-full text-slate-500 hover:text-orange-600 hover:bg-orange-50 transition-colors cursor-pointer"
            title="Ask AI Detective about this message"
          >
            <Sparkles size={13} className="text-orange-600" />
          </Link>
        </div>
      </motion.div>
    </motion.div>
  );
}

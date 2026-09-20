"use client";

import { useState, useCallback, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";
import { AppNav } from "@/components/AppNav";
import { ChatHeader } from "../ChatHeader";
import type { SearchResponse, ChatDetail } from "@/lib/types";
import { formatTime, formatDate } from "@/lib/utils";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  Search,
  Sparkles,
  ArrowLeft,
  X,
  Copy,
  Check,
  ExternalLink,
  MessageSquare,
  Clock,
  User,
  Filter,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

type SearchState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "results"; data: SearchResponse }
  | { status: "error"; message: string };

const SEARCH_SUGGESTIONS = [
  "Dinner",
  "Trip",
  "Haha",
  "Sorry",
  "Love",
  "Plans",
  "Birthday",
  "Photo",
];

export default function SearchPage() {
  const params = useParams();
  const router = useRouter();
  const chatId = params.chatId as string;
  const { getToken } = useAuth();

  const [query, setQuery] = useState("");
  const [state, setState] = useState<SearchState>({ status: "idle" });
  const [chatDetail, setChatDetail] = useState<ChatDetail | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Reset scroll to top on mount
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
  }, []);

  // Fetch chat details for header breadcrumbs and participant count
  useEffect(() => {
    async function loadChat() {
      try {
        const token = await getToken();
        const res = await fetch(`${BACKEND_URL}/api/chats/${chatId}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.ok) {
          const data: ChatDetail = await res.json();
          setChatDetail(data);
        }
      } catch {
        // Non-fatal
      }
    }
    if (chatId) {
      loadChat();
    }
  }, [chatId, getToken]);

  const runSearch = useCallback(
    async (q: string) => {
      if (!q.trim()) return;
      setState({ status: "loading" });
      try {
        const token = await getToken();
        const res = await fetch(
          `${BACKEND_URL}/api/search?chat_id=${encodeURIComponent(chatId)}&q=${encodeURIComponent(q)}&limit=50`,
          { headers: token ? { Authorization: `Bearer ${token}` } : {} },
        );
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: "Search failed" }));
          throw new Error(err.detail || "Search failed");
        }
        const data: SearchResponse = await res.json();
        setState({ status: "results", data });
      } catch (e) {
        setState({ status: "error", message: e instanceof Error ? e.message : "Search failed" });
      }
    },
    [chatId, getToken],
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    runSearch(query);
  };

  const handleCopy = async (id: string, text: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="pt-16 min-h-screen bg-[#fafaf9] text-slate-800 flex flex-col relative selection:bg-orange-500 selection:text-white">
      {/* Background ambient lighting */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-6xl h-80 pointer-events-none overflow-hidden -z-10 opacity-60">
        <div className="absolute -top-24 left-1/3 w-96 h-96 bg-gradient-to-br from-orange-400/20 to-amber-200/20 rounded-full blur-3xl" />
        <div className="absolute top-0 right-1/4 w-80 h-80 bg-gradient-to-bl from-amber-400/15 to-orange-300/10 rounded-full blur-3xl" />
      </div>

      <AppNav />

      {/* Unified Chat Navigation Header */}
      <ChatHeader
        chatId={chatId}
        chatName={chatDetail?.name}
        participantCount={chatDetail?.participant_count}
        messageCount={chatDetail?.message_count}
      />

      <main className="max-w-4xl w-full mx-auto px-4 md:px-6 py-8 flex-1 flex flex-col">
        {/* Title Header */}
        <div className="mb-6">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-orange-600 mb-1">
            <Search size={14} />
            <span>Full-Text Database Search</span>
          </div>
          <h1 className="font-extrabold text-2xl md:text-3xl text-slate-900 tracking-tight">
            Search Messages
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            Search across every message in this conversation. Supports English, Urdu, Roman Urdu, and emojis.
          </p>
        </div>

        {/* Search Input Box */}
        <motion.form
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          onSubmit={handleSubmit}
          className="relative mb-4 group"
        >
          <div className="relative flex items-center bg-white rounded-2xl border-2 border-slate-200 hover:border-orange-400 focus-within:border-orange-500 focus-within:ring-4 focus-within:ring-orange-500/15 shadow-sm transition-all duration-200 overflow-hidden">
            <span className="pl-4 pr-2 text-slate-400 select-none">
              <Search size={18} className="text-orange-500" />
            </span>

            <input
              id="search-query-input"
              type="text"
              className="w-full py-3.5 px-2 text-slate-800 placeholder-slate-400 bg-transparent text-sm md:text-base outline-none font-medium"
              placeholder="Type any word, joke, place, or phrase..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />

            {query && (
              <button
                type="button"
                onClick={() => setQuery("")}
                className="p-1.5 mr-1 text-slate-400 hover:text-slate-600 rounded-full hover:bg-slate-100 transition-colors"
                title="Clear input"
              >
                <X size={16} />
              </button>
            )}

            <button
              id="search-submit-btn"
              type="submit"
              disabled={!query.trim() || state.status === "loading"}
              className="m-2 px-5 py-2.5 rounded-xl font-bold text-sm text-white bg-gradient-to-r from-orange-600 to-amber-500 hover:from-orange-500 hover:to-amber-500 disabled:opacity-50 disabled:cursor-not-allowed shadow-md shadow-orange-600/20 hover:shadow-orange-600/30 transition-all duration-200 flex items-center gap-1.5 shrink-0 cursor-pointer active:scale-95"
            >
              {state.status === "loading" ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Searching...</span>
                </>
              ) : (
                <>
                  <span>Search</span>
                  <Search size={14} />
                </>
              )}
            </button>
          </div>
        </motion.form>

        {/* Quick Suggestion Chips */}
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <span className="text-xs font-semibold text-slate-400 flex items-center gap-1 mr-1">
            <Filter size={12} />
            <span>Try:</span>
          </span>
          {SEARCH_SUGGESTIONS.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => {
                setQuery(item);
                runSearch(item);
              }}
              className="px-3 py-1 rounded-full text-xs font-semibold bg-white border border-slate-200 text-slate-600 hover:text-orange-600 hover:border-orange-300 hover:bg-orange-50/70 shadow-2xs transition-all cursor-pointer"
            >
              {item}
            </button>
          ))}
        </div>

        {/* AI Detective Banner Callout */}
        <div className="flex items-center justify-between gap-3 px-3.5 py-2.5 mb-6 text-xs text-slate-600 bg-gradient-to-r from-orange-50 to-amber-50/50 border border-orange-200/80 rounded-xl shadow-2xs">
          <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded-lg bg-orange-500/10 flex items-center justify-center text-orange-600 shrink-0 font-bold">
              ✨
            </span>
            <span>
              Looking for relationship dynamic, inside jokes, or memory synthesis?
            </span>
          </div>
          <Link
            href={`/chat/${chatId}/qa`}
            className="inline-flex items-center gap-1 font-bold text-white bg-orange-600 hover:bg-orange-700 px-3 py-1.5 rounded-lg shadow-xs transition-colors shrink-0"
          >
            <Sparkles size={13} />
            <span>Ask AI Detective</span>
          </Link>
        </div>

        {/* Search Results */}
        {state.status === "results" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between px-1">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                {state.data.total === 0
                  ? "No matching messages found"
                  : `Found ${state.data.total.toLocaleString()} match${state.data.total !== 1 ? "es" : ""} for "${state.data.query}"`}
              </span>
              {state.data.total > 0 && (
                <span className="text-xs text-slate-400">
                  Showing top {state.data.results.length} ranked by relevance
                </span>
              )}
            </div>

            {state.data.total === 0 ? (
              <div className="p-10 rounded-2xl bg-white border border-slate-200 text-center shadow-xs">
                <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto text-slate-400 mb-3">
                  <Search size={22} />
                </div>
                <h3 className="font-bold text-slate-800 mb-1">No matches found</h3>
                <p className="text-slate-500 text-sm max-w-sm mx-auto mb-4">
                  Try searching for different keywords, partial words, or common conversation phrases.
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setQuery("");
                    setState({ status: "idle" });
                  }}
                  className="px-4 py-2 rounded-xl text-xs font-bold text-slate-700 bg-slate-100 hover:bg-slate-200 transition-colors"
                >
                  Clear Search
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {state.data.results.map((result, idx) => (
                  <motion.div
                    key={result.id || idx}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.25, delay: Math.min(idx * 0.03, 0.3) }}
                    className="p-4 rounded-2xl bg-white border border-slate-200/90 shadow-2xs hover:shadow-md hover:border-orange-200 transition-all group"
                  >
                    {/* Result Header */}
                    <div className="flex items-center justify-between gap-3 mb-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-orange-500 to-amber-500 flex items-center justify-center text-white text-xs font-bold shrink-0">
                          {result.sender_name.charAt(0).toUpperCase()}
                        </div>
                        <span className="font-bold text-sm text-slate-900 truncate">
                          {result.sender_name}
                        </span>
                      </div>

                      <div className="flex items-center gap-3 text-xs text-slate-400 shrink-0">
                        <span className="flex items-center gap-1">
                          <Clock size={12} />
                          <span>
                            {formatDate(result.timestamp)} · {formatTime(result.timestamp)}
                          </span>
                        </span>

                        <button
                          type="button"
                          onClick={() => handleCopy(result.id, result.content)}
                          className="p-1 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100 transition-colors"
                          title="Copy message content"
                        >
                          {copiedId === result.id ? (
                            <Check size={14} className="text-emerald-600" />
                          ) : (
                            <Copy size={14} />
                          )}
                        </button>
                      </div>
                    </div>

                    {/* Result Highlighted Content */}
                    <div
                      className="text-sm text-slate-800 leading-relaxed pl-9 [&>mark]:bg-amber-200/80 [&>mark]:text-amber-950 [&>mark]:px-1 [&>mark]:py-0.5 [&>mark]:rounded [&>mark]:font-semibold"
                      dangerouslySetInnerHTML={{ __html: result.highlight || result.content }}
                    />

                    {/* Footer link to jump into chat archive */}
                    <div className="mt-3 pl-9 pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
                      <span className="text-slate-400 font-mono text-[11px]">
                        Message #{result.id.slice(0, 8)}
                      </span>
                      <Link
                        href={`/chat/${chatId}`}
                        className="inline-flex items-center gap-1 font-semibold text-orange-600 hover:text-orange-700 hover:underline transition-colors"
                      >
                        <span>View in Messages Archive</span>
                        <ExternalLink size={12} />
                      </Link>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Error State */}
        {state.status === "error" && (
          <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-sm flex items-center gap-3">
            <span className="text-lg">⚠️</span>
            <div className="flex-1">
              <span className="font-bold">Search Error: </span>
              <span>{state.message}</span>
            </div>
            <button
              onClick={() => runSearch(query)}
              className="px-3 py-1 rounded-lg text-xs font-bold bg-white text-rose-700 border border-rose-300 hover:bg-rose-100 transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {/* Idle prompt */}
        {state.status === "idle" && (
          <div className="py-16 text-center text-slate-400 flex flex-col items-center justify-center">
            <div className="w-16 h-16 rounded-2xl bg-orange-50 text-orange-500 border border-orange-100 flex items-center justify-center mb-4 shadow-sm">
              <Search size={28} />
            </div>
            <h3 className="font-bold text-slate-700 text-base mb-1">
              Quickly Find Any Message
            </h3>
            <p className="text-sm text-slate-500 max-w-sm">
              Type any word, joke, date, or topic into the search bar above to instantly scan through the entire archive.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}

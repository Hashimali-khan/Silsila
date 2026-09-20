"use client";

import { useState, useRef, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";
import { AppNav } from "@/components/AppNav";
import Link from "next/link";
import {
  ArrowLeft,
  Sparkles,
  MessageSquare,
  Search,
  Copy,
  Check,
  RotateCcw,
  FileText,
  ChevronDown,
  ChevronUp,
  X,
  ExternalLink,
  ShieldCheck,
  Hash,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

type QAState =
  | { status: "idle" }
  | { status: "searching"; message?: string }
  | { status: "answering"; answer: string; evidence: any[] }
  | { status: "done"; answer: string; evidence: any[] }
  | { status: "error"; message: string };

const SUGGESTIONS = [
  { icon: "🎭", label: "Biggest inside joke", query: "What was our biggest inside joke?" },
  { icon: "✈️", label: "Plans & trips", query: "What plans or trips did we discuss?" },
  { icon: "⏳", label: "First conversation", query: "When did we first start chatting?" },
  { icon: "📊", label: "Chat balance & stats", query: "Who sends the most messages and what are they about?" },
  { icon: "💔", label: "First disagreement", query: "What was our first argument or disagreement about?" },
  { icon: "✨", label: "Relationship vibe", query: "How would you describe our relationship dynamic and overall vibe?" },
];

const SEARCH_PHASES = [
  "Scanning memory archives across conversations...",
  "Uncovering banter, timestamps & sentiment...",
  "Synthesizing relationship insights with verified citations...",
];

// Helper to parse and render Markdown + interactive citation badges
function FormattedAnswer({
  content,
  onCitationClick,
}: {
  content: string;
  onCitationClick: (citationId: string) => void;
}) {
  if (!content) return null;

  // Split lines to detect tables, blockquotes, headers, and bullet lists
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  let tableBuffer: string[] = [];

  const flushTable = (buffer: string[], keyPrefix: number) => {
    if (buffer.length < 2) return null;
    const headerRow = buffer[0].split("|").map((c) => c.trim()).filter(Boolean);
    const dataRows = buffer.slice(2).map((row) =>
      row.split("|").map((c) => c.trim()).filter(Boolean)
    );

    return (
      <div key={`table-${keyPrefix}`} className="my-4 overflow-x-auto rounded-xl border border-orange-200/70 shadow-sm bg-white/90">
        <table className="w-full text-left border-collapse text-xs md:text-sm">
          <thead>
            <tr className="bg-gradient-to-r from-orange-50 to-amber-50 border-b border-orange-200/80">
              {headerRow.map((h, i) => (
                <th key={i} className="py-2.5 px-3.5 font-bold text-slate-800 tracking-wide">
                  {renderInlineFormatting(h, onCitationClick)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {dataRows.map((row, rIdx) => (
              <tr key={rIdx} className={rIdx % 2 === 0 ? "bg-white hover:bg-orange-50/40" : "bg-slate-50/50 hover:bg-orange-50/40"}>
                {row.map((cell, cIdx) => (
                  <td key={cIdx} className="py-2.5 px-3.5 text-slate-700 leading-relaxed">
                    {renderInlineFormatting(cell, onCitationClick)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Table detection
    if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
      tableBuffer.push(line.trim());
      continue;
    } else if (tableBuffer.length > 0) {
      elements.push(flushTable(tableBuffer, i));
      tableBuffer = [];
    }

    const trimmed = line.trim();

    if (!trimmed) {
      elements.push(<div key={i} className="h-2.5" />);
      continue;
    }

    // Major headers
    if (trimmed.startsWith("### ")) {
      elements.push(
        <h4 key={i} className="text-base md:text-lg font-extrabold text-slate-900 mt-4 mb-2 flex items-center gap-2">
          <span className="w-1.5 h-4 rounded-full bg-gradient-to-b from-orange-500 to-amber-500 inline-block" />
          {renderInlineFormatting(trimmed.substring(4), onCitationClick)}
        </h4>
      );
      continue;
    }
    if (trimmed.startsWith("## ")) {
      elements.push(
        <h3 key={i} className="text-lg md:text-xl font-black text-slate-900 mt-5 mb-2.5 flex items-center gap-2">
          <span className="w-2 h-5 rounded-full bg-orange-600 inline-block" />
          {renderInlineFormatting(trimmed.substring(3), onCitationClick)}
        </h3>
      );
      continue;
    }

    // Bold title banner line e.g. **Biggest inside joke – “gen1 yehi dil”**
    if (trimmed.startsWith("**") && trimmed.endsWith("**") && !trimmed.slice(2, -2).includes("**")) {
      elements.push(
        <div
          key={i}
          className="my-3 p-3.5 rounded-xl bg-gradient-to-r from-orange-500/10 via-amber-500/10 to-transparent border-l-4 border-orange-500 font-bold text-slate-900 text-base md:text-lg shadow-sm"
        >
          {renderInlineFormatting(trimmed.slice(2, -2), onCitationClick)}
        </div>
      );
      continue;
    }

    // Blockquote
    if (trimmed.startsWith("> ")) {
      elements.push(
        <blockquote
          key={i}
          className="my-3 pl-4 py-2 border-l-4 border-orange-400 bg-orange-50/60 rounded-r-xl text-slate-800 italic text-sm md:text-base leading-relaxed"
        >
          {renderInlineFormatting(trimmed.substring(2), onCitationClick)}
        </blockquote>
      );
      continue;
    }

    // Bullet points
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      elements.push(
        <div key={i} className="flex items-start gap-2.5 my-1.5 text-slate-700 text-sm md:text-base leading-relaxed">
          <span className="text-orange-500 font-black mt-1 text-xs select-none">●</span>
          <div className="flex-1">{renderInlineFormatting(trimmed.substring(2), onCitationClick)}</div>
        </div>
      );
      continue;
    }

    // Regular paragraph
    elements.push(
      <p key={i} className="my-1.5 text-slate-700 text-sm md:text-base leading-relaxed">
        {renderInlineFormatting(trimmed, onCitationClick)}
      </p>
    );
  }

  if (tableBuffer.length > 0) {
    elements.push(flushTable(tableBuffer, lines.length));
  }

  return <div className="space-y-1">{elements}</div>;
}

// Inline parser for bold, code, and interactive [id: abc12345] citation badges
function renderInlineFormatting(text: string, onCitationClick: (id: string) => void): React.ReactNode[] {
  // Regex to match citation patterns like `([id: 12345])`, `[id: 12345]`, `[id: 12345, 67890]`
  const citationRegex = /(\(?\[id:\s*([a-f0-9,\s]+)\]\)?)/gi;

  const parts = text.split(citationRegex);
  const result: React.ReactNode[] = [];

  for (let idx = 0; idx < parts.length; idx++) {
    const part = parts[idx];
    if (!part) continue;

    // Check if part is full citation match
    if (part.startsWith("[id:") || part.startsWith("([id:") || (part.endsWith("]") && part.includes("id:"))) {
      const match = /id:\s*([a-f0-9,\s]+)/i.exec(part);
      if (match) {
        const ids = match[1].split(",").map((s) => s.trim()).filter(Boolean);
        result.push(
          <span key={`cite-${idx}`} className="inline-flex items-center gap-1 mx-1 align-baseline">
            {ids.map((singleId, idIndex) => (
              <button
                key={idIndex}
                type="button"
                onClick={() => onCitationClick(singleId)}
                title={`Click to view verified chat evidence for message [id: ${singleId}]`}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-orange-100/90 text-orange-800 border border-orange-300 hover:bg-orange-500 hover:text-white hover:border-orange-500 transition-all duration-200 shadow-sm cursor-pointer hover:scale-105 active:scale-95"
              >
                <Hash size={11} className="opacity-75" />
                <span>{singleId.slice(0, 8)}</span>
              </button>
            ))}
          </span>
        );
        continue;
      }
    }

    // Parse bold formatting (**bold**)
    const boldParts = part.split(/(\*\*.*?\*\*)/g);
    for (let bIdx = 0; bIdx < boldParts.length; bIdx++) {
      const bPart = boldParts[bIdx];
      if (bPart.startsWith("**") && bPart.endsWith("**")) {
        result.push(
          <strong key={`bold-${idx}-${bIdx}`} className="font-bold text-slate-900">
            {bPart.slice(2, -2)}
          </strong>
        );
      } else if (bPart) {
        result.push(bPart);
      }
    }
  }

  return result;
}

import { ChatHeader } from "../ChatHeader";

export function QAClient({
  chatId,
  chatName,
  participantCount,
  messageCount,
  initialQuery = "",
}: {
  chatId: string;
  chatName?: string;
  participantCount?: number;
  messageCount?: number;
  initialQuery?: string;
}) {
  const { getToken } = useAuth();

  const [query, setQuery] = useState(initialQuery);
  const [state, setState] = useState<QAState>({ status: "idle" });
  const [showEvidence, setShowEvidence] = useState(false);
  const [activeTab, setActiveTab] = useState<"answer" | "evidence">("answer");
  const [highlightedId, setHighlightedId] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [phaseIndex, setPhaseIndex] = useState(0);

  const endRef = useRef<HTMLDivElement>(null);
  const evidenceRef = useRef<HTMLDivElement>(null);
  const autoRanRef = useRef(false);

  // Rotate searching phases for delight
  useEffect(() => {
    if (state.status !== "searching") return;
    const timer = setInterval(() => {
      setPhaseIndex((prev) => (prev + 1) % SEARCH_PHASES.length);
    }, 2400);
    return () => clearInterval(timer);
  }, [state.status]);

  useEffect(() => {
    if (state.status === "answering" || state.status === "done") {
      endRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [state]);

  const runQA = async (q: string) => {
    if (!q.trim()) return;
    setState({ status: "searching", message: SEARCH_PHASES[0] });
    setShowEvidence(false);
    setActiveTab("answer");
    setHighlightedId(null);

    try {
      const token = await getToken();

      const response = await fetch(`${BACKEND_URL}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          query_text: q,
          chat_id: chatId,
        }),
      });

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({ detail: "Failed to query chat" }));
        throw new Error(errJson.detail || `Server error (${response.status})`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder("utf-8");

      if (!reader) {
        throw new Error("Stream not available");
      }

      let currentAnswer = "";
      let currentEvidence: any[] = [];
      let isAnswering = false;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const dataStr = line.substring(6).trim();
            if (!dataStr) continue;

            try {
              const data = JSON.parse(dataStr);
              if (data.type === "status") {
                if (!isAnswering) {
                  setState({ status: "searching", message: data.content });
                }
              } else if (data.type === "evidence") {
                currentEvidence = data.content;
              } else if (data.type === "token") {
                isAnswering = true;
                currentAnswer += data.content;
                setState({ status: "answering", answer: currentAnswer, evidence: currentEvidence });
              } else if (data.type === "error") {
                setState({ status: "error", message: data.content });
                return;
              } else if (data.type === "done") {
                setState({ status: "done", answer: currentAnswer, evidence: currentEvidence });
                return;
              }
            } catch (e) {
              console.error("Failed to parse SSE message:", dataStr, e);
            }
          }
        }
      }

      if (currentAnswer) {
        setState({ status: "done", answer: currentAnswer, evidence: currentEvidence });
      } else {
        setState({
          status: "error",
          message: "Response stream ended before an answer could be generated. Please try again.",
        });
      }
    } catch (e) {
      setState({ status: "error", message: e instanceof Error ? e.message : "QA failed" });
    }
  };

  useEffect(() => {
    if (initialQuery && !autoRanRef.current) {
      autoRanRef.current = true;
      runQA(initialQuery);
    }
  }, [initialQuery]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    runQA(query);
  };

  const handleCopy = async () => {
    if ("answer" in state && state.answer) {
      await navigator.clipboard.writeText(state.answer);
      setCopied(true);
      setTimeout(() => setCopied(false), 2200);
    }
  };

  const handleCitationClick = (citationId: string) => {
    setHighlightedId(citationId.toLowerCase());
    setShowEvidence(true);
    setActiveTab("evidence");
    setTimeout(() => {
      const el = document.getElementById(`evidence-msg-${citationId.toLowerCase()}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      } else {
        evidenceRef.current?.scrollIntoView({ behavior: "smooth" });
      }
    }, 150);
  };

  // Flatten messages for evidence tab
  const evidenceMessages: any[] = [];
  if ("evidence" in state && state.evidence) {
    for (const block of state.evidence) {
      if (Array.isArray(block.messages)) {
        evidenceMessages.push(...block.messages);
      }
    }
  }

  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
    // Focus without jumping or scrolling viewport down under sticky header
    inputRef.current?.focus({ preventScroll: true });
  }, []);

  return (
    <div className="pt-16 min-h-screen bg-[#fafaf9] text-slate-800 flex flex-col relative selection:bg-orange-500 selection:text-white">
      {/* Ambient background glows */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-[450px] pointer-events-none overflow-hidden -z-10 opacity-70">
        <div className="absolute -top-32 left-1/4 w-[500px] h-[500px] bg-gradient-to-br from-orange-400/20 to-amber-300/10 rounded-full blur-3xl" />
        <div className="absolute top-10 right-1/4 w-[450px] h-[450px] bg-gradient-to-bl from-amber-400/15 to-rose-400/10 rounded-full blur-3xl" />
      </div>

      <AppNav />

      {/* Unified Chat Header with Back Button, Breadcrumbs, & Tabs */}
      <ChatHeader
        chatId={chatId}
        chatName={chatName}
        participantCount={participantCount}
        messageCount={messageCount}
      />

      {/* Main Body */}
      <main className="max-w-4xl w-full mx-auto px-4 md:px-6 py-6 md:py-8 flex-1 flex flex-col">
        {/* Hero Title Section */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="flex items-start gap-4 mb-6"
        >
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-orange-600 to-amber-500 flex items-center justify-center text-white shadow-md shadow-orange-500/20 shrink-0">
            <Sparkles size={24} className="animate-pulse" />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="font-extrabold text-2xl md:text-3xl text-slate-900 tracking-tight font-display">
                AI Memory Detective
              </h1>
              <span className="px-2 py-0.5 rounded-md text-[11px] font-bold uppercase tracking-wider bg-orange-100 text-orange-800 border border-orange-200">
                RAG v2
              </span>
            </div>
            <p className="text-slate-500 text-xs md:text-sm mt-1 leading-relaxed">
              Ask natural questions about your chat. Powered by full conversational window retrieval, Roman Urdu nuance, and message citations.
            </p>
          </div>
        </motion.div>

        {/* Enhanced Search Input */}
        <motion.form
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.05 }}
          onSubmit={handleSubmit}
          className="relative mb-4 group"
        >
          <div className="relative flex items-center bg-white rounded-2xl border-2 border-slate-200 hover:border-orange-400 focus-within:border-orange-500 focus-within:ring-4 focus-within:ring-orange-500/15 shadow-sm transition-all duration-200 overflow-hidden">
            <span className="pl-4.5 pr-2 text-orange-500 text-lg select-none">
              ✨
            </span>

            <input
              ref={inputRef}
              id="qa-query-input"
              type="text"
              className="w-full py-4 px-2 text-slate-800 placeholder-slate-400 bg-transparent text-sm md:text-base outline-none font-medium"
              placeholder="E.g. What was our biggest inside joke? Or what plans did we discuss?"
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
              type="submit"
              disabled={!query.trim() || state.status === "searching" || state.status === "answering"}
              className="m-2 px-5 py-2.5 rounded-xl font-bold text-sm text-white bg-gradient-to-r from-orange-600 to-amber-500 hover:from-orange-500 hover:to-amber-500 disabled:opacity-50 disabled:cursor-not-allowed shadow-md shadow-orange-600/20 hover:shadow-orange-600/30 transition-all duration-200 flex items-center gap-1.5 shrink-0 cursor-pointer active:scale-95"
            >
              {state.status === "searching" ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Thinking...</span>
                </>
              ) : (
                <>
                  <span>Investigate</span>
                  <ArrowLeft size={14} className="rotate-180" />
                </>
              )}
            </button>
          </div>
        </motion.form>

        {/* Suggestion Chips */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.35, delay: 0.1 }}
          className="flex flex-wrap gap-2 mb-4"
        >
          {SUGGESTIONS.map((item, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => {
                setQuery(item.query);
                runQA(item.query);
              }}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold bg-white border border-slate-200 text-slate-600 hover:text-orange-700 hover:border-orange-300 hover:bg-orange-50/70 shadow-2xs hover:shadow-xs transition-all duration-200 cursor-pointer hover:-translate-y-0.5 active:translate-y-0"
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </motion.div>

        {/* Quick jump to Search Page */}
        <div className="flex items-center justify-between gap-3 px-1 mb-6 text-xs text-slate-500 bg-orange-50/50 border border-orange-100 rounded-xl py-2 px-3">
          <span className="flex items-center gap-1.5 font-medium">
            <Sparkles size={13} className="text-orange-600 shrink-0" />
            <span>Need to locate a specific word, person, or date in the raw text?</span>
          </span>
          <Link
            href={`/chat/${chatId}/search`}
            className="inline-flex items-center gap-1 font-bold text-orange-600 hover:text-orange-700 hover:underline transition-colors shrink-0 bg-white px-2.5 py-1 rounded-lg border border-orange-200/80 shadow-2xs"
          >
            <Search size={12} />
            <span>Open Search Page →</span>
          </Link>
        </div>

        {/* Searching Radar Scanner State */}
        <AnimatePresence>
          {state.status === "searching" && (
            <motion.div
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              className="my-6 p-8 md:p-10 rounded-2xl bg-white border border-orange-200 shadow-xl shadow-orange-500/5 text-center relative overflow-hidden"
            >
              <div className="absolute inset-0 bg-gradient-to-b from-orange-50/40 via-transparent to-transparent -z-10" />

              {/* Animated Radar Pulse */}
              <div className="relative w-20 h-20 mx-auto mb-5 flex items-center justify-center">
                <div className="absolute inset-0 rounded-full border-2 border-orange-400/40 animate-ping" />
                <div className="absolute -inset-3 rounded-full border border-orange-300/30 animate-pulse" />
                <div className="w-14 h-14 rounded-full bg-gradient-to-tr from-orange-500 to-amber-400 flex items-center justify-center text-white shadow-md shadow-orange-500/30 z-10">
                  <Sparkles size={24} className="animate-spin-slow" />
                </div>
              </div>

              <h3 className="font-bold text-slate-900 text-base md:text-lg mb-1">
                AI Detective is analyzing conversation memories
              </h3>
              <p className="text-orange-700 font-semibold text-xs md:text-sm animate-pulse min-h-[1.5rem]">
                {SEARCH_PHASES[phaseIndex]}
              </p>

              {/* Shimmer skeleton lines */}
              <div className="max-w-md mx-auto mt-6 space-y-2.5 opacity-60">
                <div className="h-2.5 bg-gradient-to-r from-orange-100 via-amber-200 to-orange-100 rounded-full animate-shimmer" />
                <div className="h-2.5 bg-gradient-to-r from-orange-100 via-amber-200 to-orange-100 rounded-full animate-shimmer w-5/6 mx-auto" />
                <div className="h-2.5 bg-gradient-to-r from-orange-100 via-amber-200 to-orange-100 rounded-full animate-shimmer w-4/6 mx-auto" />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Answer Card & Evidence Container */}
        <AnimatePresence>
          {(state.status === "answering" || state.status === "done") && (
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
              className="bg-white rounded-2xl border-2 border-orange-200/90 shadow-xl shadow-orange-500/10 mb-8 overflow-hidden"
            >
              {/* Card Header Bar */}
              <div className="px-5 md:px-7 py-4 bg-gradient-to-r from-orange-50/90 via-amber-50/50 to-white border-b border-orange-200/70 flex items-center justify-between flex-wrap gap-3">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-orange-600 text-white flex items-center justify-center shadow-xs">
                    <Sparkles size={16} />
                  </div>
                  <div>
                    <h2 className="font-extrabold text-slate-900 text-base md:text-lg leading-tight">
                      Synthesized Insight
                    </h2>
                    <p className="text-xs text-slate-500">
                      Cross-referenced across full chat history & timestamps
                    </p>
                  </div>
                </div>

                {/* Tabs / Actions */}
                <div className="flex items-center gap-2">
                  <div className="inline-flex p-1 bg-slate-100 rounded-xl border border-slate-200 text-xs font-semibold">
                    <button
                      type="button"
                      onClick={() => setActiveTab("answer")}
                      className={`px-3 py-1 rounded-lg transition-all cursor-pointer ${
                        activeTab === "answer"
                          ? "bg-white text-orange-700 shadow-xs"
                          : "text-slate-600 hover:text-slate-900"
                      }`}
                    >
                      Answer
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setActiveTab("evidence");
                        setShowEvidence(true);
                      }}
                      className={`px-3 py-1 rounded-lg transition-all cursor-pointer flex items-center gap-1 ${
                        activeTab === "evidence"
                          ? "bg-white text-orange-700 shadow-xs"
                          : "text-slate-600 hover:text-slate-900"
                      }`}
                    >
                      <span>Evidence</span>
                      {state.evidence && state.evidence.length > 0 && (
                        <span className="w-4 h-4 rounded-full bg-orange-100 text-orange-800 text-[10px] flex items-center justify-center font-bold">
                          {evidenceMessages.length || state.evidence.length}
                        </span>
                      )}
                    </button>
                  </div>

                  <button
                    type="button"
                    onClick={handleCopy}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 hover:text-slate-900 transition-colors shadow-2xs cursor-pointer"
                    title="Copy response to clipboard"
                  >
                    {copied ? (
                      <>
                        <Check size={14} className="text-emerald-600" />
                        <span className="text-emerald-700 font-bold">Copied!</span>
                      </>
                    ) : (
                      <>
                        <Copy size={14} />
                        <span>Copy</span>
                      </>
                    )}
                  </button>

                  <button
                    type="button"
                    onClick={() => runQA(query)}
                    className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors cursor-pointer"
                    title="Re-run analysis"
                  >
                    <RotateCcw size={15} />
                  </button>
                </div>
              </div>

              {/* Main Content Area */}
              <div className="p-5 md:p-7">
                {activeTab === "answer" ? (
                  <div className="prose prose-slate max-w-none">
                    <FormattedAnswer
                      content={state.answer}
                      onCitationClick={handleCitationClick}
                    />

                    {state.status === "answering" && (
                      <span className="inline-block w-2 h-4 ml-1 bg-orange-600 animate-pulse align-middle" />
                    )}
                  </div>
                ) : (
                  /* Evidence Inspector View */
                  <div ref={evidenceRef} className="space-y-4">
                    <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                      <div>
                        <h4 className="font-bold text-slate-900 text-sm flex items-center gap-1.5">
                          <FileText size={15} className="text-orange-600" />
                          <span>Verified Conversation Evidence</span>
                        </h4>
                        <p className="text-xs text-slate-500">
                          Click any citation in the answer to spotlight the exact chat bubble below.
                        </p>
                      </div>

                      {highlightedId && (
                        <button
                          type="button"
                          onClick={() => setHighlightedId(null)}
                          className="text-xs text-orange-600 hover:underline font-semibold"
                        >
                          Clear Highlight
                        </button>
                      )}
                    </div>

                    {/* Timeline message list */}
                    {evidenceMessages.length > 0 ? (
                      <div className="space-y-2.5 max-h-[500px] overflow-y-auto pr-1">
                        {evidenceMessages.map((msg: any, mIdx: number) => {
                          const mid = String(msg.id || "").toLowerCase();
                          const isHighlighted = highlightedId && (mid.includes(highlightedId) || highlightedId.includes(mid));

                          return (
                            <div
                              key={mIdx}
                              id={`evidence-msg-${mid.slice(0, 8)}`}
                              className={`p-3 rounded-xl border transition-all duration-300 ${
                                isHighlighted
                                  ? "bg-orange-50/90 border-orange-400 ring-2 ring-orange-400/40 shadow-md"
                                  : "bg-slate-50/70 border-slate-200/80 hover:bg-slate-100/70"
                              }`}
                            >
                              <div className="flex items-center justify-between mb-1.5 text-xs">
                                <div className="flex items-center gap-2">
                                  <span className="w-5 h-5 rounded-full bg-slate-300 text-slate-700 font-bold flex items-center justify-center text-[10px]">
                                    {(msg.sender_name || "U")[0].toUpperCase()}
                                  </span>
                                  <span className="font-bold text-slate-900">{msg.sender_name}</span>
                                </div>

                                <div className="flex items-center gap-2 text-slate-400">
                                  <span>{msg.timestamp ? new Date(msg.timestamp).toLocaleString([], { dateStyle: "short", timeStyle: "short" }) : ""}</span>
                                  <span className="font-mono text-[10px] px-1.5 py-0.5 rounded-md bg-white border border-slate-200 text-slate-500">
                                    id: {String(msg.id).slice(0, 8)}
                                  </span>
                                </div>
                              </div>

                              <div className="text-xs md:text-sm text-slate-800 whitespace-pre-wrap leading-relaxed pl-7">
                                {msg.content}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      /* Fallback block view */
                      <div className="space-y-3">
                        {state.evidence.map((block: any, idx: number) => (
                          <div key={idx} className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs md:text-sm font-mono whitespace-pre-wrap text-slate-800">
                            {block.content}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Evidence accordion toggle in Answer tab */}
                {activeTab === "answer" && state.evidence && state.evidence.length > 0 && (
                  <div className="mt-6 pt-4 border-t border-slate-100 flex items-center justify-between">
                    <button
                      type="button"
                      onClick={() => {
                        setActiveTab("evidence");
                        setShowEvidence(true);
                      }}
                      className="inline-flex items-center gap-1.5 text-xs md:text-sm font-bold text-orange-600 hover:text-orange-700 cursor-pointer group"
                    >
                      <span>Explore Raw Chat Evidence ({evidenceMessages.length || state.evidence.length} messages)</span>
                      <ArrowLeft size={14} className="rotate-180 transition-transform group-hover:translate-x-1" />
                    </button>

                    <span className="text-xs text-slate-400">
                      Tap any <span className="text-orange-600 font-bold font-mono">id:xxx</span> chip in the text
                    </span>
                  </div>
                )}
              </div>

              <div ref={endRef} />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Error Notification Card */}
        <AnimatePresence>
          {state.status === "error" && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-sm font-medium flex items-center gap-3 shadow-xs mb-6"
            >
              <span className="text-lg">⚠️</span>
              <div className="flex-1">{state.message}</div>
              <button
                type="button"
                onClick={() => runQA(query)}
                className="px-3 py-1 rounded-lg bg-white border border-rose-200 text-rose-700 text-xs font-bold hover:bg-rose-100 transition-colors cursor-pointer"
              >
                Retry
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      <style jsx global>{`
        @keyframes spin-slow {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        .animate-spin-slow {
          animation: spin-slow 12s linear infinite;
        }
        @keyframes shimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
        .animate-shimmer {
          background-size: 200% 100%;
          animation: shimmer 1.8s infinite;
        }
      `}</style>
    </div>
  );
}

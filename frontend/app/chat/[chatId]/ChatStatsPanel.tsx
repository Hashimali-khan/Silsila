"use client";

import type { ChatStats } from "@/lib/types";
import { formatNumber } from "@/lib/utils";
import Link from "next/link";
import { Sparkles, Search, ArrowRight, Calendar, Users, MessageSquare, Flame } from "lucide-react";
import { motion } from "framer-motion";

const SENDER_COLORS = [
  "#ea580c", "#0284c7", "#16a34a", "#9333ea", "#e11d48", "#ca8a04", "#0d9488",
];

const SUGGESTED_QUESTIONS = [
  { icon: "⏳", text: "When did we first meet or chat?" },
  { icon: "🎭", text: "What were the biggest inside jokes?" },
  { icon: "✈️", text: "Summarize key moments and plans" },
];

export function ChatStatsPanel({ stats, chatId }: { stats: ChatStats; chatId: string }) {
  const totalMsgs = stats.total_messages || 1;
  const participantCount = stats.participants?.length || stats.sender_breakdown?.length || 0;

  return (
    <div className="flex flex-col gap-4">
      {/* AI Features Callout Card with Animated Glow */}
      <div className="relative rounded-2xl bg-gradient-to-br from-orange-50 via-amber-50/50 to-white border-2 border-orange-300/80 p-5 shadow-lg shadow-orange-500/10 overflow-hidden">
        <div className="absolute top-0 right-0 w-32 h-32 bg-orange-400/10 rounded-full blur-2xl pointer-events-none" />

        <div className="flex items-center gap-2 mb-2">
          <div className="w-6 h-6 rounded-lg bg-orange-600 text-white flex items-center justify-center shadow-xs">
            <Sparkles size={14} className="animate-pulse" />
          </div>
          <h3 className="font-extrabold text-sm md:text-base text-orange-950 font-display m-0">
            Silsila AI Detective
          </h3>
        </div>

        <p className="text-xs text-slate-600 mb-3.5 leading-relaxed">
          Ask natural language questions about conversations, memories, promises, inside jokes, and dynamics.
        </p>

        <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
          <Link
            href={`/chat/${chatId}/qa`}
            className="flex items-center justify-center gap-2 w-full py-2.5 px-4 bg-gradient-to-r from-orange-600 to-amber-500 hover:from-orange-500 hover:to-amber-500 text-white font-bold text-xs md:text-sm rounded-xl shadow-md shadow-orange-600/25 transition-all mb-3.5 cursor-pointer"
          >
            <Sparkles size={15} />
            <span>Launch AI Detective</span>
          </Link>
        </motion.div>

        {/* Suggested Quick Questions with Physics Hover */}
        <div className="space-y-1.5">
          <span className="text-[10px] font-extrabold uppercase tracking-wider text-orange-900 block mb-1">
            Quick Prompts:
          </span>
          {SUGGESTED_QUESTIONS.map((q, idx) => (
            <motion.div
              key={idx}
              whileHover={{ x: 4, scale: 1.01 }}
              whileTap={{ scale: 0.98 }}
              transition={{ type: "spring", stiffness: 400, damping: 25 }}
            >
              <Link
                href={`/chat/${chatId}/qa?q=${encodeURIComponent(q.text)}`}
                className="text-xs text-orange-900 bg-white/90 hover:bg-orange-100/80 border border-orange-200/90 py-2 px-2.5 rounded-xl flex items-center justify-between gap-2 shadow-2xs hover:shadow-xs transition-colors group cursor-pointer"
              >
                <div className="flex items-center gap-1.5 truncate">
                  <span>{q.icon}</span>
                  <span className="truncate font-medium">{q.text}</span>
                </div>
                <ArrowRight size={12} className="text-orange-500 shrink-0 transition-transform group-hover:translate-x-0.5" />
              </Link>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Semantic Search Link Card */}
      <motion.div whileHover={{ y: -2 }} transition={{ type: "spring", stiffness: 400, damping: 25 }}>
        <Link
          href={`/chat/${chatId}/search`}
          className="flex items-center justify-between p-4 rounded-2xl bg-white border border-slate-200 shadow-xs hover:border-orange-300 hover:shadow-md transition-all group"
        >
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-orange-100 text-orange-600 flex items-center justify-center shrink-0">
              <Search size={18} />
            </div>
            <div>
              <div className="font-bold text-xs md:text-sm text-slate-900">Semantic Search</div>
              <div className="text-[11px] text-slate-500">
                Search across all messages & topics
              </div>
            </div>
          </div>
          <ArrowRight size={16} className="text-slate-400 group-hover:text-orange-600 group-hover:translate-x-1 transition-all" />
        </Link>
      </motion.div>

      {/* Overview stats card */}
      <div className="p-4.5 rounded-2xl bg-white border border-slate-200 shadow-xs">
        <h3 className="font-bold text-xs uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
          <MessageSquare size={13} />
          <span>Overview</span>
        </h3>
        <div className="grid grid-cols-2 gap-2.5">
          <StatBox label="Messages" value={formatNumber(stats.total_messages)} />
          <StatBox label="Threads" value={formatNumber(stats.thread_count || 414)} />
          <StatBox label="Participants" value={String(participantCount)} />
          <StatBox label="Archived" value="100%" />
        </div>
      </div>

      {/* Per-sender breakdown card */}
      <div className="p-4.5 rounded-2xl bg-white border border-slate-200 shadow-xs">
        <h3 className="font-bold text-xs uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
          <Users size={13} />
          <span>By Participant</span>
        </h3>
        <div className="space-y-3">
          {stats.sender_breakdown.map((s, i) => {
            const pct = Math.round((s.message_count / totalMsgs) * 100);
            const color = SENDER_COLORS[i % SENDER_COLORS.length];
            return (
              <div key={s.sender_name} className="group">
                <div className="flex justify-between items-center mb-1 text-xs">
                  <span className="font-semibold text-slate-700 truncate max-w-[65%] group-hover:text-orange-600 transition-colors">
                    {s.sender_name}
                  </span>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <span className="text-slate-400 text-[11px]">{s.message_count.toLocaleString()}</span>
                    <span className="font-bold text-slate-800 text-[11px]">{pct}%</span>
                  </div>
                </div>
                <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${pct}%` }}
                    transition={{ duration: 0.8, ease: "easeOut" }}
                    className="h-full rounded-full"
                    style={{ background: color }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Date range */}
      {stats.date_range?.start && (
        <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 text-xs text-slate-500 flex items-center gap-2">
          <Calendar size={14} className="text-orange-500 shrink-0" />
          <span>
            {new Date(stats.date_range.start).toLocaleDateString()} →{" "}
            {new Date(stats.date_range.end).toLocaleDateString()}
          </span>
        </div>
      )}
    </div>
  );
}

function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-slate-50 border border-slate-100 rounded-xl p-3">
      <div className="text-[10px] text-slate-400 uppercase tracking-wider font-bold mb-0.5">
        {label}
      </div>
      <div className="font-black text-base md:text-lg text-slate-900 font-display">
        {value}
      </div>
    </div>
  );
}

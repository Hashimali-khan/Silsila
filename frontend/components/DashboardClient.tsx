"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { useAuth } from "@clerk/nextjs";
import { motion, AnimatePresence } from "framer-motion";
import {
  MessageSquare,
  Users,
  Calendar,
  ArrowRight,
  Trash2,
  Search,
  CloudUpload,
  X,
  AlertTriangle,
  Clock,
  SlidersHorizontal,
  FolderOpen,
  CheckCircle2,
} from "lucide-react";
import type { Chat } from "@/lib/types";
import { formatDateShort, formatNumber } from "@/lib/utils";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

const CARD_THEMES = [
  {
    gradient: "",
    accent: "#ea580c",
    badgeBg: "bg-orange-50 text-orange-800 border-orange-200",
    avatarBg: "bg-orange-600 text-white",
  },
  {
    gradient: "",
    accent: "#0284c7",
    badgeBg: "bg-sky-50 text-sky-800 border-sky-200",
    avatarBg: "bg-sky-600 text-white",
  },
  {
    gradient: "",
    accent: "#059669",
    badgeBg: "bg-emerald-50 text-emerald-800 border-emerald-200",
    avatarBg: "bg-emerald-600 text-white",
  },
  {
    gradient: "",
    accent: "#7c3aed",
    badgeBg: "bg-purple-50 text-purple-800 border-purple-200",
    avatarBg: "bg-purple-600 text-white",
  },
  {
    gradient: "",
    accent: "#e11d48",
    badgeBg: "bg-rose-50 text-rose-800 border-rose-200",
    avatarBg: "bg-rose-600 text-white",
  },
  {
    gradient: "",
    accent: "#d97706",
    badgeBg: "bg-amber-50 text-amber-900 border-amber-200",
    avatarBg: "bg-amber-600 text-white",
  },
];

interface DashboardClientProps {
  initialChats: Chat[];
}

export function DashboardClient({ initialChats }: DashboardClientProps) {
  const { getToken } = useAuth();
  const [chats, setChats] = useState<Chat[]>(initialChats);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState<"recent" | "messages" | "name">("recent");

  // Delete modal state
  const [chatToDelete, setChatToDelete] = useState<Chat | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Stats calculations
  const totalMessages = useMemo(
    () => chats.reduce((acc, c) => acc + (c.message_count || 0), 0),
    [chats]
  );
  const totalParticipants = useMemo(
    () => chats.reduce((acc, c) => acc + (c.participant_count || 0), 0),
    [chats]
  );

  // Filter and sort chats
  const filteredChats = useMemo(() => {
    let result = chats.filter((chat) =>
      chat.name.toLowerCase().includes(searchQuery.toLowerCase().trim())
    );

    result.sort((a, b) => {
      if (sortBy === "messages") {
        return (b.message_count || 0) - (a.message_count || 0);
      }
      if (sortBy === "name") {
        return a.name.localeCompare(b.name);
      }
      // default "recent"
      const dateA = a.last_message_at ? new Date(a.last_message_at).getTime() : 0;
      const dateB = b.last_message_at ? new Date(b.last_message_at).getTime() : 0;
      return dateB - dateA;
    });

    return result;
  }, [chats, searchQuery, sortBy]);

  // Handle Chat Deletion
  const handleDeleteChat = async () => {
    if (!chatToDelete) return;
    setIsDeleting(true);
    setDeleteError(null);

    try {
      const token = await getToken();
      const res = await fetch(`${BACKEND_URL}/api/chats/${chatToDelete.id}`, {
        method: "DELETE",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: "Failed to delete chat" }));
        throw new Error(data.detail || "Failed to delete chat");
      }

      // Optimistic update
      const deletedName = chatToDelete.name;
      setChats((prev) => prev.filter((c) => c.id !== chatToDelete.id));
      setChatToDelete(null);
      setToastMessage(`"${deletedName}" has been permanently deleted.`);
      setTimeout(() => setToastMessage(null), 4000);
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Error deleting chat");
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10" id="chats">
      {/* Toast Notification */}
      <AnimatePresence>
        {toastMessage && (
          <motion.div
            initial={{ opacity: 0, y: -20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -20, scale: 0.95 }}
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
            className="fixed top-20 right-6 z-50 flex items-center gap-2.5 px-4 py-3 rounded-2xl bg-slate-900 text-white text-sm font-semibold shadow-2xl border border-slate-800"
          >
            <CheckCircle2 size={18} className="text-emerald-400 shrink-0" />
            <span>{toastMessage}</span>
            <button
              onClick={() => setToastMessage(null)}
              className="ml-2 text-slate-400 hover:text-white"
            >
              <X size={15} />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Hero Header & Quick Actions */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-8">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold text-orange-700 bg-orange-100/80 border border-orange-200/80 mb-2">
            <span className="w-2 h-2 rounded-full bg-orange-500" />
            <span>Interactive Archive Engine</span>
          </div>

          <h1 className="font-display font-extrabold text-3xl sm:text-5xl text-slate-900 tracking-tight">
            Your Conversations
          </h1>
          <p className="text-base sm:text-lg text-slate-500 mt-2 max-w-2xl font-medium">
            Search, ask questions with AI memory, and relive relationship milestones across your chats.
          </p>
        </div>

        {/* Upload Button */}
        <Link
          href="/upload"
          className="group inline-flex items-center gap-2.5 px-6 py-3.5 rounded-2xl font-display font-bold text-sm text-white bg-gradient-to-r from-orange-600 via-orange-500 to-amber-500 hover:from-orange-500 hover:to-amber-500 shadow-lg shadow-orange-500/25 hover:shadow-orange-500/35 transition-all transform hover:-translate-y-0.5 active:translate-y-0 cursor-pointer self-start md:self-auto"
        >
          <CloudUpload size={20} className="group-hover:scale-110 transition-transform" />
          <span>Upload New Chat</span>
        </Link>
      </div>

      {/* Stats Counter Strip (When user has chats) */}
      {chats.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 mb-8">
          <motion.div
            whileHover={{ y: -2 }}
            className="p-4 rounded-2xl bg-white border border-slate-200/90 shadow-2xs flex flex-col justify-between"
          >
            <div className="flex items-center justify-between text-slate-400 text-xs font-bold uppercase tracking-wider mb-2">
              <span>Chats</span>
              <MessageSquare size={16} className="text-orange-500" />
            </div>
            <div className="text-2xl sm:text-3xl font-black text-slate-900 font-display">
              {chats.length}
            </div>
            <div className="text-[11px] text-slate-500 mt-1 font-medium">Active Archives</div>
          </motion.div>

          <motion.div
            whileHover={{ y: -2 }}
            className="p-4 rounded-2xl bg-white border border-slate-200/90 shadow-2xs flex flex-col justify-between"
          >
            <div className="flex items-center justify-between text-slate-400 text-xs font-bold uppercase tracking-wider mb-2">
              <span>Messages</span>
              <Clock size={16} className="text-blue-500" />
            </div>
            <div className="text-2xl sm:text-3xl font-black text-slate-900 font-display">
              {formatNumber(totalMessages)}
            </div>
            <div className="text-[11px] text-slate-500 mt-1 font-medium">Indexed & Searchable</div>
          </motion.div>

          <motion.div
            whileHover={{ y: -2 }}
            className="p-4 rounded-2xl bg-white border border-slate-200/90 shadow-2xs flex flex-col justify-between"
          >
            <div className="flex items-center justify-between text-slate-400 text-xs font-bold uppercase tracking-wider mb-2">
              <span>People</span>
              <Users size={16} className="text-emerald-500" />
            </div>
            <div className="text-2xl sm:text-3xl font-black text-slate-900 font-display">
              {totalParticipants}
            </div>
            <div className="text-[11px] text-slate-500 mt-1 font-medium">Participants Identified</div>
          </motion.div>

          <motion.div
            whileHover={{ y: -2 }}
            className="p-4 rounded-2xl bg-white border border-slate-200/90 shadow-2xs flex flex-col justify-between"
          >
            <div className="flex items-center justify-between text-slate-400 text-xs font-bold uppercase tracking-wider mb-2">
              <span>Protection</span>
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
            </div>
            <div className="text-2xl sm:text-3xl font-black text-emerald-600 font-display">
              100%
            </div>
            <div className="text-[11px] text-slate-500 mt-1 font-medium">Encrypted & Private</div>
          </motion.div>
        </div>
      )}

      {/* Search & Sort Controls Toolbar (When user has chats) */}
      {chats.length > 0 && (
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 mb-6 p-2 rounded-2xl bg-slate-100/80 border border-slate-200/70">
          {/* Live Search Filter */}
          <div className="relative flex-1 max-w-md">
            <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter chats by name or person..."
              className="w-full pl-10 pr-8 py-2 text-xs sm:text-sm bg-white rounded-xl border border-slate-200/80 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500 transition-all font-medium"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-0.5"
                title="Clear filter"
              >
                <X size={14} />
              </button>
            )}
          </div>

          {/* Sort Filter Buttons */}
          <div className="flex items-center gap-1.5 self-end sm:self-auto overflow-x-auto">
            <span className="text-xs text-slate-400 font-bold uppercase tracking-wider flex items-center gap-1 px-1 mr-1">
              <SlidersHorizontal size={13} />
              <span className="hidden md:inline">Sort:</span>
            </span>

            <button
              type="button"
              onClick={() => setSortBy("recent")}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                sortBy === "recent"
                  ? "bg-slate-900 text-white shadow-2xs border border-slate-900"
                  : "text-slate-500 hover:text-slate-900 hover:bg-white/60"
              }`}
            >
              Recent
            </button>

            <button
              type="button"
              onClick={() => setSortBy("messages")}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                sortBy === "messages"
                  ? "bg-slate-900 text-white shadow-2xs border border-slate-900"
                  : "text-slate-500 hover:text-slate-900 hover:bg-white/60"
              }`}
            >
              Most Messages
            </button>

            <button
              type="button"
              onClick={() => setSortBy("name")}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                sortBy === "name"
                  ? "bg-slate-900 text-white shadow-2xs border border-slate-900"
                  : "text-slate-500 hover:text-slate-900 hover:bg-white/60"
              }`}
            >
              A–Z
            </button>
          </div>
        </div>
      )}

      {/* Main Grid or Empty States */}
      {chats.length === 0 ? (
        /* Empty State (No uploads yet) */
        <div className="max-w-2xl mx-auto w-full py-16 text-center">
          <div className="w-20 h-20 rounded-3xl bg-orange-100 text-orange-600 flex items-center justify-center mx-auto mb-6 shadow-md border border-orange-200">
            <FolderOpen size={36} />
          </div>
          <h3 className="font-display font-extrabold text-2xl sm:text-3xl text-slate-900 mb-2">
            No chats uploaded yet
          </h3>
          <p className="text-slate-500 text-sm sm:text-base max-w-md mx-auto mb-8">
            Upload your WhatsApp chat export (.zip or .txt) to turn your messages into searchable, AI-analyzed memories.
          </p>
          <Link
            href="/upload"
            className="inline-flex items-center gap-2 px-6 py-3.5 rounded-2xl font-display font-bold text-sm text-white bg-gradient-to-r from-orange-600 to-amber-500 hover:from-orange-500 hover:to-amber-500 shadow-lg shadow-orange-500/25 hover:scale-105 active:scale-95 transition-all"
          >
            <CloudUpload size={18} />
            <span>Upload Your First Chat</span>
          </Link>
        </div>
      ) : filteredChats.length === 0 ? (
        /* Search Query Has No Matches */
        <div className="py-16 text-center">
          <div className="w-14 h-14 rounded-2xl bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-3">
            <Search size={24} />
          </div>
          <h3 className="font-bold text-slate-800 text-base mb-1">
            No conversations matching &ldquo;{searchQuery}&rdquo;
          </h3>
          <p className="text-slate-400 text-xs mb-4">
            Check your spelling or clear the search filter to see all conversations.
          </p>
          <button
            type="button"
            onClick={() => setSearchQuery("")}
            className="px-4 py-2 rounded-xl text-xs font-bold text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 shadow-2xs transition-colors cursor-pointer"
          >
            Clear Filter
          </button>
        </div>
      ) : (
        /* Animated Cards Grid */
        <motion.div layout className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <AnimatePresence mode="popLayout">
            {filteredChats.map((chat, i) => {
              const theme = CARD_THEMES[i % CARD_THEMES.length];
              const initials = chat.name
                .split(/\s+/)
                .slice(0, 2)
                .map((w) => w[0])
                .join("")
                .toUpperCase() || "WC";

              const isGroup = (chat.participant_count || 0) > 2;

              return (
                <motion.div
                  layout
                  key={chat.id}
                  initial={{ opacity: 0, y: 20, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9, transition: { duration: 0.2 } }}
                  transition={{ duration: 0.35, delay: Math.min(i * 0.05, 0.3) }}
                  whileHover={{ y: -6 }}
                  className="group relative flex flex-col bg-white rounded-3xl border border-slate-200/90 shadow-2xs hover:shadow-xl hover:border-slate-300 transition-all duration-300 overflow-hidden"
                >
                  {/* Top Ambient Accent Gradient Removed */}

                  {/* Card Header Row */}
                  <div className="p-6 pb-4 relative z-10 flex-1 flex flex-col">
                    <div className="flex items-start justify-between gap-3 mb-4">
                      {/* Avatar with Initials */}
                      <div className="flex items-center gap-3 min-w-0">
                        <div
                          className={`w-12 h-12 rounded-2xl ${theme.avatarBg} flex items-center justify-center font-display font-extrabold text-base shrink-0 shadow-md group-hover:rotate-3 group-hover:scale-105 transition-all duration-300`}
                        >
                          {initials}
                        </div>

                        <div className="min-w-0">
                          <Link
                            href={`/chat/${chat.id}`}
                            className="font-display font-extrabold text-base md:text-lg text-slate-900 group-hover:text-orange-600 transition-colors line-clamp-1 block"
                            title={chat.name}
                          >
                            {chat.name}
                          </Link>

                          <div className="flex items-center gap-2 mt-1">
                            <span
                              className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] font-bold border ${theme.badgeBg}`}
                            >
                              <Users size={11} />
                              <span>
                                {chat.participant_count} {chat.participant_count === 1 ? "participant" : "participants"}
                              </span>
                            </span>

                            <span className="text-[11px] font-semibold text-slate-400">
                              {isGroup ? "Group" : "Direct"}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Delete Quick Action Button */}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          setChatToDelete(chat);
                        }}
                        className="p-2 rounded-xl text-slate-400 hover:text-rose-600 hover:bg-rose-50 border border-transparent hover:border-rose-200 transition-all cursor-pointer opacity-70 group-hover:opacity-100"
                        title="Delete this conversation"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>

                    {/* Stats Strip */}
                    <div className="grid grid-cols-2 gap-2 p-3 my-2 border-t border-b border-slate-100">
                      <div className="px-2 py-1">
                        <div className="text-xs uppercase tracking-wider font-bold text-slate-500 mb-1">
                          Messages
                        </div>
                        <div className="text-base font-extrabold text-slate-900 font-display">
                          {formatNumber(chat.message_count)}
                        </div>
                      </div>

                      <div className="px-2 py-1 border-l border-slate-200/70">
                        <div className="text-xs uppercase tracking-wider font-bold text-slate-500 mb-1">
                          Started
                        </div>
                        <div className="text-xs sm:text-sm font-bold text-slate-700 truncate">
                          {formatDateShort(chat.first_message_at) || "N/A"}
                        </div>
                      </div>
                    </div>

                    {/* Interactive Sub-Links */}
                    <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between gap-1 text-xs">
                      <div className="flex items-center gap-1.5">
                        <Link
                          href={`/chat/${chat.id}/search`}
                          className="px-2.5 py-1 rounded-lg text-slate-600 hover:text-orange-600 hover:bg-orange-50 font-semibold transition-colors flex items-center gap-1"
                        >
                          <Search size={12} />
                          <span>Search</span>
                        </Link>

                        <Link
                          href={`/chat/${chat.id}/qa`}
                          className="px-2.5 py-1 rounded-lg text-slate-600 hover:text-orange-600 hover:bg-orange-50 font-semibold transition-colors flex items-center gap-1"
                        >
                          <span>Detective</span>
                        </Link>
                      </div>

                      <div className="text-xs font-medium text-slate-600">
                        {chat.last_message_at ? formatDateShort(chat.last_message_at) : ""}
                      </div>
                    </div>
                  </div>

                  {/* Primary Enter Link Banner */}
                  <Link
                    href={`/chat/${chat.id}`}
                    className="px-6 py-3.5 bg-slate-50/90 group-hover:bg-slate-900 border-t border-slate-200 group-hover:border-transparent flex items-center justify-between text-xs font-bold text-slate-700 group-hover:text-white transition-all duration-300"
                  >
                    <span>Explore Messages & Archive</span>
                    <ArrowRight
                      size={15}
                      className="transform group-hover:translate-x-1.5 transition-transform duration-300"
                    />
                  </Link>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </motion.div>
      )}

      {/* Delete Confirmation Modal */}
      <AnimatePresence>
        {chatToDelete && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => {
                if (!isDeleting) {
                  setChatToDelete(null);
                  setDeleteError(null);
                }
              }}
              className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm"
            />

            {/* Modal Dialog Card */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ type: "spring", stiffness: 450, damping: 30 }}
              className="relative w-full max-w-md bg-white rounded-3xl shadow-2xl border border-slate-200 p-6 z-10 overflow-hidden"
            >
              {/* Modal Header */}
              <div className="flex items-start gap-4 mb-4">
                <div className="w-12 h-12 rounded-2xl bg-rose-100 text-rose-600 flex items-center justify-center shrink-0">
                  <AlertTriangle size={24} />
                </div>
                <div>
                  <h3 className="font-display font-extrabold text-lg text-slate-900">
                    Delete Conversation?
                  </h3>
                  <p className="text-xs text-slate-500 mt-1">
                    This action is permanent and cannot be undone.
                  </p>
                </div>
              </div>

              {/* Chat to delete detail */}
              <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/80 mb-4">
                <div className="font-bold text-sm text-slate-900 truncate">
                  {chatToDelete.name}
                </div>
                <div className="text-xs text-slate-500 mt-0.5">
                  {chatToDelete.participant_count} participants · {chatToDelete.message_count?.toLocaleString()} messages
                </div>
              </div>

              <p className="text-xs text-slate-600 leading-relaxed mb-6">
                All parsed messages, threads, character memory indexes, and timeline events for this conversation will be permanently erased from your database.
              </p>

              {deleteError && (
                <div className="mb-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-semibold flex items-center gap-2">
                  <span>⚠️</span>
                  <span>{deleteError}</span>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-3">
                <button
                  type="button"
                  disabled={isDeleting}
                  onClick={() => {
                    setChatToDelete(null);
                    setDeleteError(null);
                  }}
                  className="px-4 py-2.5 rounded-xl text-xs font-bold text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors cursor-pointer"
                >
                  Cancel
                </button>

                <button
                  type="button"
                  disabled={isDeleting}
                  onClick={handleDeleteChat}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 active:scale-95 shadow-md shadow-rose-600/20 transition-all cursor-pointer disabled:opacity-50"
                >
                  {isDeleting ? (
                    <>
                      <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Deleting…</span>
                    </>
                  ) : (
                    <>
                      <Trash2 size={14} />
                      <span>Yes, Delete Chat</span>
                    </>
                  )}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </section>
  );
}

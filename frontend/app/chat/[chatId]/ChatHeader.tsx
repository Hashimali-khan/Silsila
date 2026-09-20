"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { MessageSquare, Sparkles, Search, ArrowLeft, Home, ChevronRight } from "lucide-react";
import { motion } from "framer-motion";

interface ChatHeaderProps {
  chatId: string;
  chatName?: string;
  participantCount?: number;
  messageCount?: number;
}

export function ChatHeader({
  chatId,
  chatName,
  participantCount,
  messageCount,
}: ChatHeaderProps) {
  const pathname = usePathname();
  const router = useRouter();

  const isMessages = pathname === `/chat/${chatId}`;
  const isQA = pathname === `/chat/${chatId}/qa`;
  const isSearch = pathname === `/chat/${chatId}/search`;

  const handleGoBack = () => {
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back();
    } else {
      router.push(isMessages ? "/" : `/chat/${chatId}`);
    }
  };

  const tabs = [
    {
      id: "messages",
      label: "Messages Archive",
      href: `/chat/${chatId}`,
      icon: MessageSquare,
      active: isMessages,
    },
    {
      id: "qa",
      label: "AI Detective (Q&A)",
      href: `/chat/${chatId}/qa`,
      icon: Sparkles,
      active: isQA,
    },
    {
      id: "search",
      label: "Semantic Search",
      href: `/chat/${chatId}/search`,
      icon: Search,
      active: isSearch,
    },
  ];

  return (
    <div className="bg-white border-b border-slate-200 sticky top-16 z-30 shadow-xs">
      {/* Top bar with back, breadcrumbs, title and quick actions */}
      <div className="px-4 md:px-6 py-2.5 flex items-center justify-between gap-4 max-w-7xl mx-auto">
        <div className="flex items-center gap-2.5 min-w-0">
          {/* Back button */}
          <button
            type="button"
            onClick={handleGoBack}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs md:text-sm font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 hover:text-slate-900 border border-slate-200/80 transition-all cursor-pointer active:scale-95 shadow-xs shrink-0"
            title="Go back to previous page"
          >
            <ArrowLeft size={15} />
            <span className="font-bold">Back</span>
          </button>

          {/* Breadcrumbs & Chat name */}
          <div className="flex items-center gap-1.5 min-w-0 text-xs">
            <Link
              href="/"
              className="hidden sm:inline-flex items-center gap-1 px-2 py-1 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors shrink-0 font-medium"
              title="Return to Dashboard"
            >
              <Home size={13} />
              <span>Dashboard</span>
            </Link>

            <ChevronRight size={13} className="hidden sm:inline text-slate-300 shrink-0" />

            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="font-extrabold text-sm md:text-base text-slate-900 tracking-tight truncate max-w-[160px] sm:max-w-xs md:max-w-md">
                  {chatName || "Conversation"}
                </h1>
                <span className="hidden md:inline-flex px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider bg-orange-100/80 text-orange-800 shrink-0">
                  {isQA ? "AI Detective" : isSearch ? "Search" : "Archive"}
                </span>
              </div>
              {(participantCount !== undefined || messageCount !== undefined) && (
                <p className="text-[11px] text-slate-500 font-medium truncate">
                  {participantCount !== undefined ? `${participantCount} participants` : ""}
                  {participantCount !== undefined && messageCount !== undefined ? " · " : ""}
                  {messageCount !== undefined ? `${messageCount.toLocaleString()} messages` : ""}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Quick action pill buttons on the right */}
        <div className="flex items-center gap-2 shrink-0">
          {/* Messages link if not already on messages */}
          {!isMessages && (
            <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}>
              <Link
                href={`/chat/${chatId}`}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-semibold text-xs md:text-sm text-slate-700 bg-slate-100 hover:bg-slate-200 border border-slate-200/80 transition-colors"
                title="Open chat message archive"
              >
                <MessageSquare size={14} className="text-slate-500" />
                <span className="hidden sm:inline">Messages</span>
              </Link>
            </motion.div>
          )}

          {/* Search link if not already on search */}
          {!isSearch && (
            <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}>
              <Link
                href={`/chat/${chatId}/search`}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-semibold text-xs md:text-sm text-slate-700 bg-slate-100 hover:bg-slate-200 border border-slate-200/80 transition-colors"
                title="Search conversation messages"
              >
                <Search size={14} className="text-slate-500" />
                <span>Search</span>
              </Link>
            </motion.div>
          )}

          {/* AI Detective link if not already on QA */}
          {!isQA && (
            <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
              <Link
                href={`/chat/${chatId}/qa`}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl font-bold text-xs md:text-sm text-white bg-gradient-to-r from-orange-600 to-amber-500 hover:from-orange-500 hover:to-amber-500 shadow-md shadow-orange-500/20 transition-all cursor-pointer"
                title="Ask AI Memory Detective"
              >
                <Sparkles size={14} className="animate-pulse" />
                <span className="hidden xs:inline">Ask AI Detective</span>
              </Link>
            </motion.div>
          )}
        </div>
      </div>

      {/* Navigation tabs with Sliding Spring Physics indicator */}
      <div className="px-4 md:px-6 flex gap-1 max-w-7xl mx-auto border-t border-slate-100 overflow-x-auto no-scrollbar">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <Link
              key={tab.id}
              href={tab.href}
              className={`relative inline-flex items-center gap-2 px-4 py-2.5 text-xs md:text-sm font-bold transition-colors cursor-pointer select-none ${
                tab.active ? "text-orange-600" : "text-slate-500 hover:text-slate-900"
              }`}
            >
              <Icon size={16} />
              <span>{tab.label}</span>

              {/* Sliding spring underline pill */}
              {tab.active && (
                <motion.div
                  layoutId="activeHeaderTab"
                  transition={{ type: "spring", stiffness: 450, damping: 30 }}
                  className="absolute bottom-0 left-0 right-0 h-0.75 bg-gradient-to-r from-orange-600 to-amber-500 rounded-t-full shadow-xs"
                />
              )}
            </Link>
          );
        })}
      </div>
    </div>
  );
}

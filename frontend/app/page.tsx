import { auth } from "@clerk/nextjs/server";
import { api } from "@/lib/api";
import type { Chat } from "@/lib/types";
import { formatDateShort, formatNumber } from "@/lib/utils";
import { AppNav } from "@/components/AppNav";
import { PhysicsHero } from "@/components/PhysicsHero";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Dashboard — Silsila",
  description: "Your uploaded chats and conversation history.",
};

const CARD_ACCENTS = [
  "#ea580c", "#0284c7", "#16a34a", "#9333ea", "#e11d48", "#ca8a04", "#0d9488",
];

export default async function DashboardPage() {
  const { userId } = await auth();

  if (!userId) {
    return (
      <>
        <AppNav />
        <main className="pt-16 overflow-hidden min-h-screen flex flex-col">
          <div className="flex-1 relative">
            <PhysicsHero />
          </div>
          <PremiumFooter />
        </main>
      </>
    );
  }

  let chats: Chat[] = [];
  let error: string | null = null;

  try {
    chats = await api.get<Chat[]>("/chats");
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load chats";
  }

  return (
    <>
      <AppNav />
      <main className="pt-16 overflow-hidden min-h-screen">
        {/* Chats Section */}
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12" id="chats">
          
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8">
            <div>
              <h2 className="font-display font-extrabold text-3xl sm:text-5xl text-on-surface mt-3 tracking-tight">
                {chats.length === 0 ? "Unlock Your Memories" : "Your Conversations"}
              </h2>
              <p className="font-body text-base sm:text-lg text-on-surface-variant mt-2 max-w-2xl">
                {chats.length === 0 
                  ? "Turn your endless WhatsApp group banter and late-night heart-to-hearts into a living, searchable archive."
                  : `${chats.length} chat${chats.length !== 1 ? "s" : ""} uploaded and processed. Click a card to explore.`}
              </p>
            </div>
            {chats.length > 0 && (
              <Link
                href="/upload"
                className="bg-primary hover:bg-primary-hover text-white font-display font-bold text-sm px-6 py-3 rounded-full shadow-btn-primary hover:scale-105 active:scale-95 transition-all flex items-center gap-2 self-start md:self-auto"
              >
                <span className="material-symbols-outlined text-[20px]">cloud_upload</span>
                <span>Upload New Chat</span>
              </Link>
            )}
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-2xl p-4 text-red-700 mb-8 text-sm font-medium flex items-center gap-2 shadow-warm-sm">
              <span className="material-symbols-outlined">error</span>
              {error}
            </div>
          )}

          {chats.length === 0 && !error ? (
            <div className="max-w-4xl mx-auto w-full mt-12">
              <Link href="/upload" className="block outline-none group" id="dropzone-area">
                {/* Premium Glassmorphic Portal Upload Card */}
                <div className="relative glass-panel animated-gradient-border rounded-3xl p-1 sm:p-2 shadow-warm-lg hover:shadow-warm-xl hover-lift">
                  <div className="bg-white/80 backdrop-blur-3xl rounded-[1.35rem] p-8 sm:p-14 text-center flex flex-col items-center justify-center overflow-hidden relative">
                    
                    {/* Floating background decorative elements */}
                    <div className="absolute top-10 left-10 text-orange-200/50 animate-float" style={{ animationDelay: '0s' }}>
                      <span className="material-symbols-outlined text-[60px] rotate-[-15deg]">forum</span>
                    </div>
                    <div className="absolute bottom-10 right-10 text-emerald-200/40 animate-float" style={{ animationDelay: '2s' }}>
                      <span className="material-symbols-outlined text-[80px] rotate-[10deg]">auto_awesome</span>
                    </div>
                    
                    <div className="relative mb-8 z-10">
                      {/* Pulsing Core */}
                      <div className="absolute inset-0 rounded-full animate-pulse-ring"></div>
                      <div className="w-24 h-24 sm:w-28 sm:h-28 rounded-full bg-gradient-to-br from-orange-50 to-orange-100 border border-orange-200 flex items-center justify-center text-primary group-hover:scale-110 transition-transform duration-500 shadow-warm-md relative z-10">
                        <span className="material-symbols-outlined text-[50px] sm:text-[60px]">cloud_upload</span>
                      </div>
                      <div className="absolute -bottom-2 -right-2 w-10 h-10 rounded-full bg-teal-accent text-white flex items-center justify-center shadow-md z-20 group-hover:-translate-y-2 group-hover:translate-x-2 transition-transform duration-500">
                        <span className="material-symbols-outlined text-[24px]">add</span>
                      </div>
                    </div>
                    
                    <h3 className="font-display font-extrabold text-3xl sm:text-4xl text-on-surface tracking-tight mb-4 relative z-10">
                      Drop your WhatsApp export here
                    </h3>
                    
                    <p className="font-body text-base sm:text-lg text-on-surface-variant max-w-xl mx-auto leading-relaxed relative z-10 group-hover:text-on-surface transition-colors">
                      Export your chat from WhatsApp via <strong className="text-on-surface font-extrabold">Export Chat &gt; Without Media</strong> (.zip or .txt).
                    </p>
                    
                    <div className="flex flex-wrap items-center justify-center gap-3 mt-8 relative z-10">
                      <span className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-surface-muted/80 backdrop-blur-sm text-xs font-bold text-on-surface border border-surface-border shadow-warm-sm group-hover:bg-white transition-colors">
                        <span className="material-symbols-outlined text-[16px] text-primary">folder_zip</span>.ZIP archive
                      </span>
                      <span className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-emerald-50/80 backdrop-blur-sm text-teal-accent border border-emerald-200 text-xs font-bold shadow-warm-sm group-hover:bg-emerald-50 transition-colors">
                        <span className="material-symbols-outlined text-[16px]">lock</span>100% Client Encrypted
                      </span>
                    </div>
                  </div>
                </div>
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 pt-4">
              {chats.map((chat, i) => {
                const accent = CARD_ACCENTS[i % CARD_ACCENTS.length];
                const initials = chat.name
                  .split(/\s+/)
                  .slice(0, 2)
                  .map((w) => w[0])
                  .join("")
                  .toUpperCase();

                return (
                  <Link
                    key={chat.id}
                    href={`/chat/${chat.id}`}
                    className="block outline-none group relative"
                  >
                    {/* Accent glowing aura behind the card on hover */}
                    <div 
                      className="absolute inset-0 rounded-3xl opacity-0 group-hover:opacity-100 blur-xl transition-opacity duration-500 -z-10"
                      style={{ background: accent, opacity: '0.15' }}
                    ></div>

                    <div className="warm-card rounded-3xl p-6 shadow-warm-sm hover:shadow-warm-lg hover-lift flex flex-col h-full relative z-10 bg-white/95 backdrop-blur-sm overflow-hidden">
                      
                      {/* Subtle accent line on top */}
                      <div className="absolute top-0 left-0 w-full h-1 opacity-0 group-hover:opacity-100 transition-opacity duration-300" style={{ background: accent }}></div>

                      {/* Card Header */}
                      <div className="flex items-start gap-4 mb-5">
                        <div
                          className="w-12 h-12 rounded-2xl flex items-center justify-center font-display font-bold text-lg shrink-0 transition-transform duration-500 group-hover:rotate-3 group-hover:scale-110 shadow-sm"
                          style={{
                            background: accent + "18",
                            border: `1px solid ${accent}30`,
                            color: accent,
                          }}
                        >
                          {initials || "💬"}
                        </div>
                        <div className="flex-1 min-w-0 pt-1">
                          <h3 className="font-display font-extrabold text-lg text-on-surface truncate group-hover:text-primary transition-colors duration-300">
                            {chat.name}
                          </h3>
                          <p className="text-sm text-on-surface-subtle font-medium mt-0.5">
                            {chat.participant_count} participant{chat.participant_count !== 1 ? "s" : ""}
                          </p>
                        </div>
                      </div>

                      {/* Stats */}
                      <div className="flex items-center gap-4 p-4 rounded-2xl bg-surface-muted/50 border border-surface-border mb-5 group-hover:bg-surface-muted transition-colors duration-300">
                        <StatChip label="Messages" value={formatNumber(chat.message_count)} accent={accent} />
                        <div className="w-px h-10 bg-surface-border"></div>
                        <StatChip label="From" value={formatDateShort(chat.first_message_at)} accent={accent} />
                      </div>

                      {/* Footer */}
                      <div className="mt-auto pt-2 flex items-center justify-between text-xs font-bold text-on-surface-subtle tracking-wider uppercase">
                        <span>Last: {formatDateShort(chat.last_message_at)}</span>
                        <span className="flex items-center gap-1 group-hover:translate-x-2 transition-transform duration-300" style={{ color: accent }}>
                          Enter <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
                        </span>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </section>
        <PremiumFooter />
      </main>
    </>
  );
}

function PremiumFooter() {
  return (
    <footer className="w-full relative z-10 mt-20">
      <div className="absolute inset-0 bg-on-surface -z-10"></div>
      {/* Subtle top border glow */}
      <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent"></div>
      
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 lg:py-20">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-12 lg:gap-8 mb-12">
          <div className="lg:col-span-2">
            <div className="flex items-center gap-3 group cursor-pointer mb-6">
              <div className="w-10 h-10 rounded-[12px] bg-gradient-to-br from-primary to-amber-accent flex items-center justify-center text-white shadow-warm-md group-hover:shadow-warm-lg transition-all duration-300 transform group-hover:-rotate-3 group-hover:scale-105">
                <svg
                  className="w-5 h-5 stroke-white fill-none"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2.5"
                  viewBox="0 0 24 24"
                >
                  <circle cx="9" cy="12" r="5" />
                  <circle cx="15" cy="12" r="5" />
                </svg>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-display font-black text-2xl tracking-tighter text-white block leading-tight">Silsila <span className="text-primary opacity-90 font-extrabold">AI</span></span>
                <span className="text-xs text-slate-400 font-medium tracking-wide border-l border-slate-700 pl-2 ml-1">Your relationships, understood.</span>
              </div>
            </div>
            <p className="text-slate-400 text-sm leading-relaxed max-w-sm mb-6">
              Turn endless WhatsApp group banter, family voice notes, and late-night chats into a living, searchable memory engine.
            </p>
            <div className="flex items-center gap-4">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-800 text-xs font-bold text-slate-300 border border-slate-700">
                <span className="material-symbols-outlined text-[16px] text-teal-400">verified_user</span> 100% Private
              </span>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-800 text-xs font-bold text-slate-300 border border-slate-700">
                <span className="material-symbols-outlined text-[16px] text-primary">bolt</span> Lightning Fast
              </span>
            </div>
          </div>
          
          <div>
            <h4 className="font-display font-bold text-white mb-4 tracking-wide">Product</h4>
            <ul className="space-y-3">
              <li><a href="#" className="text-slate-400 hover:text-white transition-colors text-sm font-medium">Dashboard</a></li>
              <li><a href="/upload" className="text-slate-400 hover:text-white transition-colors text-sm font-medium">Upload Chat</a></li>
              <li><a href="#" className="text-slate-400 hover:text-white transition-colors text-sm font-medium">Privacy Architecture</a></li>
              <li><a href="#" className="text-slate-400 hover:text-white transition-colors text-sm font-medium">Security Details</a></li>
            </ul>
          </div>
          
          <div>
            <h4 className="font-display font-bold text-white mb-4 tracking-wide">Connect</h4>
            <ul className="space-y-3">
              <li><a href="#" className="text-slate-400 hover:text-white transition-colors text-sm font-medium flex items-center gap-2"><span className="material-symbols-outlined text-[18px]">support_agent</span> Help Center</a></li>
              <li><a href="#" className="text-slate-400 hover:text-white transition-colors text-sm font-medium flex items-center gap-2"><span className="material-symbols-outlined text-[18px]">bug_report</span> Report Issue</a></li>
              <li><a href="#" className="text-slate-400 hover:text-white transition-colors text-sm font-medium flex items-center gap-2"><span className="material-symbols-outlined text-[18px]">mail</span> Contact Us</a></li>
            </ul>
          </div>
        </div>
        
        <div className="pt-8 border-t border-slate-800 flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-slate-500 text-sm font-medium">
            © {new Date().getFullYear()} Silsila AI. All rights reserved.
          </p>
          <div className="flex gap-4 text-sm font-medium">
            <a href="#" className="text-slate-500 hover:text-slate-300 transition-colors">Terms of Service</a>
            <a href="#" className="text-slate-500 hover:text-slate-300 transition-colors">Privacy Policy</a>
          </div>
        </div>
      </div>
    </footer>
  );
}

function StatChip({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent: string;
}) {
  return (
    <div className="flex-1 transform transition-transform duration-300 group-hover:scale-[1.02]">
      <div className="text-[11px] text-on-surface-subtle mb-1 uppercase tracking-widest font-extrabold">
        {label}
      </div>
      <div
        className="font-display font-extrabold text-lg sm:text-xl"
        style={{ color: accent }}
      >
        {value}
      </div>
    </div>
  );
}

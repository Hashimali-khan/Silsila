import { auth } from "@clerk/nextjs/server";
import { api } from "@/lib/api";
import type { Chat } from "@/lib/types";
import { AppNav } from "@/components/AppNav";
import { PhysicsHero } from "@/components/PhysicsHero";
import { DashboardClient } from "@/components/DashboardClient";
import { AlertCircle, ShieldCheck, Zap, Headphones, Bug, Mail } from "lucide-react";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Dashboard — Silsila",
  description: "Your uploaded chats and conversation history.",
};

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
      <main className="pt-16 overflow-hidden min-h-screen bg-slate-50/50">
        {error && (
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8">
            <div className="bg-red-50 border border-red-200 rounded-2xl p-4 text-red-700 text-sm font-medium flex items-center gap-2 shadow-warm-sm">
              <AlertCircle size={20} />
              <span>{error}</span>
            </div>
          </div>
        )}

        <DashboardClient initialChats={chats} />

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
            <p className="text-slate-300 text-sm leading-relaxed max-w-sm mb-6">
              Turn endless WhatsApp group banter, family voice notes, and late-night chats into a living, searchable memory engine.
            </p>
            <div className="flex items-center gap-4">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-800 text-xs font-bold text-slate-300 border border-slate-700">
                <ShieldCheck size={16} className="text-teal-400" /> 100% Private
              </span>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-800 text-xs font-bold text-slate-300 border border-slate-700">
                <Zap size={16} className="text-primary" /> Lightning Fast
              </span>
            </div>
          </div>
          
          <div>
            <h3 className="font-display font-bold text-white mb-4 tracking-wide">Product</h3>
            <ul className="space-y-3">
              <li><a href="#" className="text-slate-300 hover:text-white transition-colors text-sm font-medium">Dashboard</a></li>
              <li><a href="/upload" className="text-slate-300 hover:text-white transition-colors text-sm font-medium">Upload Chat</a></li>
              <li><a href="#" className="text-slate-300 hover:text-white transition-colors text-sm font-medium">Privacy Architecture</a></li>
              <li><a href="#" className="text-slate-300 hover:text-white transition-colors text-sm font-medium">Security Details</a></li>
            </ul>
          </div>
          
          <div>
            <h3 className="font-display font-bold text-white mb-4 tracking-wide">Connect</h3>
            <ul className="space-y-3">
              <li><a href="#" className="text-slate-300 hover:text-white transition-colors text-sm font-medium flex items-center gap-2"><Headphones size={18} /> Help Center</a></li>
              <li><a href="#" className="text-slate-300 hover:text-white transition-colors text-sm font-medium flex items-center gap-2"><Bug size={18} /> Report Issue</a></li>
              <li><a href="#" className="text-slate-300 hover:text-white transition-colors text-sm font-medium flex items-center gap-2"><Mail size={18} /> Contact Us</a></li>
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

"use client";

import { useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { AppNav } from "@/components/AppNav";
import { STEP_LABELS, stepProgress } from "@/lib/utils";
import type { JobStatus } from "@/lib/types";
import { motion, AnimatePresence } from "framer-motion";
import { CloudUpload, Settings, CheckCircle, AlertTriangle, FileArchive, FileText, Sparkles } from "lucide-react";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

type UploadState =
  | { phase: "idle" }
  | { phase: "uploading" }
  | { phase: "processing"; jobId: string; status: JobStatus }
  | { phase: "done"; chatId: string }
  | { phase: "error"; message: string };

export default function UploadPage() {
  const router = useRouter();
  const { getToken } = useAuth();
  const [state, setState] = useState<UploadState>({ phase: "idle" });
  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const startUpload = useCallback(
    async (file: File) => {
      setState({ phase: "uploading" });

      try {
        const token = await getToken();
        if (!token) throw new Error("Not authenticated");

        const formData = new FormData();
        formData.append("file", file);

        const res = await fetch(`${BACKEND_URL}/api/parse/whatsapp`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: "Upload failed" }));
          throw new Error(err.detail || "Upload failed");
        }

        const { job_id } = await res.json();

        // Start checking job progress
        subscribeToJobProgress(job_id, token);
      } catch (e) {
        setState({ phase: "error", message: e instanceof Error ? e.message : "Upload failed" });
      }
    },
    [getToken],
  );

  const subscribeToJobProgress = (jobId: string, token: string) => {
    let pollInterval: ReturnType<typeof setInterval> | null = null;

    const startPolling = () => {
      pollInterval = setInterval(async () => {
        try {
          const res = await fetch(`${BACKEND_URL}/api/parse/jobs/${jobId}`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (!res.ok) return;
          const job: JobStatus = await res.json();
          handleJobUpdate(job);
          if (job.status === "complete" || job.status === "failed") {
            if (pollInterval) clearInterval(pollInterval);
          }
        } catch {
          // keep polling
        }
      }, 1500);
    };

    const handleJobUpdate = (job: JobStatus) => {
      if (job.status === "complete" && job.chat_id) {
        setState({ phase: "done", chatId: job.chat_id });
        setTimeout(() => router.push(`/chat/${job.chat_id}`), 1500);
        return;
      }
      if (job.status === "failed") {
        setState({ phase: "error", message: job.error_message || "Processing failed" });
        return;
      }
      setState({ phase: "processing", jobId, status: job });
    };

    setState({
      phase: "processing",
      jobId,
      status: {
        job_id: jobId,
        status: "pending",
        current_step: "queued",
        total_messages: 0,
        processed_messages: 0,
        error_message: null,
        chat_id: null,
      },
    });
    startPolling();
  };

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) {
        setSelectedFile(file);
        startUpload(file);
      }
    },
    [startUpload],
  );

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      startUpload(file);
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <AppNav />
      <main className="flex-1 w-full max-w-3xl mx-auto px-4 sm:px-6 py-16 sm:py-24 relative flex flex-col justify-center">
        {/* Glow behind main container */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-primary/10 blur-[100px] rounded-full pointer-events-none -z-10" />

        <div className="text-center mb-10">
          <motion.h1 
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="font-display font-extrabold text-3xl sm:text-4xl text-on-surface mb-3 tracking-tight"
          >
            Upload a WhatsApp Chat
          </motion.h1>
          <motion.p 
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="font-body text-on-surface-variant max-w-md mx-auto"
          >
            Export a chat from WhatsApp as a <strong className="font-extrabold text-on-surface">.txt</strong> file or <strong className="font-extrabold text-on-surface">.zip</strong> archive, then drop it here.
          </motion.p>
        </div>

        <div className="relative z-10 w-full max-w-2xl mx-auto">
          <AnimatePresence mode="wait">
            
            {/* IDLE DROPZONE */}
            {state.phase === "idle" && (
              <motion.div
                key="idle"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.3 }}
                className="w-full"
              >
                <div
                  className={`relative group cursor-pointer transition-all duration-300 ${dragOver ? 'scale-[1.02]' : ''}`}
                  onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={handleDrop}
                  onClick={() => inputRef.current?.click()}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
                  aria-label="Upload WhatsApp export file"
                >
                  <div className={`absolute inset-0 rounded-[2rem] transition-opacity duration-300 -z-10 ${dragOver ? 'opacity-100 blur-xl' : 'opacity-0 group-hover:opacity-100 blur-lg'}`} style={{ background: 'var(--color-primary)', opacity: dragOver ? 0.3 : 0.15 }}></div>
                  <div className={`relative glass-panel rounded-[2rem] p-10 sm:p-14 text-center border-2 border-dashed transition-colors duration-300 shadow-warm-md hover:shadow-warm-xl ${dragOver ? 'border-primary bg-primary-light/40' : 'border-surface-border bg-white/70 hover:bg-white/90 hover:border-primary/50'}`}>
                    
                    <input
                      ref={inputRef}
                      type="file"
                      accept=".txt,.zip"
                      className="hidden"
                      onChange={handleFileSelect}
                      id="file-upload-input"
                    />

                    <motion.div
                      animate={dragOver ? { y: [0, -10, 0] } : {}}
                      transition={{ repeat: Infinity, duration: 1.5 }}
                      className="w-20 h-20 mx-auto bg-gradient-to-br from-orange-50 to-orange-100 border border-orange-200 rounded-2xl flex items-center justify-center text-primary mb-6 shadow-warm-sm group-hover:scale-110 transition-transform duration-300"
                    >
                      <CloudUpload size={40} strokeWidth={1.5} />
                    </motion.div>

                    <h3 className="font-display font-extrabold text-xl sm:text-2xl text-on-surface mb-2 tracking-tight">
                      Drop your chat export here
                    </h3>
                    <p className="text-on-surface-subtle font-medium mb-8">
                      or click to browse files
                    </p>

                    <div className="flex flex-wrap items-center justify-center gap-3">
                      <span className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-surface-muted border border-surface-border text-xs font-bold text-on-surface-variant group-hover:bg-white transition-colors">
                        <FileArchive size={14} className="text-primary" /> .ZIP archive
                      </span>
                      <span className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-surface-muted border border-surface-border text-xs font-bold text-on-surface-variant group-hover:bg-white transition-colors">
                        <FileText size={14} className="text-primary" /> .TXT file
                      </span>
                    </div>
                  </div>
                </div>

                <div className="mt-12 text-left bg-surface-muted/50 rounded-[1.5rem] p-6 sm:p-8 border border-surface-border">
                  <h3 className="font-display font-extrabold text-lg text-on-surface mb-4 tracking-tight">How to export from WhatsApp</h3>
                  <ol className="space-y-3 text-sm text-on-surface-variant font-medium list-decimal list-inside leading-relaxed">
                    <li>Open the chat you want to analyze in WhatsApp</li>
                    <li>Tap <strong className="text-on-surface font-black">⋮ More</strong> (Android) or the contact name (iOS)</li>
                    <li>Select <strong className="text-on-surface font-black">Export Chat → Without Media</strong></li>
                    <li>Save the .txt file and upload it here</li>
                  </ol>
                </div>
              </motion.div>
            )}

            {/* UPLOADING STATE */}
            {state.phase === "uploading" && (
              <StatusCard icon={<CloudUpload size={28} className="animate-bounce" />} title="Uploading..." subtitle={selectedFile?.name || ""}>
                <ProgressBar value={20} animated />
              </StatusCard>
            )}

            {/* PROCESSING STATE */}
            {state.phase === "processing" && (
              <StatusCard
                icon={<Settings size={28} className="animate-spin text-teal-600" />}
                title={STEP_LABELS[state.status.current_step] || "Processing..."}
                subtitle={selectedFile?.name || ""}
                iconBg="bg-teal-50"
              >
                <ProgressBar
                  value={stepProgress(
                    state.status.current_step,
                    state.status.total_messages,
                    state.status.processed_messages,
                  )}
                  animated
                />
                <div className="flex flex-wrap justify-center gap-2 mt-6">
                  {["parsing", "storing", "threading", "complete"].map((step) => {
                    const order = ["parsing", "storing", "threading", "complete"];
                    const currentIdx = order.indexOf(state.status.current_step);
                    const stepIdx = order.indexOf(step);
                    const done = stepIdx < currentIdx || state.status.current_step === "complete";
                    const active = step === state.status.current_step;
                    return (
                      <StepPill key={step} label={STEP_LABELS[step] || step} done={done} active={active} />
                    );
                  })}
                </div>
                {state.status.total_messages > 0 && (
                  <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-[11px] font-extrabold text-on-surface-subtle mt-5 uppercase tracking-widest">
                    {state.status.processed_messages.toLocaleString()} /{" "}
                    {state.status.total_messages.toLocaleString()} messages
                  </motion.p>
                )}
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 1 }}
                  className="mt-6 p-4 bg-amber-50/80 border border-amber-200 rounded-2xl text-xs font-semibold text-amber-800 flex items-start gap-3 text-left shadow-sm backdrop-blur-sm"
                >
                  <Sparkles size={16} className="mt-0.5 shrink-0 text-amber-600" />
                  <p>The analysis engine may take up to 30 seconds to wake up on first use.</p>
                </motion.div>
              </StatusCard>
            )}

            {/* DONE STATE */}
            {state.phase === "done" && (
              <StatusCard 
                icon={<CheckCircle size={28} className="text-emerald-600" />} 
                title="Processing complete!" 
                subtitle="Redirecting to your chat..."
                iconBg="bg-emerald-50"
              >
                <ProgressBar value={100} />
              </StatusCard>
            )}

            {/* ERROR STATE */}
            {state.phase === "error" && (
              <motion.div
                key="error"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="bg-red-50/90 backdrop-blur-xl border border-red-200 rounded-[2rem] p-10 text-center shadow-warm-xl relative overflow-hidden"
              >
                <div className="absolute top-0 left-0 w-full h-1 bg-red-500"></div>
                <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center text-red-600 mb-6 mx-auto shadow-sm">
                  <AlertTriangle size={32} />
                </div>
                <h3 className="font-display font-extrabold text-2xl text-red-700 tracking-tight mb-2">Upload failed</h3>
                <p className="text-sm font-medium text-red-600/80 mb-8 max-w-sm mx-auto">{state.message}</p>
                <button
                  className="bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-8 rounded-full shadow-md hover:shadow-xl hover:-translate-y-0.5 active:translate-y-0 transition-all focus:ring-4 focus:ring-red-600/20"
                  onClick={() => setState({ phase: "idle" })}
                >
                  Try again
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────

function StatusCard({
  icon,
  title,
  subtitle,
  children,
  iconBg = "bg-orange-50"
}: {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  children: React.ReactNode;
  iconBg?: string;
}) {
  return (
    <motion.div
      key="status-card"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="relative glass-panel animated-gradient-border rounded-[2rem] p-1 shadow-warm-xl mx-auto w-full"
    >
      <div className="bg-white/95 backdrop-blur-3xl rounded-[1.85rem] p-8 sm:p-12 text-center flex flex-col items-center justify-center">
        <div className={`w-16 h-16 rounded-full ${iconBg} flex items-center justify-center text-primary mb-6 shadow-sm`}>
          {icon}
        </div>
        <h3 className="font-display font-extrabold text-2xl text-on-surface tracking-tight mb-2">
          {title}
        </h3>
        {subtitle && (
          <p className="text-sm font-bold text-on-surface-subtle mb-8 max-w-sm truncate">
            {subtitle}
          </p>
        )}
        <div className="w-full">
          {children}
        </div>
      </div>
    </motion.div>
  );
}

function ProgressBar({ value, animated = false }: { value: number; animated?: boolean }) {
  return (
    <div className="w-full h-3 bg-surface-border rounded-full overflow-hidden relative shadow-inner">
      <motion.div 
        initial={{ width: 0 }}
        animate={{ width: `${Math.min(value, 100)}%` }}
        transition={{ duration: 0.5, ease: "easeInOut" }}
        className="absolute top-0 left-0 h-full bg-gradient-to-r from-primary to-amber-accent rounded-full"
      />
      {/* Animated shimmer over the progress bar */}
      {animated && (
        <div className="absolute top-0 left-0 w-full h-full bg-[linear-gradient(90deg,transparent,rgba(255,255,255,0.4),transparent)] -translate-x-full animate-[shimmer_2s_infinite]" />
      )}
    </div>
  );
}

function StepPill({
  label,
  done,
  active,
}: {
  label: string;
  done: boolean;
  active: boolean;
}) {
  return (
    <motion.span
      layout
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ 
        scale: active ? 1.05 : 1,
        opacity: (done || active) ? 1 : 0.6,
      }}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-[11px] font-extrabold tracking-wide uppercase border transition-colors ${
        done ? "bg-orange-100 text-orange-700 border-orange-200" 
        : active ? "bg-orange-50 text-primary border-orange-300 shadow-sm"
        : "bg-surface-muted text-on-surface-subtle border-transparent"
      }`}
    >
      {done && <CheckCircle size={14} />}
      {active && <Settings size={14} className="animate-spin" />}
      {label}
    </motion.span>
  );
}

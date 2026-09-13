"use client";

import { useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { AppNav } from "@/components/AppNav";
import { STEP_LABELS, stepProgress } from "@/lib/utils";
import type { JobStatus } from "@/lib/types";

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
  const eventSourceRef = useRef<EventSource | null>(null);

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

        // Start SSE stream
        subscribeToJobProgress(job_id, token);
      } catch (e) {
        setState({ phase: "error", message: e instanceof Error ? e.message : "Upload failed" });
      }
    },
    [getToken],
  );

  const subscribeToJobProgress = (jobId: string, token: string) => {
    // EventSource doesn't support custom headers, so we pass token as query param
    // Note: For production, use a short-lived signed token or cookie auth
    const url = `${BACKEND_URL}/api/parse/jobs/${jobId}/stream?token=${encodeURIComponent(token)}`;

    // Fallback to polling if SSE fails
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

    // Try SSE first (won't work if backend requires auth header for SSE)
    // Fall back to polling — reliable across all setups
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

  const isProcessing =
    state.phase === "uploading" || state.phase === "processing";

  return (
    <div style={{ minHeight: "100vh", background: "var(--background)" }}>
      <AppNav />

      <main
        style={{
          maxWidth: "680px",
          margin: "0 auto",
          padding: "3rem 1.5rem",
        }}
      >
        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: "2.5rem" }}>
          <h1
            style={{
              fontFamily: "'Plus Jakarta Sans', sans-serif",
              fontWeight: 800,
              fontSize: "2rem",
              color: "var(--text-primary)",
              margin: "0 0 0.5rem",
            }}
          >
            Upload a WhatsApp Chat
          </h1>
          <p style={{ color: "var(--text-secondary)", margin: 0 }}>
            Export a chat from WhatsApp as a <strong>.txt</strong> file, then drop it here.
          </p>
        </div>

        {/* Dropzone */}
        {state.phase === "idle" && (
          <div
            className={`dropzone ${dragOver ? "dragover" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
            aria-label="Upload WhatsApp export file"
          >
            <input
              ref={inputRef}
              type="file"
              accept=".txt,.zip"
              style={{ display: "none" }}
              onChange={handleFileSelect}
              id="file-upload-input"
            />

            <div
              style={{
                width: "64px",
                height: "64px",
                background: "var(--orange-50)",
                border: "2px solid var(--orange-200)",
                borderRadius: "16px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 1.25rem",
                fontSize: "1.75rem",
                transition: "all 0.2s ease",
              }}
            >
              ☁️
            </div>

            <h3
              style={{
                fontFamily: "'Plus Jakarta Sans', sans-serif",
                fontWeight: 700,
                fontSize: "1.1rem",
                color: "var(--text-primary)",
                margin: "0 0 0.5rem",
              }}
            >
              Drop your chat export here
            </h3>
            <p style={{ color: "var(--text-secondary)", margin: "0 0 1.25rem", fontSize: "0.9rem" }}>
              or click to browse files
            </p>

            {/* File type badges */}
            <div style={{ display: "flex", gap: "0.5rem", justifyContent: "center" }}>
              {[".ZIP archive", ".TXT file"].map((label) => (
                <span
                  key={label}
                  style={{
                    padding: "0.25rem 0.75rem",
                    background: "var(--stone-100)",
                    border: "1px solid var(--stone-200)",
                    borderRadius: "var(--radius-full)",
                    fontSize: "0.8rem",
                    color: "var(--text-secondary)",
                    fontWeight: 500,
                  }}
                >
                  {label}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Uploading spinner */}
        {state.phase === "uploading" && (
          <StatusCard icon="⏫" title="Uploading…" subtitle={selectedFile?.name || ""}>
            <ProgressBar value={5} />
          </StatusCard>
        )}

        {/* Processing with live progress */}
        {state.phase === "processing" && (
          <StatusCard
            icon="⚙️"
            title={STEP_LABELS[state.status.current_step] || "Processing…"}
            subtitle={selectedFile?.name || ""}
          >
            <ProgressBar
              value={stepProgress(
                state.status.current_step,
                state.status.total_messages,
                state.status.processed_messages,
              )}
            />

            {/* Step pills */}
            <div
              style={{
                display: "flex",
                gap: "0.375rem",
                flexWrap: "wrap",
                marginTop: "1rem",
              }}
            >
              {["parsing", "storing", "threading", "complete"].map((step) => {
                const order = ["parsing", "storing", "threading", "complete"];
                const currentIdx = order.indexOf(state.status.current_step);
                const stepIdx = order.indexOf(step);
                const done = stepIdx < currentIdx || state.status.current_step === "complete";
                const active = step === state.status.current_step;
                return (
                  <StepPill
                    key={step}
                    label={STEP_LABELS[step] || step}
                    done={done}
                    active={active}
                  />
                );
              })}
            </div>

            {state.status.total_messages > 0 && (
              <p style={{ fontSize: "0.825rem", color: "var(--text-muted)", margin: "0.75rem 0 0", textAlign: "center" }}>
                {state.status.processed_messages.toLocaleString()} /{" "}
                {state.status.total_messages.toLocaleString()} messages
              </p>
            )}

            {/* Cold start warning */}
            <div
              style={{
                marginTop: "1rem",
                padding: "0.75rem 1rem",
                background: "var(--orange-50)",
                border: "1px solid var(--orange-200)",
                borderRadius: "var(--radius-md)",
                fontSize: "0.8125rem",
                color: "var(--orange-700)",
                display: "flex",
                gap: "0.5rem",
                alignItems: "flex-start",
              }}
            >
              <span>💡</span>
              <span>
                The analysis engine may take up to 30 seconds to wake up on first use.
              </span>
            </div>
          </StatusCard>
        )}

        {/* Done */}
        {state.phase === "done" && (
          <StatusCard icon="✅" title="Processing complete!" subtitle="Redirecting to your chat…">
            <ProgressBar value={100} />
          </StatusCard>
        )}

        {/* Error */}
        {state.phase === "error" && (
          <div
            style={{
              background: "#fff1f2",
              border: "1px solid #fda4af",
              borderRadius: "var(--radius-xl)",
              padding: "2rem",
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem" }}>⚠️</div>
            <h3
              style={{
                fontFamily: "'Plus Jakarta Sans', sans-serif",
                fontWeight: 700,
                color: "#be123c",
                margin: "0 0 0.5rem",
              }}
            >
              Upload failed
            </h3>
            <p style={{ color: "#9f1239", fontSize: "0.9rem", margin: "0 0 1.25rem" }}>
              {state.message}
            </p>
            <button
              className="btn-primary"
              onClick={() => setState({ phase: "idle" })}
              id="retry-upload-btn"
            >
              Try again
            </button>
          </div>
        )}

        {/* How to export instructions */}
        {state.phase === "idle" && (
          <div style={{ marginTop: "2.5rem" }}>
            <h3
              style={{
                fontFamily: "'Plus Jakarta Sans', sans-serif",
                fontWeight: 700,
                fontSize: "0.9375rem",
                color: "var(--text-primary)",
                margin: "0 0 1rem",
              }}
            >
              How to export from WhatsApp
            </h3>
            <ol
              style={{
                paddingLeft: "1.25rem",
                color: "var(--text-secondary)",
                fontSize: "0.875rem",
                lineHeight: 1.8,
                margin: 0,
              }}
            >
              <li>Open the chat you want to analyze</li>
              <li>
                Tap <strong>⋮ More</strong> (Android) or the contact name (iOS)
              </li>
              <li>
                Select <strong>Export Chat → Without Media</strong>
              </li>
              <li>Save the .txt file and upload it here</li>
            </ol>
          </div>
        )}
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
}: {
  icon: string;
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className="card fade-in"
      style={{ padding: "2rem", textAlign: "center" }}
    >
      <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem" }}>{icon}</div>
      <h3
        style={{
          fontFamily: "'Plus Jakarta Sans', sans-serif",
          fontWeight: 700,
          fontSize: "1.125rem",
          color: "var(--text-primary)",
          margin: "0 0 0.25rem",
        }}
      >
        {title}
      </h3>
      {subtitle && (
        <p style={{ color: "var(--text-muted)", fontSize: "0.875rem", margin: "0 0 1.25rem" }}>
          {subtitle}
        </p>
      )}
      {children}
    </div>
  );
}

function ProgressBar({ value }: { value: number }) {
  return (
    <div className="progress-bar-track" style={{ margin: "0 auto" }}>
      <div className="progress-bar-fill" style={{ width: `${Math.min(value, 100)}%` }} />
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
    <span
      style={{
        padding: "0.25rem 0.625rem",
        borderRadius: "var(--radius-full)",
        fontSize: "0.75rem",
        fontWeight: 500,
        background: done
          ? "var(--orange-100)"
          : active
          ? "var(--orange-50)"
          : "var(--stone-100)",
        color: done || active ? "var(--orange-700)" : "var(--text-muted)",
        border: active ? "1px solid var(--orange-300)" : "1px solid transparent",
        display: "inline-flex",
        alignItems: "center",
        gap: "0.25rem",
      }}
    >
      {done ? "✓ " : active ? "⟳ " : ""}
      {label}
    </span>
  );
}

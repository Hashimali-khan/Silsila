/**
 * Utilities for consistent sender color assignment and message formatting.
 */

// Deterministically assign one of 8 bubble color classes to a sender name
export function senderColorClass(senderName: string): string {
  let hash = 0;
  for (let i = 0; i < senderName.length; i++) {
    hash = senderName.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % 8;
  return `bubble-${index}`;
}

// Short sender initial for avatar
export function senderInitial(name: string): string {
  return name.trim().charAt(0).toUpperCase();
}

// Format a timestamp to a human-readable string
export function formatTime(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function formatDate(timestamp: string): string {
  const date = new Date(timestamp);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  if (date.toDateString() === today.toDateString()) return "Today";
  if (date.toDateString() === yesterday.toDateString()) return "Yesterday";

  return date.toLocaleDateString([], {
    weekday: "long",
    day: "numeric",
    month: "long",
    year:
      date.getFullYear() !== today.getFullYear() ? "numeric" : undefined,
  });
}

export function formatDateShort(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" });
}

export function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

// Group messages by date for the chat browser's date separator headers
export function groupMessagesByDate<T extends { timestamp: string }>(
  messages: T[],
): Array<{ dateLabel: string; messages: T[] }> {
  const groups: Map<string, T[]> = new Map();
  for (const msg of messages) {
    const key = new Date(msg.timestamp).toDateString();
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(msg);
  }
  return Array.from(groups.entries()).map(([key, msgs]) => ({
    dateLabel: formatDate(msgs[0].timestamp),
    messages: msgs,
  }));
}

// Step label for the ingestion progress display
export const STEP_LABELS: Record<string, string> = {
  queued:    "Queued",
  parsing:   "Parsing messages…",
  creating:  "Setting up contacts…",
  storing:   "Saving to database…",
  threading: "Detecting conversations…",
  stats:     "Computing statistics…",
  complete:  "Done!",
  failed:    "Failed",
};

export function stepProgress(step: string, total: number, processed: number): number {
  const stepOrder: Record<string, number> = {
    queued: 0, parsing: 15, creating: 30, storing: 50,
    threading: 75, stats: 90, complete: 100, failed: 0,
  };
  const base = stepOrder[step] ?? 0;
  if (step === "storing" && total > 0) {
    return 30 + (processed / total) * 20;
  }
  return base;
}

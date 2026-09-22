// Shared TypeScript types for the Silsila frontend

export interface Chat {
  id: string;
  name: string;
  participant_count: number;
  message_count: number;
  first_message_at: string;
  last_message_at: string;
  created_at: string;
}

export interface Person {
  id: string;
  canonical_name: string;
  message_count: number;
  first_seen_at: string;
  last_seen_at: string;
}

export interface Message {
  id: string;
  sender_name: string;
  timestamp: string;
  content: string;
  is_media: boolean;
  person_id: string | null;
}

export interface MessagesPageResponse {
  chat_id: string;
  messages: Message[];
  has_more: boolean;
  oldest_timestamp: string | null;
}

export interface SearchResult {
  id: string;
  sender_name: string;
  timestamp: string;
  content: string;
  person_id: string | null;
  highlight: string; // HTML with <mark> tags
}

export interface SearchResponse {
  query: string;
  total: number;
  results: SearchResult[];
}

export interface JobStatus {
  job_id: string;
  status: "pending" | "parsing" | "storing" | "threading" | "stats" | "complete" | "failed";
  current_step: string;
  total_messages: number;
  processed_messages: number;
  error_message: string | null;
  chat_id: string | null;
}

export interface DailyActivity {
  date: string;
  message_count: number;
  active_senders: number;
}

export interface SenderBreakdown {
  sender_name: string;
  message_count: number;
}

export interface ChatStats {
  total_messages: number;
  thread_count: number;
  participants: string[];
  messages_per_sender: Record<string, number>;
  date_range: { start: string; end: string };
  daily_activity: DailyActivity[];
  sender_breakdown: SenderBreakdown[];
}

export interface ChatDetail extends Chat {
  people: Person[];
}

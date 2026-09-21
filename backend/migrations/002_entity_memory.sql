-- =============================================================
-- Silsila AI Memory Engine — Migration 002
-- Adds entity-anchored structured memory (Phase 3)
-- Run ONLY if 001 has already been applied (i.e., on existing DBs).
-- Safe to run multiple times (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS).
-- =============================================================

-- Add entity_ids column to message_chunks (backfilled during ingestion step 5.5)
ALTER TABLE public.message_chunks
    ADD COLUMN IF NOT EXISTS entity_ids UUID[] DEFAULT '{}';

-- ENTITY MENTIONS — junction: message ↔ entity
-- Original messages.content is NEVER modified; annotations live here.
CREATE TABLE IF NOT EXISTS public.entity_mentions (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id           TEXT NOT NULL,
    message_id        UUID NOT NULL REFERENCES public.messages(id) ON DELETE CASCADE,
    person_id         UUID NOT NULL REFERENCES public.people(id) ON DELETE CASCADE,
    mention_text      TEXT NOT NULL,       -- original surface form: "he", "bhai", "Abdullah"
    resolution_method TEXT NOT NULL,       -- 'exact_alias' | 'llm_coref' | 'hitl_confirmed'
    confidence        FLOAT DEFAULT 1.0,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(message_id, person_id, mention_text)
);

-- RLS
ALTER TABLE public.entity_mentions ENABLE  ROW LEVEL SECURITY;
ALTER TABLE public.entity_mentions FORCE   ROW LEVEL SECURITY;

CREATE POLICY IF NOT EXISTS "own_data" ON public.entity_mentions
    FOR ALL USING (user_id = current_setting('app.user_id', true));

-- Indexes
CREATE INDEX IF NOT EXISTS idx_entity_mentions_person  ON public.entity_mentions(person_id);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_message ON public.entity_mentions(message_id);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_user    ON public.entity_mentions(user_id);
CREATE INDEX IF NOT EXISTS idx_chunks_entity_ids       ON public.message_chunks USING GIN(entity_ids);

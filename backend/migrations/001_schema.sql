-- =============================================================
-- Silsila AI Memory Engine — Database Migration
-- Stack: Heroku Mini Postgres + Native RLS (ADR §12)
-- Run: psql $DATABASE_URL -f migrations/001_schema.sql
-- =============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- for fuzzy alias matching

-- =============================================================
-- TABLES
-- =============================================================

-- PROFILES
-- One row per Clerk user. Auto-created on first API request.
CREATE TABLE IF NOT EXISTS public.profiles (
    id          TEXT PRIMARY KEY,  -- Clerk user_id (e.g. user_2abc...)
    email       TEXT,
    full_name   TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- CHATS
-- A distinct WhatsApp export (one upload = one chat)
CREATE TABLE IF NOT EXISTS public.chats (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id           TEXT NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    name              TEXT NOT NULL,
    participant_count INTEGER DEFAULT 2,
    message_count     INTEGER DEFAULT 0,
    first_message_at  TIMESTAMPTZ,
    last_message_at   TIMESTAMPTZ,
    metadata          JSONB DEFAULT '{}',
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- PEOPLE
-- Unique identities extracted from chats. Foundation for character profiles.
CREATE TABLE IF NOT EXISTS public.people (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         TEXT NOT NULL,  -- denormalized for fast RLS
    canonical_name  TEXT NOT NULL,
    message_count   INTEGER DEFAULT 0,
    first_seen_at   TIMESTAMPTZ,
    last_seen_at    TIMESTAMPTZ,
    profile         JSONB DEFAULT '{}',  -- AI-generated profile (Phase 3)
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ALIASES
-- Maps nicknames / alternate handles to a canonical person.
CREATE TABLE IF NOT EXISTS public.aliases (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     TEXT NOT NULL,  -- denormalized
    person_id   UUID NOT NULL REFERENCES public.people(id) ON DELETE CASCADE,
    alias       TEXT NOT NULL,
    confidence  FLOAT DEFAULT 1.0,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(person_id, alias)
);

-- MESSAGES
-- Central store for all parsed messages. search_vector auto-populated by trigger.
CREATE TABLE IF NOT EXISTS public.messages (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id       TEXT NOT NULL,  -- denormalized for RLS
    chat_id       UUID NOT NULL REFERENCES public.chats(id) ON DELETE CASCADE,
    person_id     UUID REFERENCES public.people(id) ON DELETE SET NULL,
    sender_name   TEXT NOT NULL,
    timestamp     TIMESTAMPTZ NOT NULL,
    content       TEXT NOT NULL,
    is_system_msg BOOLEAN DEFAULT FALSE,
    is_media      BOOLEAN DEFAULT FALSE,
    metadata      JSONB DEFAULT '{}',
    search_vector TSVECTOR,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-populate tsvector for full-text search (simple config = multilingual-safe)
CREATE OR REPLACE FUNCTION update_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector('simple', COALESCE(NEW.content, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS messages_search_vector_trigger ON public.messages;
CREATE TRIGGER messages_search_vector_trigger
    BEFORE INSERT OR UPDATE OF content ON public.messages
    FOR EACH ROW EXECUTE FUNCTION update_search_vector();

-- CONVERSATION THREADS
-- Grouped by adaptive time-gap detection (ADR §3)
CREATE TABLE IF NOT EXISTS public.conversation_threads (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id       TEXT NOT NULL,
    chat_id       UUID NOT NULL REFERENCES public.chats(id) ON DELETE CASCADE,
    start_time    TIMESTAMPTZ NOT NULL,
    end_time      TIMESTAMPTZ NOT NULL,
    message_count INTEGER DEFAULT 0,
    summary       TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Junction: message ↔ thread
CREATE TABLE IF NOT EXISTS public.message_threads (
    message_id UUID NOT NULL REFERENCES public.messages(id) ON DELETE CASCADE,
    thread_id  UUID NOT NULL REFERENCES public.conversation_threads(id) ON DELETE CASCADE,
    PRIMARY KEY (message_id, thread_id)
);

-- MESSAGE CHUNKS
-- Conversation window embeddings. Vectors stored in Qdrant (not here).
-- This table holds the relational metadata; qdrant_id links to Qdrant point.
CREATE TABLE IF NOT EXISTS public.message_chunks (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id          TEXT NOT NULL,
    chat_id          UUID NOT NULL REFERENCES public.chats(id) ON DELETE CASCADE,
    thread_id        UUID REFERENCES public.conversation_threads(id) ON DELETE SET NULL,
    qdrant_id        TEXT UNIQUE,  -- Qdrant point ID (same as id cast to string)
    start_message_id UUID NOT NULL,
    end_message_id   UUID NOT NULL,
    start_time       TIMESTAMPTZ NOT NULL,
    end_time         TIMESTAMPTZ NOT NULL,
    content          TEXT NOT NULL,   -- concatenated messages text
    message_ids      UUID[] NOT NULL,
    message_count    INTEGER NOT NULL,
    voyage_tokens    INTEGER DEFAULT 0,  -- tokens used for this chunk embedding
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- INGESTION JOBS
-- Persisted progress for every upload job (ADR §11 idempotency requirement).
-- Progress survives dyno restarts.
CREATE TABLE IF NOT EXISTS public.ingestion_jobs (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             TEXT NOT NULL,
    chat_id             UUID REFERENCES public.chats(id) ON DELETE SET NULL,
    status              TEXT NOT NULL DEFAULT 'pending',
    -- statuses: pending | parsing | storing | threading | chunking | embedding | complete | failed
    file_name           TEXT,
    total_messages      INTEGER DEFAULT 0,
    processed_messages  INTEGER DEFAULT 0,
    total_chunks        INTEGER DEFAULT 0,
    embedded_chunks     INTEGER DEFAULT 0,
    voyage_tokens_used  INTEGER DEFAULT 0,
    current_step        TEXT DEFAULT 'waiting',
    error_message       TEXT,
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- VOYAGE TOKEN LEDGER
-- Tracks cumulative Voyage AI token usage against the 200M free grant.
CREATE TABLE IF NOT EXISTS public.voyage_token_ledger (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      TEXT NOT NULL,
    job_id       UUID REFERENCES public.ingestion_jobs(id) ON DELETE SET NULL,
    tokens_used  INTEGER NOT NULL,
    cumulative   BIGINT NOT NULL,  -- running total across all users
    recorded_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ALIAS SUGGESTIONS (Human-in-the-Loop — Phase 3)
CREATE TABLE IF NOT EXISTS public.alias_suggestions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             TEXT NOT NULL,
    suggested_alias     TEXT NOT NULL,
    suggested_person_id UUID REFERENCES public.people(id) ON DELETE CASCADE,
    status              TEXT NOT NULL DEFAULT 'pending',
    -- statuses: pending | accepted | rejected | new_person
    confidence          FLOAT DEFAULT 0.0,
    evidence_message_ids UUID[] DEFAULT '{}',
    context_snippet     TEXT,
    resolved_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- RELATIONSHIPS (graph edges — Phase 3)
CREATE TABLE IF NOT EXISTS public.relationships (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id           TEXT NOT NULL,
    person_a_id       UUID NOT NULL REFERENCES public.people(id) ON DELETE CASCADE,
    person_b_id       UUID NOT NULL REFERENCES public.people(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL DEFAULT 'mentioned_together',
    strength          FLOAT DEFAULT 0.0,
    first_detected    TIMESTAMPTZ,
    last_detected     TIMESTAMPTZ,
    metadata          JSONB DEFAULT '{}',
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(person_a_id, person_b_id, relationship_type)
);

-- EVENTS (Phase 4)
CREATE TABLE IF NOT EXISTS public.events (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     TEXT NOT NULL,
    chat_id     UUID REFERENCES public.chats(id) ON DELETE CASCADE,
    type        TEXT NOT NULL,  -- ghosting | fight | celebration | confession | distance
    description TEXT,
    detected_at TIMESTAMPTZ,
    evidence    JSONB DEFAULT '[]',  -- [{message_id, snippet}]
    people_ids  UUID[] DEFAULT '{}',
    confidence  FLOAT DEFAULT 0.0,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- EMOTION LABELS (Phase 4)
CREATE TABLE IF NOT EXISTS public.emotion_labels (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    TEXT NOT NULL,
    message_id UUID NOT NULL REFERENCES public.messages(id) ON DELETE CASCADE,
    emotion    TEXT NOT NULL,
    score      FLOAT DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ANALYSIS CACHE (precomputed stats for fast dashboard)
CREATE TABLE IF NOT EXISTS public.analysis_cache (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     TEXT NOT NULL,
    chat_id     UUID REFERENCES public.chats(id) ON DELETE CASCADE,
    person_id   UUID REFERENCES public.people(id) ON DELETE CASCADE,
    metric_type TEXT NOT NULL,
    data        JSONB NOT NULL,
    computed_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================
-- INDEXES
-- =============================================================

CREATE INDEX IF NOT EXISTS idx_chats_user          ON public.chats(user_id);
CREATE INDEX IF NOT EXISTS idx_people_user         ON public.people(user_id);
CREATE INDEX IF NOT EXISTS idx_aliases_person      ON public.aliases(person_id);
CREATE INDEX IF NOT EXISTS idx_aliases_user        ON public.aliases(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_chat       ON public.messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_person     ON public.messages(person_id);
CREATE INDEX IF NOT EXISTS idx_messages_ts         ON public.messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_user       ON public.messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_search     ON public.messages USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_messages_non_system ON public.messages(chat_id, timestamp)
    WHERE is_system_msg = FALSE;
CREATE INDEX IF NOT EXISTS idx_threads_chat        ON public.conversation_threads(chat_id);
CREATE INDEX IF NOT EXISTS idx_threads_user        ON public.conversation_threads(user_id);
CREATE INDEX IF NOT EXISTS idx_chunks_chat         ON public.message_chunks(chat_id);
CREATE INDEX IF NOT EXISTS idx_chunks_user         ON public.message_chunks(user_id);
CREATE INDEX IF NOT EXISTS idx_chunks_thread       ON public.message_chunks(thread_id);
CREATE INDEX IF NOT EXISTS idx_jobs_user           ON public.ingestion_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_suggestions_pending ON public.alias_suggestions(user_id)
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_relationships_a     ON public.relationships(person_a_id);
CREATE INDEX IF NOT EXISTS idx_relationships_user  ON public.relationships(user_id);
CREATE INDEX IF NOT EXISTS idx_events_chat         ON public.events(chat_id);
CREATE INDEX IF NOT EXISTS idx_emotions_message    ON public.emotion_labels(message_id);
CREATE INDEX IF NOT EXISTS idx_cache_chat          ON public.analysis_cache(chat_id);

-- Trigram index for fuzzy alias matching (Phase 3 coreference)
CREATE INDEX IF NOT EXISTS idx_aliases_trgm
    ON public.aliases USING GIN(alias gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_people_name_trgm
    ON public.people USING GIN(canonical_name gin_trgm_ops);

-- =============================================================
-- NATIVE ROW LEVEL SECURITY (ADR §12)
-- Uses current_setting('app.user_id', true) set per-connection
-- by the application layer (db/connection.py → set_rls_user).
-- This makes cross-user data leaks structurally impossible.
-- =============================================================

ALTER TABLE public.profiles           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chats              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.people             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.aliases            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversation_threads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.message_threads    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.message_chunks     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ingestion_jobs     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.voyage_token_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alias_suggestions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.relationships      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.events             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.emotion_labels     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.analysis_cache     ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.profiles           FORCE ROW LEVEL SECURITY;
ALTER TABLE public.chats              FORCE ROW LEVEL SECURITY;
ALTER TABLE public.people             FORCE ROW LEVEL SECURITY;
ALTER TABLE public.aliases            FORCE ROW LEVEL SECURITY;
ALTER TABLE public.messages           FORCE ROW LEVEL SECURITY;
ALTER TABLE public.conversation_threads FORCE ROW LEVEL SECURITY;
ALTER TABLE public.message_threads    FORCE ROW LEVEL SECURITY;
ALTER TABLE public.message_chunks     FORCE ROW LEVEL SECURITY;
ALTER TABLE public.ingestion_jobs     FORCE ROW LEVEL SECURITY;
ALTER TABLE public.voyage_token_ledger FORCE ROW LEVEL SECURITY;
ALTER TABLE public.alias_suggestions  FORCE ROW LEVEL SECURITY;
ALTER TABLE public.relationships      FORCE ROW LEVEL SECURITY;
ALTER TABLE public.events             FORCE ROW LEVEL SECURITY;
ALTER TABLE public.emotion_labels     FORCE ROW LEVEL SECURITY;
ALTER TABLE public.analysis_cache     FORCE ROW LEVEL SECURITY;

-- Allow superuser / migration user to bypass RLS
CREATE POLICY "own_data" ON public.profiles
    FOR ALL USING (id = current_setting('app.user_id', true));

CREATE POLICY "own_data" ON public.chats
    FOR ALL USING (user_id = current_setting('app.user_id', true));

CREATE POLICY "own_data" ON public.people
    FOR ALL USING (user_id = current_setting('app.user_id', true));

CREATE POLICY "own_data" ON public.aliases
    FOR ALL USING (user_id = current_setting('app.user_id', true));

CREATE POLICY "own_data" ON public.messages
    FOR ALL USING (user_id = current_setting('app.user_id', true));

CREATE POLICY "own_data" ON public.conversation_threads
    FOR ALL USING (user_id = current_setting('app.user_id', true));

CREATE POLICY "own_data" ON public.message_chunks
    FOR ALL USING (user_id = current_setting('app.user_id', true));

CREATE POLICY "own_data" ON public.ingestion_jobs
    FOR ALL USING (user_id = current_setting('app.user_id', true));

CREATE POLICY "own_data" ON public.voyage_token_ledger
    FOR ALL USING (user_id = current_setting('app.user_id', true));

CREATE POLICY "own_data" ON public.alias_suggestions
    FOR ALL USING (user_id = current_setting('app.user_id', true));

CREATE POLICY "own_data" ON public.relationships
    FOR ALL USING (user_id = current_setting('app.user_id', true));

CREATE POLICY "own_data" ON public.events
    FOR ALL USING (user_id = current_setting('app.user_id', true));

CREATE POLICY "own_data" ON public.emotion_labels
    FOR ALL USING (user_id = current_setting('app.user_id', true));

CREATE POLICY "own_data" ON public.analysis_cache
    FOR ALL USING (user_id = current_setting('app.user_id', true));

-- message_threads needs a join (not on hot path)
CREATE POLICY "own_data" ON public.message_threads
    FOR ALL USING (
        message_id IN (
            SELECT id FROM public.messages
            WHERE user_id = current_setting('app.user_id', true)
        )
    );

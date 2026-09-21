"""baseline schema

Revision ID: 0001_baseline_schema
Revises: None
Create Date: 2026-09-20 14:55:00

"""
from typing import Sequence, Union
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_baseline_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm";')

    # Tables
    op.execute("""
    CREATE TABLE IF NOT EXISTS public.profiles (
        id          TEXT PRIMARY KEY,
        email       TEXT,
        full_name   TEXT,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    op.execute("""
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
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS public.people (
        id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id         TEXT NOT NULL,
        canonical_name  TEXT NOT NULL,
        message_count   INTEGER DEFAULT 0,
        first_seen_at   TIMESTAMPTZ,
        last_seen_at    TIMESTAMPTZ,
        profile         JSONB DEFAULT '{}',
        created_at      TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS public.aliases (
        id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id     TEXT NOT NULL,
        person_id   UUID NOT NULL REFERENCES public.people(id) ON DELETE CASCADE,
        alias       TEXT NOT NULL,
        confidence  FLOAT DEFAULT 1.0,
        created_at  TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(person_id, alias)
    );
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS public.messages (
        id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id       TEXT NOT NULL,
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
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION update_search_vector()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.search_vector := to_tsvector('simple', COALESCE(NEW.content, ''));
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    DROP TRIGGER IF EXISTS messages_search_vector_trigger ON public.messages;
    """)

    op.execute("""
    CREATE TRIGGER messages_search_vector_trigger
        BEFORE INSERT OR UPDATE OF content ON public.messages
        FOR EACH ROW EXECUTE FUNCTION update_search_vector();
    """)

    op.execute("""
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
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS public.message_threads (
        message_id UUID NOT NULL REFERENCES public.messages(id) ON DELETE CASCADE,
        thread_id  UUID NOT NULL REFERENCES public.conversation_threads(id) ON DELETE CASCADE,
        PRIMARY KEY (message_id, thread_id)
    );
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS public.message_chunks (
        id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id          TEXT NOT NULL,
        chat_id          UUID NOT NULL REFERENCES public.chats(id) ON DELETE CASCADE,
        thread_id        UUID REFERENCES public.conversation_threads(id) ON DELETE SET NULL,
        qdrant_id        TEXT UNIQUE,
        start_message_id UUID NOT NULL,
        end_message_id   UUID NOT NULL,
        start_time       TIMESTAMPTZ NOT NULL,
        end_time         TIMESTAMPTZ NOT NULL,
        content          TEXT NOT NULL,
        message_ids      UUID[] NOT NULL,
        message_count    INTEGER NOT NULL,
        voyage_tokens    INTEGER DEFAULT 0,
        created_at       TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS public.ingestion_jobs (
        id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id             TEXT NOT NULL,
        chat_id             UUID REFERENCES public.chats(id) ON DELETE SET NULL,
        status              TEXT NOT NULL DEFAULT 'pending',
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
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS public.voyage_token_ledger (
        id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id      TEXT NOT NULL,
        job_id       UUID REFERENCES public.ingestion_jobs(id) ON DELETE SET NULL,
        tokens_used  INTEGER NOT NULL,
        cumulative   BIGINT NOT NULL,
        recorded_at  TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS public.alias_suggestions (
        id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id             TEXT NOT NULL,
        suggested_alias     TEXT NOT NULL,
        suggested_person_id UUID REFERENCES public.people(id) ON DELETE CASCADE,
        status              TEXT NOT NULL DEFAULT 'pending',
        confidence          FLOAT DEFAULT 0.0,
        evidence_message_ids UUID[] DEFAULT '{}',
        context_snippet     TEXT,
        resolved_at         TIMESTAMPTZ,
        created_at          TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    op.execute("""
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
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS public.events (
        id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id     TEXT NOT NULL,
        chat_id     UUID REFERENCES public.chats(id) ON DELETE CASCADE,
        type        TEXT NOT NULL,
        description TEXT,
        detected_at TIMESTAMPTZ,
        evidence    JSONB DEFAULT '[]',
        people_ids  UUID[] DEFAULT '{}',
        confidence  FLOAT DEFAULT 0.0,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS public.emotion_labels (
        id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id    TEXT NOT NULL,
        message_id UUID NOT NULL REFERENCES public.messages(id) ON DELETE CASCADE,
        emotion    TEXT NOT NULL,
        score      FLOAT DEFAULT 0.0,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    op.execute("""
    CREATE TABLE IF NOT EXISTS public.analysis_cache (
        id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id     TEXT NOT NULL,
        chat_id     UUID REFERENCES public.chats(id) ON DELETE CASCADE,
        person_id   UUID REFERENCES public.people(id) ON DELETE CASCADE,
        metric_type TEXT NOT NULL,
        data        JSONB NOT NULL,
        computed_at TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    # Indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_chats_user ON public.chats(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_people_user ON public.people(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_aliases_person ON public.aliases(person_id);",
        "CREATE INDEX IF NOT EXISTS idx_aliases_user ON public.aliases(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_messages_chat ON public.messages(chat_id);",
        "CREATE INDEX IF NOT EXISTS idx_messages_person ON public.messages(person_id);",
        "CREATE INDEX IF NOT EXISTS idx_messages_ts ON public.messages(timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_messages_user ON public.messages(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_messages_search ON public.messages USING GIN(search_vector);",
        "CREATE INDEX IF NOT EXISTS idx_messages_non_system ON public.messages(chat_id, timestamp) WHERE is_system_msg = FALSE;",
        "CREATE INDEX IF NOT EXISTS idx_threads_chat ON public.conversation_threads(chat_id);",
        "CREATE INDEX IF NOT EXISTS idx_threads_user ON public.conversation_threads(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_chunks_chat ON public.message_chunks(chat_id);",
        "CREATE INDEX IF NOT EXISTS idx_chunks_user ON public.message_chunks(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_chunks_thread ON public.message_chunks(thread_id);",
        "CREATE INDEX IF NOT EXISTS idx_jobs_user ON public.ingestion_jobs(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_suggestions_pending ON public.alias_suggestions(user_id) WHERE status = 'pending';",
        "CREATE INDEX IF NOT EXISTS idx_relationships_a ON public.relationships(person_a_id);",
        "CREATE INDEX IF NOT EXISTS idx_relationships_user ON public.relationships(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_events_chat ON public.events(chat_id);",
        "CREATE INDEX IF NOT EXISTS idx_emotions_message ON public.emotion_labels(message_id);",
        "CREATE INDEX IF NOT EXISTS idx_cache_chat ON public.analysis_cache(chat_id);",
        "CREATE INDEX IF NOT EXISTS idx_aliases_trgm ON public.aliases USING GIN(alias gin_trgm_ops);",
        "CREATE INDEX IF NOT EXISTS idx_people_name_trgm ON public.people USING GIN(canonical_name gin_trgm_ops);",
    ]
    for idx_sql in indexes:
        op.execute(idx_sql)

    # RLS Enable & Force
    tables = [
        "profiles", "chats", "people", "aliases", "messages",
        "conversation_threads", "message_threads", "message_chunks",
        "ingestion_jobs", "voyage_token_ledger", "alias_suggestions",
        "relationships", "events", "emotion_labels", "analysis_cache",
    ]
    for tbl in tables:
        op.execute(f"ALTER TABLE public.{tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE public.{tbl} FORCE ROW LEVEL SECURITY;")

    # Policies
    for tbl in ["chats", "people", "aliases", "messages", "conversation_threads", "message_chunks", "ingestion_jobs", "voyage_token_ledger", "alias_suggestions", "relationships", "events", "emotion_labels", "analysis_cache"]:
        op.execute(f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'own_data' AND tablename = '{tbl}') THEN
                CREATE POLICY "own_data" ON public.{tbl} FOR ALL USING (user_id = current_setting('app.user_id', true));
            END IF;
        END $$;
        """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'own_data' AND tablename = 'profiles') THEN
            CREATE POLICY "own_data" ON public.profiles FOR ALL USING (id = current_setting('app.user_id', true));
        END IF;
    END $$;
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'own_data' AND tablename = 'message_threads') THEN
            CREATE POLICY "own_data" ON public.message_threads FOR ALL USING (
                EXISTS (
                    SELECT 1 FROM public.messages WHERE id = message_id AND user_id = current_setting('app.user_id', true)
                )
            );
        END IF;
    END $$;
    """)


def downgrade() -> None:
    tables = [
        "analysis_cache", "emotion_labels", "events", "relationships",
        "alias_suggestions", "voyage_token_ledger", "ingestion_jobs",
        "message_chunks", "message_threads", "conversation_threads",
        "messages", "aliases", "people", "chats", "profiles"
    ]
    for tbl in tables:
        op.execute(f"DROP TABLE IF EXISTS public.{tbl} CASCADE;")
    op.execute("DROP TRIGGER IF EXISTS messages_search_vector_trigger ON public.messages;")
    op.execute("DROP FUNCTION IF EXISTS update_search_vector();")

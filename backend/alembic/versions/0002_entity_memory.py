"""add entity_mentions and entity_ids for structured memory

Revision ID: 0002_entity_memory
Revises: 0001_baseline_schema
Create Date: 2026-09-20 15:00:00

"""
from typing import Sequence, Union
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_entity_memory"
down_revision: Union[str, Sequence[str], None] = "0001_baseline_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add entity_ids column to message_chunks (backfilled during ingestion step 5.5)
    op.execute("""
    ALTER TABLE public.message_chunks
        ADD COLUMN IF NOT EXISTS entity_ids UUID[] DEFAULT '{}';
    """)

    # 2. ENTITY MENTIONS — junction: message <-> entity
    # Original messages.content is NEVER modified; annotations live here.
    op.execute("""
    CREATE TABLE IF NOT EXISTS public.entity_mentions (
        id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id           TEXT NOT NULL,
        message_id        UUID NOT NULL REFERENCES public.messages(id) ON DELETE CASCADE,
        person_id         UUID NOT NULL REFERENCES public.people(id) ON DELETE CASCADE,
        mention_text      TEXT NOT NULL,
        resolution_method TEXT NOT NULL,
        confidence        FLOAT DEFAULT 1.0,
        created_at        TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(message_id, person_id, mention_text)
    );
    """)

    # 3. Row Level Security for entity_mentions
    op.execute("ALTER TABLE public.entity_mentions ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.entity_mentions FORCE ROW LEVEL SECURITY;")

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE policyname = 'own_data' AND tablename = 'entity_mentions'
        ) THEN
            CREATE POLICY "own_data" ON public.entity_mentions
                FOR ALL USING (user_id = current_setting('app.user_id', true));
        END IF;
    END $$;
    """)

    # 4. Performance Indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_entity_mentions_person  ON public.entity_mentions(person_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_entity_mentions_message ON public.entity_mentions(message_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_entity_mentions_user    ON public.entity_mentions(user_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chunks_entity_ids       ON public.message_chunks USING GIN(entity_ids);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.idx_chunks_entity_ids;")
    op.execute("DROP INDEX IF EXISTS public.idx_entity_mentions_user;")
    op.execute("DROP INDEX IF EXISTS public.idx_entity_mentions_message;")
    op.execute("DROP INDEX IF EXISTS public.idx_entity_mentions_person;")
    op.execute("DROP TABLE IF EXISTS public.entity_mentions CASCADE;")
    op.execute("ALTER TABLE public.message_chunks DROP COLUMN IF EXISTS entity_ids;")

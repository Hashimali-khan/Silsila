"""add cascade performance foreign key indexes

Revision ID: 0003_cascade_perf_indexes
Revises: 0002_entity_memory
Create Date: 2026-09-21 19:15:00

"""
from typing import Sequence, Union
from alembic import op

revision: str = "0003_cascade_perf_indexes"
down_revision: Union[str, Sequence[str], None] = "0002_entity_memory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS idx_message_threads_thread ON public.message_threads(thread_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_chat ON public.ingestion_jobs(chat_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_voyage_tokens_job ON public.voyage_token_ledger(job_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_alias_suggestions_person ON public.alias_suggestions(suggested_person_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_relationships_b ON public.relationships(person_b_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cache_person ON public.analysis_cache(person_id);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.idx_message_threads_thread;")
    op.execute("DROP INDEX IF EXISTS public.idx_ingestion_jobs_chat;")
    op.execute("DROP INDEX IF EXISTS public.idx_voyage_tokens_job;")
    op.execute("DROP INDEX IF EXISTS public.idx_alias_suggestions_person;")
    op.execute("DROP INDEX IF EXISTS public.idx_relationships_b;")
    op.execute("DROP INDEX IF EXISTS public.idx_cache_person;")

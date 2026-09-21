"""entity_timeline.py — Entity Timeline API

GET /api/entities/{person_id}/timeline?chat_id=...

Returns all chunks mentioning a person, ordered chronologically, with:
- The original message content (never rewritten)
- The entity_mentions annotations for that chunk (how each mention was resolved)
- Aliases and canonical name for the person

This is the "trace everything about Abdullah" surface:
pure SQL against message_chunks WHERE $person_id = ANY(entity_ids),
ordered by start_time.
"""

import logging
from typing import Optional, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.connection import get_pool, set_rls_user
from app.dependencies import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter()


class EntityMentionAnnotation(BaseModel):
    mention_text: str
    resolution_method: str  # 'exact_alias' | 'llm_coref' | 'hitl_confirmed'
    confidence: float


class TimelineChunk(BaseModel):
    chunk_id: str
    thread_id: Optional[str]
    start_time: Any
    end_time: Any
    content: str                             # raw, original, never rewritten
    entity_mentions: list[EntityMentionAnnotation]


class PersonSummary(BaseModel):
    id: str
    canonical_name: str
    aliases: list[str]
    message_count: int


class EntityTimelineResponse(BaseModel):
    person: PersonSummary
    timeline: list[TimelineChunk]
    total_chunks: int


@router.get("/entities/{person_id}/timeline", response_model=EntityTimelineResponse)
async def get_entity_timeline(
    person_id: str,
    chat_id: str = Query(..., description="UUID of the chat to search within"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user_id),
):
    """
    Return all message chunks that mention a given person, ordered chronologically.

    Uses the entity_ids GIN index on message_chunks for fast array-containment lookup.
    Each chunk includes the original unmodified text and any resolved entity annotations.
    """
    pool = await get_pool()

    async with pool.acquire() as conn:
        await set_rls_user(conn, user_id)

        # ── Fetch person + aliases ────────────────────────────────────────────
        person_row = await conn.fetchrow(
            """
            SELECT id::text, canonical_name, message_count
            FROM public.people
            WHERE id = $1::uuid AND user_id = $2
            """,
            person_id, user_id,
        )
        if not person_row:
            raise HTTPException(status_code=404, detail="Person not found.")

        alias_rows = await conn.fetch(
            """
            SELECT alias FROM public.aliases
            WHERE person_id = $1::uuid AND user_id = $2
              AND lower(alias) != lower($3)
            ORDER BY confidence DESC
            """,
            person_id, user_id, person_row["canonical_name"],
        )
        aliases = [r["alias"] for r in alias_rows]

        # ── Count total chunks mentioning this person ─────────────────────────
        total_chunks = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM public.message_chunks
            WHERE chat_id = $1::uuid
              AND user_id = $2
              AND $3::uuid = ANY(entity_ids)
            """,
            chat_id, user_id, person_id,
        )

        # ── Fetch paginated chunks ────────────────────────────────────────────
        chunk_rows = await conn.fetch(
            """
            SELECT id::text, thread_id::text, start_time, end_time,
                   content, message_ids
            FROM public.message_chunks
            WHERE chat_id = $1::uuid
              AND user_id = $2
              AND $3::uuid = ANY(entity_ids)
            ORDER BY start_time ASC
            LIMIT $4 OFFSET $5
            """,
            chat_id, user_id, person_id, limit, offset,
        )

        # ── For each chunk, fetch entity_mention annotations ──────────────────
        timeline: list[TimelineChunk] = []
        for chunk in chunk_rows:
            message_ids = [str(mid) for mid in (chunk["message_ids"] or [])]

            mention_rows = await conn.fetch(
                """
                SELECT mention_text, resolution_method, confidence
                FROM public.entity_mentions
                WHERE person_id = $1::uuid
                  AND message_id = ANY($2::uuid[])
                  AND user_id = $3
                ORDER BY confidence DESC
                """,
                person_id, message_ids, user_id,
            )

            annotations = [
                EntityMentionAnnotation(
                    mention_text=r["mention_text"],
                    resolution_method=r["resolution_method"],
                    confidence=r["confidence"],
                )
                for r in mention_rows
            ]

            timeline.append(
                TimelineChunk(
                    chunk_id=chunk["id"],
                    thread_id=chunk["thread_id"],
                    start_time=chunk["start_time"],
                    end_time=chunk["end_time"],
                    content=chunk["content"],
                    entity_mentions=annotations,
                )
            )

    return EntityTimelineResponse(
        person=PersonSummary(
            id=str(person_row["id"]),
            canonical_name=person_row["canonical_name"],
            aliases=aliases,
            message_count=person_row["message_count"],
        ),
        timeline=timeline,
        total_chunks=total_chunks or 0,
    )

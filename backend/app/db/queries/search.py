"""Full-text search database queries using Postgres tsvector."""

import asyncpg
from typing import Any


async def keyword_search(
    conn: asyncpg.Connection,
    chat_id: str,
    query: str,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Full-text keyword search within a chat using Postgres tsvector + ts_headline.

    Uses the 'simple' text search config for multilingual support (Urdu, Hinglish).
    ts_headline wraps matching terms in <mark> tags for frontend highlighting.

    Args:
        conn: asyncpg connection (must have RLS user set).
        chat_id: UUID string of the target chat.
        query: Raw search string from user (e.g., "birthday party").
        limit: Max results to return.
        offset: Pagination offset.

    Returns:
        List of matching messages with highlighted snippets.
    """
    # Convert raw query to tsquery — websearch_to_tsquery handles partial words,
    # phrases, and boolean operators naturally
    rows = await conn.fetch(
        """
        SELECT
            m.id::text,
            m.sender_name,
            m.timestamp,
            m.content,
            m.person_id::text,
            ts_headline(
                'simple',
                m.content,
                websearch_to_tsquery('simple', $2),
                'StartSel=<mark>, StopSel=</mark>, MaxWords=30, MinWords=15, ShortWord=3'
            ) AS highlight,
            ts_rank(m.search_vector, websearch_to_tsquery('simple', $2)) AS rank
        FROM public.messages m
        WHERE m.chat_id = $1::uuid
          AND m.is_system_msg = FALSE
          AND m.search_vector @@ websearch_to_tsquery('simple', $2)
        ORDER BY rank DESC, m.timestamp DESC
        LIMIT $3 OFFSET $4
        """,
        chat_id,
        query,
        limit,
        offset,
    )
    return [dict(r) for r in rows]


async def keyword_search_count(
    conn: asyncpg.Connection,
    chat_id: str,
    query: str,
) -> int:
    """Count total matching messages for pagination."""
    count = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM public.messages
        WHERE chat_id = $1::uuid
          AND is_system_msg = FALSE
          AND search_vector @@ websearch_to_tsquery('simple', $2)
        """,
        chat_id,
        query,
    )
    return count or 0

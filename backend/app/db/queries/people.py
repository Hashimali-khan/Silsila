"""People database queries."""

import asyncpg
from typing import Any


async def get_people_for_chat(
    conn: asyncpg.Connection,
    chat_id: str,
) -> list[dict[str, Any]]:
    """
    Get all people who participated in a specific chat.

    Joins via messages to find unique person_ids for this chat,
    then returns their canonical_name and message_count.
    """
    rows = await conn.fetch(
        """
        SELECT DISTINCT ON (p.id)
            p.id::text,
            p.canonical_name,
            p.message_count,
            p.first_seen_at,
            p.last_seen_at
        FROM public.people p
        JOIN public.messages m ON m.person_id = p.id
        WHERE m.chat_id = $1::uuid
        ORDER BY p.id, p.message_count DESC
        """,
        chat_id,
    )
    return [dict(r) for r in rows]


async def get_all_people(
    conn: asyncpg.Connection,
) -> list[dict[str, Any]]:
    """List all unique people for the authenticated user, ordered by message count."""
    rows = await conn.fetch(
        """
        SELECT
            id::text,
            canonical_name,
            message_count,
            first_seen_at,
            last_seen_at,
            profile
        FROM public.people
        ORDER BY message_count DESC
        """
    )
    return [dict(r) for r in rows]

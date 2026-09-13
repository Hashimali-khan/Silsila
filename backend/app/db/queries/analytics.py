"""Analytics database queries — basic stats for Phase 1 dashboard."""

import asyncpg
from typing import Any


async def get_chat_stats(
    conn: asyncpg.Connection,
    chat_id: str,
) -> dict[str, Any] | None:
    """
    Get pre-computed basic stats for a chat from the analysis_cache table.

    These are populated at the end of the ingestion pipeline.
    Returns None if stats haven't been computed yet.
    """
    row = await conn.fetchrow(
        """
        SELECT data
        FROM public.analysis_cache
        WHERE chat_id = $1::uuid
          AND metric_type = 'basic_stats'
        ORDER BY computed_at DESC
        LIMIT 1
        """,
        chat_id,
    )
    return dict(row["data"]) if row else None


async def get_messages_per_day(
    conn: asyncpg.Connection,
    chat_id: str,
) -> list[dict[str, Any]]:
    """
    Time-series: messages per calendar day for charting.

    Aggregates non-system messages by date, ordered chronologically.
    Used for the activity chart in the chat view.
    """
    rows = await conn.fetch(
        """
        SELECT
            DATE(timestamp AT TIME ZONE 'UTC') AS date,
            COUNT(*) AS message_count,
            COUNT(DISTINCT sender_name) AS active_senders
        FROM public.messages
        WHERE chat_id = $1::uuid
          AND is_system_msg = FALSE
        GROUP BY DATE(timestamp AT TIME ZONE 'UTC')
        ORDER BY date ASC
        """,
        chat_id,
    )
    return [
        {
            "date": r["date"].isoformat(),
            "message_count": r["message_count"],
            "active_senders": r["active_senders"],
        }
        for r in rows
    ]


async def get_messages_per_sender(
    conn: asyncpg.Connection,
    chat_id: str,
) -> list[dict[str, Any]]:
    """Message count breakdown per sender for pie/bar chart."""
    rows = await conn.fetch(
        """
        SELECT sender_name, COUNT(*) AS message_count
        FROM public.messages
        WHERE chat_id = $1::uuid
          AND is_system_msg = FALSE
        GROUP BY sender_name
        ORDER BY message_count DESC
        """,
        chat_id,
    )
    return [dict(r) for r in rows]

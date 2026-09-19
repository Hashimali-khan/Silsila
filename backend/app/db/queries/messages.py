from datetime import datetime
import asyncpg
from typing import Any


async def get_messages_page(
    conn: asyncpg.Connection,
    chat_id: str,
    limit: int = 100,
    before_timestamp: str | datetime | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch a page of messages for a chat, ordered newest-first then reversed
    for display (so the UI shows oldest at top, newest at bottom).

    Uses cursor-based pagination via timestamp for infinite scroll.
    Only returns non-system messages.

    Args:
        conn: asyncpg connection (must have RLS user set).
        chat_id: UUID string of the chat.
        limit: Number of messages per page (default 100).
        before_timestamp: ISO timestamp — fetch messages *before* this time.
                          Pass None for the first page (fetches newest messages).

    Returns:
        List of message dicts ordered chronologically (oldest first for display).
    """
    ts_val: datetime | None = None
    if before_timestamp:
        if isinstance(before_timestamp, str):
            try:
                ts_val = datetime.fromisoformat(before_timestamp.replace("Z", "+00:00"))
            except ValueError:
                ts_val = None
        elif isinstance(before_timestamp, datetime):
            ts_val = before_timestamp

    if ts_val is not None:
        rows = await conn.fetch(
            """
            SELECT
                id::text,
                sender_name,
                timestamp,
                content,
                is_system_msg,
                is_media,
                person_id::text
            FROM public.messages
            WHERE chat_id = $1::uuid
              AND is_system_msg = FALSE
              AND timestamp < $2
            ORDER BY timestamp DESC
            LIMIT $3
            """,
            chat_id,
            ts_val,
            limit,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT
                id::text,
                sender_name,
                timestamp,
                content,
                is_system_msg,
                is_media,
                person_id::text
            FROM public.messages
            WHERE chat_id = $1::uuid
              AND is_system_msg = FALSE
            ORDER BY timestamp DESC
            LIMIT $2
            """,
            chat_id,
            limit,
        )

    # Reverse to chronological order for display
    return [dict(r) for r in reversed(rows)]


async def get_message_by_id(
    conn: asyncpg.Connection,
    message_id: str,
) -> dict[str, Any] | None:
    """Fetch a single message by its UUID (RLS scoped)."""
    row = await conn.fetchrow(
        """
        SELECT
            id::text,
            chat_id::text,
            sender_name,
            timestamp,
            content,
            is_system_msg,
            is_media,
            person_id::text
        FROM public.messages
        WHERE id = $1::uuid
        """,
        message_id,
    )
    return dict(row) if row else None


async def get_chat_list(
    conn: asyncpg.Connection,
) -> list[dict[str, Any]]:
    """
    List all chats for the authenticated user, ordered by most recent message.

    Returns chat cards with name, participant count, message count, date range.
    """
    rows = await conn.fetch(
        """
        SELECT
            id::text,
            name,
            participant_count,
            message_count,
            first_message_at,
            last_message_at,
            created_at
        FROM public.chats
        ORDER BY last_message_at DESC NULLS LAST
        """
    )
    return [dict(r) for r in rows]


async def get_chat_by_id(
    conn: asyncpg.Connection,
    chat_id: str,
) -> dict[str, Any] | None:
    """Fetch a single chat's metadata (RLS scoped)."""
    row = await conn.fetchrow(
        """
        SELECT
            id::text,
            name,
            participant_count,
            message_count,
            first_message_at,
            last_message_at
        FROM public.chats
        WHERE id = $1::uuid
        """,
        chat_id,
    )
    return dict(row) if row else None

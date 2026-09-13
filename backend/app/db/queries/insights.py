import asyncpg
import json
from typing import Dict, Any, List, Optional

async def get_cached_insight(
    conn: asyncpg.Connection,
    chat_id: str,
    metric_type: str
) -> Optional[Dict[str, Any]]:
    """
    Fetch a cached insight from analysis_cache table.
    """
    row = await conn.fetchrow(
        """
        SELECT data
        FROM public.analysis_cache
        WHERE chat_id = $1::uuid
          AND metric_type = $2
        ORDER BY computed_at DESC
        LIMIT 1
        """,
        chat_id,
        metric_type
    )
    return dict(row["data"]) if row else None


async def set_cached_insight(
    conn: asyncpg.Connection,
    user_id: str,
    chat_id: str,
    metric_type: str,
    data: Dict[str, Any]
) -> None:
    """
    Save an insight to analysis_cache table.
    """
    await conn.execute(
        """
        INSERT INTO public.analysis_cache (user_id, chat_id, metric_type, data)
        VALUES ($1, $2::uuid, $3, $4::jsonb)
        ON CONFLICT DO NOTHING
        """,
        user_id,
        chat_id,
        metric_type,
        json.dumps(data)
    )

async def get_longest_silence(
    conn: asyncpg.Connection,
    chat_id: str
) -> Optional[Dict[str, Any]]:
    """
    Finds the longest gap between messages in the chat.
    """
    row = await conn.fetchrow(
        """
        WITH gaps AS (
            SELECT 
                m.id as end_msg_id,
                m.sender_name as end_sender,
                m.timestamp as end_time,
                m.content as end_content,
                LAG(m.id) OVER (ORDER BY m.timestamp) as start_msg_id,
                LAG(m.sender_name) OVER (ORDER BY m.timestamp) as start_sender,
                LAG(m.timestamp) OVER (ORDER BY m.timestamp) as start_time,
                LAG(m.content) OVER (ORDER BY m.timestamp) as start_content,
                m.timestamp - LAG(m.timestamp) OVER (ORDER BY m.timestamp) as gap
            FROM public.messages m
            WHERE m.chat_id = $1::uuid
              AND m.is_system_msg = FALSE
        )
        SELECT *
        FROM gaps
        WHERE gap IS NOT NULL
        ORDER BY gap DESC
        LIMIT 1
        """,
        chat_id
    )
    
    if row:
        return {
            "start_time": row["start_time"].isoformat(),
            "end_time": row["end_time"].isoformat(),
            "start_sender": row["start_sender"],
            "end_sender": row["end_sender"],
            "start_content": row["start_content"],
            "end_content": row["end_content"],
            "gap_seconds": row["gap"].total_seconds()
        }
    return None


async def get_most_romantic_exchange(
    conn: asyncpg.Connection,
    chat_id: str
) -> Optional[Dict[str, Any]]:
    """
    Finds the highest scored Romantic message and its immediate context.
    """
    row = await conn.fetchrow(
        """
        SELECT 
            m.id::text, m.sender_name, m.content, m.timestamp, e.score
        FROM public.emotion_labels e
        JOIN public.messages m ON e.message_id = m.id
        WHERE m.chat_id = $1::uuid
          AND e.emotion = 'Romantic'
        ORDER BY e.score DESC
        LIMIT 1
        """,
        chat_id
    )
    
    if row:
        return {
            "message_id": row["id"],
            "sender_name": row["sender_name"],
            "content": row["content"],
            "timestamp": row["timestamp"].isoformat(),
            "score": float(row["score"])
        }
    return None

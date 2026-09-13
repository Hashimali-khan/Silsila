import asyncpg
from typing import List, Dict, Any

async def insert_emotion_labels(
    conn: asyncpg.Connection,
    user_id: str,
    labels: List[Dict[str, Any]]
) -> None:
    """
    Bulk insert emotion labels.
    labels is a list of dicts with: message_id, emotion, score
    """
    if not labels:
        return
        
    query = """
        INSERT INTO public.emotion_labels (user_id, message_id, emotion, score)
        VALUES ($1, $2::uuid, $3, $4)
        ON CONFLICT DO NOTHING
    """
    
    # Format for executemany
    values = [
        (user_id, label["message_id"], label["emotion"], float(label["score"]))
        for label in labels
    ]
    
    await conn.executemany(query, values)


async def get_unprocessed_messages_for_sentiment(
    conn: asyncpg.Connection,
    chat_id: str,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Fetch messages from a chat that don't have an emotion label yet.
    """
    rows = await conn.fetch(
        """
        SELECT m.id::text, m.sender_name, m.content
        FROM public.messages m
        LEFT JOIN public.emotion_labels e ON m.id = e.message_id
        WHERE m.chat_id = $1::uuid
          AND m.is_system_msg = FALSE
          AND m.is_media = FALSE
          AND e.id IS NULL
        ORDER BY m.timestamp ASC
        LIMIT $2
        """,
        chat_id,
        limit
    )
    return [dict(r) for r in rows]

async def get_emotion_trajectory(
    conn: asyncpg.Connection,
    chat_id: str,
    interval: str = "1 day"
) -> List[Dict[str, Any]]:
    """
    Get aggregated emotion scores over time for a chat.
    This groups by time interval and returns the dominant emotion and average scores.
    """
    rows = await conn.fetch(
        """
        WITH ranked_emotions AS (
            SELECT 
                date_trunc('day', m.timestamp AT TIME ZONE 'UTC') as date,
                e.emotion,
                COUNT(*) as count,
                AVG(e.score) as avg_score,
                ROW_NUMBER() OVER (
                    PARTITION BY date_trunc('day', m.timestamp AT TIME ZONE 'UTC') 
                    ORDER BY COUNT(*) DESC
                ) as rank
            FROM public.emotion_labels e
            JOIN public.messages m ON e.message_id = m.id
            WHERE m.chat_id = $1::uuid
            GROUP BY date_trunc('day', m.timestamp AT TIME ZONE 'UTC'), e.emotion
        )
        SELECT date, emotion as dominant_emotion, avg_score
        FROM ranked_emotions
        WHERE rank = 1
        ORDER BY date ASC
        """,
        chat_id
    )
    
    return [
        {
            "date": r["date"].isoformat(),
            "dominant_emotion": r["dominant_emotion"],
            "avg_score": float(r["avg_score"])
        }
        for r in rows
    ]

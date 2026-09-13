import asyncpg
import json
from typing import List, Dict, Any

async def insert_events(
    conn: asyncpg.Connection,
    user_id: str,
    chat_id: str,
    events: List[Dict[str, Any]]
) -> None:
    """
    Bulk insert detected events for a chat.
    events is a list of dicts: type, description, detected_at, evidence, people_ids, confidence
    """
    if not events:
        return
        
    query = """
        INSERT INTO public.events 
        (user_id, chat_id, type, description, detected_at, evidence, people_ids, confidence)
        VALUES ($1, $2::uuid, $3, $4, $5, $6::jsonb, $7::uuid[], $8)
    """
    
    values = []
    for e in events:
        values.append((
            user_id,
            chat_id,
            e["type"],
            e.get("description", ""),
            e["detected_at"],
            json.dumps(e.get("evidence", [])),
            e.get("people_ids", []),
            float(e.get("confidence", 0.0))
        ))
        
    await conn.executemany(query, values)


async def get_events(
    conn: asyncpg.Connection,
    chat_id: str
) -> List[Dict[str, Any]]:
    """
    Fetch all events for a given chat, ordered by timestamp.
    """
    rows = await conn.fetch(
        """
        SELECT 
            id::text, 
            type, 
            description, 
            detected_at, 
            evidence, 
            people_ids, 
            confidence
        FROM public.events
        WHERE chat_id = $1::uuid
        ORDER BY detected_at ASC
        """,
        chat_id
    )
    
    result = []
    for r in rows:
        d = dict(r)
        d["detected_at"] = d["detected_at"].isoformat() if d["detected_at"] else None
        # evidence is already returned as a dict/list because of jsonb in asyncpg
        if isinstance(d["evidence"], str):
            d["evidence"] = json.loads(d["evidence"])
        # convert UUIDs in people_ids to strings
        d["people_ids"] = [str(pid) for pid in d["people_ids"]] if d["people_ids"] else []
        result.append(d)
        
    return result

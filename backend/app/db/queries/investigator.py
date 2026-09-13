import asyncpg
from typing import List, Dict, Any, Tuple

async def get_person_id_by_name(
    conn: asyncpg.Connection,
    user_id: str,
    name: str
) -> str | None:
    """Finds a person ID matching a given name or alias using fuzzy search."""
    row = await conn.fetchrow(
        """
        SELECT p.id 
        FROM public.aliases a
        JOIN public.people p ON a.person_id = p.id
        WHERE a.user_id = $1
        ORDER BY similarity(lower(a.alias), lower($2)) DESC
        LIMIT 1
        """,
        user_id, name
    )
    return str(row["id"]) if row else None


async def get_connections_for_person(
    conn: asyncpg.Connection,
    user_id: str,
    person_id: str,
    chat_id: str
) -> List[Dict[str, Any]]:
    """
    Gets 1st degree connections for a person in a specific chat.
    Reads from the people.profile JSONB field, or joins with threads.
    """
    rows = await conn.fetch(
        """
        WITH their_threads AS (
            SELECT mt.thread_id 
            FROM public.message_threads mt
            JOIN public.messages m ON mt.message_id = m.id
            WHERE m.person_id = $1::uuid AND m.chat_id = $2::uuid
        )
        SELECT 
            p.canonical_name,
            count(DISTINCT mt.thread_id) as interaction_count
        FROM public.message_threads mt
        JOIN public.messages m ON mt.message_id = m.id
        JOIN public.people p ON m.person_id = p.id
        WHERE mt.thread_id IN (SELECT thread_id FROM their_threads)
          AND p.id != $1::uuid
          AND p.user_id = $3
        GROUP BY p.canonical_name
        ORDER BY interaction_count DESC
        LIMIT 10
        """,
        person_id, chat_id, user_id
    )
    
    return [
        {
            "name": r["canonical_name"],
            "interaction_count": r["interaction_count"]
        }
        for r in rows
    ]


async def get_events_for_persons(
    conn: asyncpg.Connection,
    user_id: str,
    chat_id: str,
    person_ids: List[str]
) -> List[Dict[str, Any]]:
    """
    Fetch events that potentially involve any of the listed person IDs.
    Since events might not always have people_ids perfectly mapped, we fetch all events
    for the chat and filter/return the most relevant ones (recent or highly confident).
    """
    rows = await conn.fetch(
        """
        SELECT id::text, type, description, detected_at, evidence, people_ids, confidence
        FROM public.events
        WHERE chat_id = $1::uuid 
        ORDER BY detected_at ASC
        """,
        chat_id
    )
    
    # In a full implementation, we would filter by `person_ids` overlapping `people_ids`
    # However, Phase 4's event_detector didn't populate people_ids perfectly (relied on sender_names).
    # So we return all events for the chat to let the LLM filter contextually.
    
    import json
    result = []
    for r in rows:
        d = dict(r)
        d["detected_at"] = d["detected_at"].isoformat() if d["detected_at"] else None
        if isinstance(d["evidence"], str):
            d["evidence"] = json.loads(d["evidence"])
        d["people_ids"] = [str(pid) for pid in d["people_ids"]] if d["people_ids"] else []
        result.append(d)
        
    return result

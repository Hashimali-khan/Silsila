import logging
from typing import Dict, Any, List
import asyncpg
import json

logger = logging.getLogger(__name__)

async def build_relationship_graph(pool: asyncpg.Pool, user_id: str, chat_id: str) -> Dict[str, Any]:
    """
    Builds a social graph (nodes and edges) for a specific chat.
    Nodes: people (with their generated profile summaries).
    Edges: relationships (based on thread co-occurrence).
    """
    async with pool.acquire() as conn:
        # 1. Fetch all people in this chat who have a generated profile in analysis_cache
        # Actually, let's fetch all people in this chat, and left join their profile
        # Since we don't have a direct link between chat and person in the people table (it's per user),
        # we can find people who have messages in this chat.
        people_records = await conn.fetch(
            """
            SELECT DISTINCT p.id, p.canonical_name, ac.data as profile
            FROM public.people p
            JOIN public.messages m ON p.id = m.person_id
            LEFT JOIN public.analysis_cache ac ON p.id::text = ac.metric_type AND ac.chat_id = $2 AND ac.user_id = $1
            WHERE m.chat_id = $2 AND p.user_id = $1
            """,
            user_id, chat_id
        )

        nodes = []
        person_ids = []
        for r in people_records:
            person_ids.append(r["id"])
            
            profile_data = {}
            if r["profile"]:
                try:
                    profile_data = json.loads(r["profile"])
                except:
                    pass
                    
            nodes.append({
                "id": r["id"],
                "label": r["canonical_name"],
                "profile": profile_data
            })
            
        # 2. Build edges based on thread co-occurrence
        # An edge exists between person A and person B if they both participated in the same thread.
        # We can weigh the edge by the number of threads they co-occurred in.
        edges = []
        
        co_occurrence = await conn.fetch(
            """
            WITH ThreadParticipants AS (
                SELECT mt.thread_id, m.person_id
                FROM public.message_threads mt
                JOIN public.messages m ON mt.message_id = m.id
                WHERE m.chat_id = $2 AND m.user_id = $1
                GROUP BY mt.thread_id, m.person_id
            )
            SELECT t1.person_id as p1, t2.person_id as p2, COUNT(*) as weight
            FROM ThreadParticipants t1
            JOIN ThreadParticipants t2 ON t1.thread_id = t2.thread_id AND t1.person_id < t2.person_id
            GROUP BY t1.person_id, t2.person_id
            HAVING COUNT(*) > 0
            """,
            user_id, chat_id
        )
        
        for r in co_occurrence:
            edges.append({
                "source": r["p1"],
                "target": r["p2"],
                "weight": r["weight"]
            })
            
        return {
            "nodes": nodes,
            "edges": edges
        }

"""chunk_enricher.py — Entity Backfill Service

After entity extraction and coreference resolution have written rows into
`entity_mentions`, this service does one job:

For each chunk → look up which entity_mentions fall within that chunk's
message_ids → collect distinct person_ids → write them to:
  1. `message_chunks.entity_ids` in Postgres
  2. Qdrant point payload `entity_ids`

No LLM involved. Pure SQL join + Qdrant set_payload.
This is what makes entity-filtered hybrid search actually work.
"""

import logging
from typing import List, Dict, Any
import asyncpg

from app.services.qdrant_client import qdrant_service

logger = logging.getLogger(__name__)


async def enrich_chunks_with_entities(
    conn: asyncpg.Connection,
    user_id: str,
    chat_id: str,
    chunks: List[Dict[str, Any]],
) -> None:
    """
    Backfills entity_ids onto message_chunks rows and Qdrant point payloads.

    Args:
        conn: An asyncpg connection with RLS already set.
        user_id: The user's ID (used for logging).
        chat_id: The chat being enriched.
        chunks: List of chunk dicts with keys `_db_id` and `message_ids`.
    """
    if not chunks:
        return

    enriched_count = 0
    qdrant_updates: List[tuple[str, List[str]]] = []  # (point_id, [person_id, ...])

    for chunk in chunks:
        chunk_id = chunk.get("_db_id")
        message_ids = chunk.get("message_ids", [])

        if not chunk_id or not message_ids:
            continue

        # Find all distinct person_ids mentioned in any message within this chunk
        # entity_mentions.user_id is denormalized so this is a direct indexed lookup
        rows = await conn.fetch(
            """
            SELECT DISTINCT em.person_id
            FROM public.entity_mentions em
            WHERE em.user_id = $1
              AND em.message_id = ANY($2::uuid[])
            """,
            user_id,
            [str(mid) for mid in message_ids],
        )

        if not rows:
            continue

        entity_ids = [str(r["person_id"]) for r in rows]

        # 1. Update Postgres message_chunks
        await conn.execute(
            """
            UPDATE public.message_chunks
            SET entity_ids = $2::uuid[]
            WHERE id = $1::uuid
            """,
            chunk_id,
            entity_ids,
        )

        # Collect for batch Qdrant update
        qdrant_updates.append((chunk_id, entity_ids))
        enriched_count += 1

    # 2. Update Qdrant payloads in bulk
    if qdrant_updates and qdrant_service.client:
        try:
            from qdrant_client.models import PointIdsList
            for point_id, entity_ids in qdrant_updates:
                await qdrant_service.client.set_payload(
                    collection_name=qdrant_service.collection_name,
                    payload={"entity_ids": entity_ids},
                    points=PointIdsList(points=[point_id]),
                )
        except Exception as e:
            # Non-fatal: Postgres is the source of truth; Qdrant payload is a cache
            logger.warning(
                "Failed to update Qdrant entity_ids payload for chat %s: %s — "
                "Postgres entity_ids are still correct and will be used for fallback.",
                chat_id, e
            )

    logger.info(
        "Chunk enrichment complete for chat %s: enriched %d/%d chunks with entity_ids",
        chat_id, enriched_count, len(chunks),
    )

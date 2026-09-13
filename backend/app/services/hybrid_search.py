import logging
from typing import List, Dict, Any, Optional

from qdrant_client.models import (
    Prefetch,
    FusionQuery,
    Fusion,
    Filter,
    FieldCondition,
    MatchValue,
    SparseVector
)

from app.services.qdrant_client import qdrant_service
from app.services.embedding import VoyageAIClient

logger = logging.getLogger(__name__)

async def hybrid_search(
    user_id: str,
    chat_id: str,
    query_text: str,
    limit: int = 10,
    person_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Performs a hybrid search (Dense + Sparse/BM25) with server-side RRF fusion.
    """
    if not qdrant_service.client:
        logger.warning("Qdrant client not initialized, skipping search.")
        return []

    # 1. Generate dense embedding for the query
    voyage_client = VoyageAIClient()
    try:
        embeddings, _ = await voyage_client.embed_batch([query_text])
        dense_query = embeddings[0]
    except Exception as e:
        logger.error(f"Failed to embed query: {e}")
        return []

    # 2. Generate sparse embedding for the query
    sparse_query: SparseVector = qdrant_service._generate_bm25_sparse_vector(query_text)

    # 3. Build filters (user_id and chat_id are mandatory)
    must_conditions = [
        FieldCondition(key="user_id", match=MatchValue(value=user_id)),
        FieldCondition(key="chat_id", match=MatchValue(value=chat_id))
    ]

    # If person_id is provided, we can filter by entity_id (added in Phase 3)
    if person_id:
        must_conditions.append(
            FieldCondition(key="entity_ids", match=MatchValue(value=person_id))
        )

    query_filter = Filter(must=must_conditions)

    # 4. Perform Qdrant query with Prefetch and RRF
    try:
        results = await qdrant_service.client.query_points(
            collection_name=qdrant_service.collection_name,
            prefetch=[
                Prefetch(
                    query=sparse_query,
                    using="sparse",
                    limit=limit * 2,
                    filter=query_filter
                ),
                Prefetch(
                    query=dense_query,
                    using="dense",
                    limit=limit * 2,
                    filter=query_filter
                )
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=limit,
            with_payload=True
        )

        # 5. Format results
        formatted_results = []
        for point in results.points:
            formatted_results.append({
                "chunk_id": str(point.id),
                "score": point.score,
                "payload": point.payload
            })

        return formatted_results

    except Exception as e:
        logger.error(f"Hybrid search failed: {e}")
        return []

import logging
import uuid
from typing import List, Dict, Any, Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    PointStruct,
    SparseVectorParams,
    SparseIndexParams,
    SparseVector
)

from app.config import settings
from app.services.privacy import privacy_service

logger = logging.getLogger(__name__)

class QdrantService:
    def __init__(self):
        self.url = getattr(settings, "QDRANT_URL", None)
        self.api_key = getattr(settings, "QDRANT_API_KEY", None)
        self.collection_name = getattr(settings, "QDRANT_COLLECTION", "silsila_chunks")
        self.dim = getattr(settings, "VOYAGE_EMBEDDING_DIM", 1024)
        
        if not self.url or not self.api_key:
            raise ValueError("QDRANT_URL or QDRANT_API_KEY not set. Vector operations will fail.")
        self.client = AsyncQdrantClient(url=self.url, api_key=self.api_key)

    async def ensure_collection(self):
        """Creates the collection if it doesn't exist, with both dense and sparse vectors."""
        if not self.client:
            return
            
        try:
            exists = await self.client.collection_exists(self.collection_name)
            if not exists:
                logger.info(f"Creating Qdrant collection: {self.collection_name}")
                await self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config={
                        "dense": VectorParams(size=self.dim, distance=Distance.COSINE)
                    },
                    sparse_vectors_config={
                        "sparse": SparseVectorParams(
                            index=SparseIndexParams(
                                on_disk=False,
                            )
                        )
                    }
                )
                logger.info(f"Collection {self.collection_name} created successfully.")
        except Exception as e:
            logger.error(f"Error ensuring Qdrant collection: {e}")
            raise

    def _apply_privacy_noise(self, vector: List[float]) -> List[float]:
        """
        Applies SPARSE differential privacy noise. 
        """
        return privacy_service.apply_noise(vector)

    def _generate_bm25_sparse_vector(self, text: str) -> SparseVector:
        """
        Generates a dummy sparse vector for BM25.
        In a real scenario, this would use a tokenizer (like fastembed) to generate BM25 indices and weights.
        For now, we generate a basic sparse vector based on word counts.
        """
        from collections import Counter
        import hashlib
        
        # Very basic tokenizer for BM25
        words = text.lower().split()
        counts = Counter(words)
        
        indices = []
        values = []
        for word, count in counts.items():
            # hash word to index
            idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % 1000000
            if idx not in indices:
                indices.append(idx)
                values.append(float(count))
                
        return SparseVector(indices=indices, values=values)

    async def batch_upsert(self, chunks: List[Dict[str, Any]], embeddings: List[List[float]]):
        """
        Upserts a batch of message chunks with dense and sparse vectors into Qdrant.
        `chunks` should contain payload data and a unique `_db_id` (used as Qdrant point ID).
        """
        if not self.client:
            raise RuntimeError("Qdrant client not initialized.")
            
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks and embeddings must match.")
            
        points = []
        for chunk, emb in zip(chunks, embeddings):
            point_id = chunk["_db_id"]
            
            # Apply DP noise
            noised_emb = self._apply_privacy_noise(emb)
            
            # Generate sparse vector
            sparse_vec = self._generate_bm25_sparse_vector(chunk["content"])
            
            payload = {
                "user_id": chunk["user_id"],
                "chat_id": chunk["chat_id"],
                "thread_id": chunk.get("thread_id"),
                "message_ids": chunk["message_ids"],
                "content": chunk["content"],
                "start_time": chunk["start_time"].isoformat() if chunk.get("start_time") else None,
                "end_time": chunk["end_time"].isoformat() if chunk.get("end_time") else None,
                "entity_ids": chunk.get("entity_ids", [])  # For Phase 3
            }
            
            points.append(
                PointStruct(
                    id=point_id,
                    vector={
                        "dense": noised_emb,
                        "sparse": sparse_vec
                    },
                    payload=payload
                )
            )
            
        if points:
            await self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            logger.info(f"Upserted {len(points)} chunks into Qdrant.")

qdrant_service = QdrantService()

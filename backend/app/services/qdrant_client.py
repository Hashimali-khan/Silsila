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
    SparseVector,
    Filter,
    FieldCondition,
    MatchValue,
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
        
        self._client = None

    @property
    def client(self) -> Optional[AsyncQdrantClient]:
        if self._client is None and self.url and self.api_key:
            self._client = AsyncQdrantClient(
                url=self.url,
                api_key=self.api_key,
                timeout=5.0,
                check_compatibility=False
            )
        return self._client

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

    @property
    def sparse_model(self):
        if not hasattr(self, '_sparse_model'):
            from fastembed import SparseTextEmbedding
            logger.info("Initializing FastEmbed SparseTextEmbedding (Qdrant/bm25)")
            self._sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
        return self._sparse_model

    async def batch_upsert(self, chunks: List[Dict[str, Any]], embeddings: List[List[float]]):
        """
        Upserts a batch of message chunks with dense and sparse vectors into Qdrant.
        `chunks` should contain payload data and a unique `_db_id` (used as Qdrant point ID).
        """
        if not self.client:
            raise RuntimeError("Qdrant client not initialized.")
            
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks and embeddings must match.")
            
        contents = [chunk["content"] for chunk in chunks]
        sparse_embeddings = list(self.sparse_model.embed(contents))
            
        points = []
        for chunk, emb, sparse_emb in zip(chunks, embeddings, sparse_embeddings):
            point_id = chunk["_db_id"]
            
            # Apply DP noise
            noised_emb = self._apply_privacy_noise(emb)
            
            # Generate sparse vector
            sparse_vec = SparseVector(
                indices=sparse_emb.indices.tolist() if hasattr(sparse_emb.indices, 'tolist') else list(sparse_emb.indices),
                values=sparse_emb.values.tolist() if hasattr(sparse_emb.values, 'tolist') else list(sparse_emb.values)
            )
            
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

    async def get_existing_point_ids(self, point_ids: List[str]) -> List[str]:
        """Returns a list of point IDs that already exist in the collection."""
        if not self.client or not point_ids:
            return []
        try:
            points = await self.client.retrieve(
                collection_name=self.collection_name,
                ids=point_ids,
                with_payload=False,
                with_vectors=False
            )
            return [str(p.id) for p in points]
        except Exception as e:
            logger.warning(f"Failed to retrieve existing Qdrant points: {e}")
            return []

    async def delete_by_chat_id(self, chat_id: str):
        """Deletes all vector points associated with a specific chat_id."""
        if not self.client:
            return
        try:
            await self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="chat_id",
                            match=MatchValue(value=chat_id)
                        )
                    ]
                )
            )
            logger.info(f"Deleted vector points for chat {chat_id} from Qdrant.")
        except Exception as e:
            logger.warning(f"Failed to delete Qdrant points for chat {chat_id}: {e}")

qdrant_service = QdrantService()

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from qdrant_client.http.models import PointStruct
from app.services.qdrant_client import QdrantService

@pytest.mark.asyncio
async def test_ensure_collection(mock_qdrant_service):
    # Setup mock to say collection doesn't exist
    mock_qdrant_service.client.collection_exists = AsyncMock(return_value=False)
    mock_qdrant_service.client.create_collection = AsyncMock()
    
    # We call ensure_collection on the real class but with patched client
    service = QdrantService()
    service.client = mock_qdrant_service.client
    
    await service.ensure_collection()
    
    # Verify collection was created with correct params
    service.client.create_collection.assert_called_once()
    kwargs = service.client.create_collection.call_args.kwargs
    assert kwargs["collection_name"] == "silsila_chunks"
    
    # Verify vector configs (dense and sparse)
    vectors_config = kwargs["vectors_config"]
    assert "dense" in vectors_config
    assert vectors_config["dense"].size == 1024
    
    sparse_vectors_config = kwargs["sparse_vectors_config"]
    assert "sparse" in sparse_vectors_config

@pytest.mark.asyncio
async def test_ensure_collection_exists(mock_qdrant_service):
    # Setup mock to say collection exists
    mock_qdrant_service.client.collection_exists = AsyncMock(return_value=True)
    mock_qdrant_service.client.create_collection = AsyncMock()
    
    service = QdrantService()
    service.client = mock_qdrant_service.client
    
    await service.ensure_collection()
    
    # Verify create_collection was NOT called
    service.client.create_collection.assert_not_called()

@pytest.mark.asyncio
async def test_batch_upsert(mock_qdrant_service):
    service = QdrantService()
    service.client = mock_qdrant_service.client
    service.client.upsert = AsyncMock()
    
    chunks = [
        {
            "_db_id": "uuid_1",
            "id": "chunk_1",
            "chat_id": "chat_1",
            "user_id": "user_1",
            "content": "hello world",
            "thread_id": "thread_1",
            "start_message_id": "msg_1",
            "end_message_id": "msg_2",
            "message_ids": ["msg_1", "msg_2"]
        }
    ]
    dense_embeddings = [[0.1, 0.2, 0.3]]
    
    await service.batch_upsert(chunks, dense_embeddings)
    
    service.client.upsert.assert_called_once()
    kwargs = service.client.upsert.call_args.kwargs
    
    assert kwargs["collection_name"] == "silsila_chunks"
    points = kwargs["points"]
    assert len(points) == 1
    
    point = points[0]
    assert point.id == "uuid_1"
    assert point.payload["chat_id"] == "chat_1"
    assert point.payload["user_id"] == "user_1"
    assert "dense" in point.vector
    assert "sparse" in point.vector

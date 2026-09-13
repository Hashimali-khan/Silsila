import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.fixture
def mock_voyage_client():
    with patch("app.services.embedding.VoyageAIClient", autospec=True) as MockClient:
        instance = MockClient.return_value
        instance.embed_batch = AsyncMock(return_value=([[0.1, 0.2, 0.3]], 10))
        yield instance

@pytest.fixture
def mock_qdrant_service():
    with patch("app.services.qdrant_client.qdrant_service") as mock_service:
        mock_service.client = MagicMock()
        mock_service.ensure_collection = AsyncMock()
        mock_service.batch_upsert = AsyncMock()
        mock_service.collection_name = "test_collection"
        
        # for query_points mock
        mock_point = MagicMock()
        mock_point.id = "chunk_1"
        mock_point.score = 0.95
        mock_point.payload = {"message_ids": ["msg1", "msg2"], "thread_id": "thread_1"}
        
        mock_result = MagicMock()
        mock_result.points = [mock_point]
        mock_service.client.query_points = AsyncMock(return_value=mock_result)
        
        # mock generating sparse vector
        mock_sparse = MagicMock()
        mock_service._generate_bm25_sparse_vector = MagicMock(return_value=mock_sparse)
        
        yield mock_service

@pytest.fixture
def mock_llm_service():
    with patch("app.services.llm.llm_service") as mock_service:
        async def mock_stream(*args, **kwargs):
            yield '{"type": "token", "content": "mock"}'
            yield '{"type": "token", "content": " answer"}'
        
        mock_service.stream_answer = mock_stream
        yield mock_service

import pytest
from unittest.mock import AsyncMock, patch
from app.services.hybrid_search import hybrid_search

@pytest.mark.asyncio
async def test_hybrid_search(mock_voyage_client, mock_qdrant_service):
    # mock_qdrant_service is already configured to return a mock query_points result
    
    with patch("app.services.hybrid_search.VoyageAIClient", return_value=mock_voyage_client), \
         patch("app.services.hybrid_search.qdrant_service", mock_qdrant_service):
         
         results = await hybrid_search(
             user_id="user_1",
             chat_id="chat_1",
             query_text="hello world",
             limit=5
         )
         
         # Check voyage embed was called
         mock_voyage_client.embed_batch.assert_called_once()
         assert mock_voyage_client.embed_batch.call_args.args[0] == ["hello world"]
         
         # Check qdrant query_points was called
         mock_qdrant_service.client.query_points.assert_called_once()
         kwargs = mock_qdrant_service.client.query_points.call_args.kwargs
         
         assert kwargs["collection_name"] == "test_collection"
         assert kwargs["limit"] == 5
         
         # verify prefetch is present for hybrid search
         assert "prefetch" in kwargs
         assert len(kwargs["prefetch"]) == 2 # dense and sparse
         
         # verify output mapping
         assert len(results) == 1
         assert results[0]["chunk_id"] == "chunk_1"
         assert results[0]["score"] == 0.95
         assert results[0]["payload"]["message_ids"] == ["msg1", "msg2"]

@pytest.mark.asyncio
async def test_hybrid_search_with_person_filter(mock_voyage_client, mock_qdrant_service):
    # Reset mocks from previous test
    mock_voyage_client.embed_batch.reset_mock()
    mock_qdrant_service.client.query_points.reset_mock()
    
    with patch("app.services.hybrid_search.VoyageAIClient", return_value=mock_voyage_client), \
         patch("app.services.hybrid_search.qdrant_service", mock_qdrant_service):
         
         results = await hybrid_search(
             user_id="user_1",
             chat_id="chat_1",
             query_text="hello world",
             person_id="person_1",
             limit=5
         )
         
         # Check qdrant query_points was called
         mock_qdrant_service.client.query_points.assert_called_once()
         kwargs = mock_qdrant_service.client.query_points.call_args.kwargs
         
         prefetch = kwargs["prefetch"]
         
         # The filter should be present in both dense and sparse prefetches
         for p in prefetch:
             # Ensure the filter has the person_id match
             # we just check that query_filter is not None
             assert p.filter is not None

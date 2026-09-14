import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.embedding import VoyageAIClient, record_token_usage, EmbeddingError

@pytest.mark.asyncio
async def test_embed_batch_success():
    with patch("app.services.embedding.voyageai.AsyncClient") as mock_client:
        mock_instance = mock_client.return_value
        mock_response = MagicMock()
        mock_response.embeddings = [[0.1, 0.2, 0.3]]
        mock_response.total_tokens = 10
        mock_instance.embed = AsyncMock(return_value=mock_response)
        
        with patch("app.services.embedding.settings") as mock_settings:
            mock_settings.VOYAGE_API_KEY = "test_key"
            client = VoyageAIClient()
            client.client = mock_instance
        embeddings, tokens = await client.embed_batch(["test text 1", "test text 2"])
        
        assert embeddings == [[0.1, 0.2, 0.3]]
        assert tokens == 10

@pytest.mark.asyncio
async def test_embed_batch_empty():
    with patch("app.services.embedding.voyageai.AsyncClient"):
        with patch("app.services.embedding.settings") as mock_settings:
            mock_settings.VOYAGE_API_KEY = "test_key"
            client = VoyageAIClient()
            client.client = MagicMock()
        embeddings, tokens = await client.embed_batch([])
        assert embeddings == []
        assert tokens == 0

@pytest.mark.asyncio
async def test_embed_batch_truncation():
    with patch("app.services.embedding.voyageai.AsyncClient") as mock_client:
        mock_instance = mock_client.return_value
        mock_response = MagicMock()
        mock_response.embeddings = [[0.1] for _ in range(128)]
        mock_response.total_tokens = 10
        mock_instance.embed = AsyncMock(return_value=mock_response)
        
        with patch("app.services.embedding.settings") as mock_settings:
            mock_settings.VOYAGE_API_KEY = "test_key"
            client = VoyageAIClient()
            client.client = mock_instance
        texts = ["text"] * 150 # Exceeds BATCH_SIZE (128)
        
        with patch("app.services.embedding.logger") as mock_logger:
            await client.embed_batch(texts)
            mock_logger.warning.assert_called_once()
            # Mock client should be called with 128 texts
            args, kwargs = client.client.embed.call_args
            assert len(args[0]) == 128

@pytest.mark.asyncio
async def test_record_token_usage():
    mock_conn = MagicMock()
    mock_conn.fetchrow = AsyncMock(return_value={"cumulative": 100})
    mock_conn.execute = AsyncMock()
    
    new_total = await record_token_usage(mock_conn, "user_1", "job_1", 50)
    
    assert new_total == 150
    mock_conn.execute.assert_called_once()
    
    # Test milestone alert
    mock_conn.fetchrow = AsyncMock(return_value={"cumulative": 149_999_990})
    with patch("app.services.embedding.logger") as mock_logger:
        new_total = await record_token_usage(mock_conn, "user_1", "job_1", 20)
        assert new_total == 150_000_010
        mock_logger.warning.assert_called_once()

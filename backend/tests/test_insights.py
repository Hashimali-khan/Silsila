import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.insights import insights_service

@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__.return_value = conn
    pool.acquire.return_value = ctx
    return pool, conn

@pytest.fixture
def mock_get_pool(mock_pool):
    with patch('app.services.insights.get_pool', return_value=mock_pool[0]) as mock:
        yield mock

@pytest.fixture
def mock_llm_service():
    with patch('app.services.insights.llm_service') as mock_llm:
        mock_llm.generate_json = AsyncMock()
        yield mock_llm

@pytest.mark.asyncio
@patch('app.services.insights.get_cached_insight')
@patch('app.services.insights.get_longest_silence')
@patch('app.services.insights.get_most_romantic_exchange')
@patch('app.services.insights.set_cached_insight')
async def test_get_memory_cards_not_cached(
    mock_set_cache, mock_get_romantic, mock_get_longest, mock_get_cache, mock_get_pool, mock_pool
):
    user_id = "user1"
    chat_id = "chat1"
    pool, conn = mock_pool
    
    # Setup mock returns
    mock_get_cache.return_value = None
    mock_get_longest.return_value = {"gap_seconds": 1000}
    mock_get_romantic.return_value = {"score": 0.9}
    
    # Mock the first message query
    from datetime import datetime
    conn.fetchrow.return_value = {"sender_name": "A", "content": "hi", "timestamp": datetime(2026, 1, 1, 12, 0)}
    
    cards = await insights_service.get_memory_cards(user_id, chat_id)
    
    assert cards["longest_silence"]["gap_seconds"] == 1000
    assert cards["most_romantic"]["score"] == 0.9
    assert cards["first_message"]["sender_name"] == "A"
    
    # Verify cache was set
    mock_set_cache.assert_called_once_with(conn, user_id, chat_id, "memory_cards", cards)

@pytest.mark.asyncio
@patch('app.services.insights.get_cached_insight')
async def test_get_memory_cards_cached(mock_get_cache, mock_get_pool):
    user_id = "user1"
    chat_id = "chat1"
    
    # Return from cache
    cached_data = {"longest_silence": {"gap_seconds": 500}}
    mock_get_cache.return_value = cached_data
    
    cards = await insights_service.get_memory_cards(user_id, chat_id)
    
    assert cards == cached_data

@pytest.mark.asyncio
@patch('app.services.insights.get_cached_insight')
@patch('app.services.insights.get_events')
@patch('app.services.insights.set_cached_insight')
async def test_get_story_mode_not_cached(
    mock_set_cache, mock_get_events, mock_get_cache, mock_get_pool, mock_llm_service, mock_pool
):
    user_id = "user1"
    chat_id = "chat1"
    pool, conn = mock_pool
    
    mock_get_cache.return_value = None
    mock_get_events.return_value = [{"detected_at": "2026", "type": "fight", "description": "Argument"}]
    
    mock_llm_service.generate_json.return_value = {
        "chapters": [{"title": "Chapter 1", "summary": "Start", "events": []}]
    }
    
    story = await insights_service.get_story_mode(user_id, chat_id)
    
    assert len(story["chapters"]) == 1
    assert story["chapters"][0]["title"] == "Chapter 1"
    
    mock_llm_service.generate_json.assert_called_once()
    mock_set_cache.assert_called_once()

import pytest
import io
import zipfile
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import Request

@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__.return_value = conn
    pool.acquire.return_value = ctx
    return pool, conn

@pytest.mark.asyncio
@patch('app.routers.account.get_pool')
async def test_delete_account(mock_get_pool, mock_pool):
    pool, conn = mock_pool
    mock_get_pool.return_value = pool
    
    # Needs to mock the transaction block
    tx = AsyncMock()
    conn.transaction = MagicMock()
    conn.transaction.return_value = tx
    tx.__aenter__.return_value = tx
    
    from app.routers.account import delete_account
    
    # Fake request for rate limiter (slowapi)
    request = MagicMock(spec=Request)
    
    await delete_account(request, user_id="user1")
    
    assert conn.execute.call_count >= 10
    # check that we delete from profiles
    conn.execute.assert_any_call("DELETE FROM public.profiles WHERE id = $1", "user1")

@pytest.mark.asyncio
@patch('app.routers.account.get_pool')
async def test_export_data(mock_get_pool, mock_pool):
    pool, conn = mock_pool
    mock_get_pool.return_value = pool
    
    # Mock chat existence
    conn.fetchrow.return_value = {"id": "chat1"}
    
    # Mock people and events
    conn.fetch.side_effect = [
        [{"id": "p1", "canonical_name": "Aimi", "profile": "{}"}],
        [{"type": "fight", "description": "argument", "detected_at": None, "confidence": 0.9}]
    ]
    
    from app.routers.account import export_data
    request = MagicMock(spec=Request)
    
    response = await export_data(request, chat_id="chat1", user_id="user1")
    
    # response is StreamingResponse
    # To test content, we can iterate
    body = b""
    async for chunk in response.body_iterator:
        body += chunk
        
    # Check if it's a valid ZIP
    zip_buffer = io.BytesIO(body)
    with zipfile.ZipFile(zip_buffer, "r") as zip_file:
        files = zip_file.namelist()
        assert "people.json" in files
        assert "events.json" in files

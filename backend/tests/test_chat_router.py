import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app

# Need to mock get_current_user_id and get_db_pool dependencies
@pytest.fixture
def override_dependencies():
    from app.dependencies import get_current_user_id
    from app.db.connection import get_pool
    
    async def override_get_current_user_id():
        return "user_1"
        
    from contextlib import asynccontextmanager

    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    
    @asynccontextmanager
    async def mock_acquire():
        yield mock_conn
        
    mock_pool.acquire = mock_acquire
    
    async def override_get_pool():
        return mock_pool
        
    app.dependency_overrides[get_current_user_id] = override_get_current_user_id
    app.dependency_overrides[get_pool] = override_get_pool
    
    yield mock_conn
    
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_chat_endpoint_success(override_dependencies, mock_llm_service):
    # Mock hybrid_search
    mock_hybrid_search = AsyncMock(return_value=[{"id": "chunk_1"}])
    
    # Mock build_evidence
    mock_build_evidence = AsyncMock(return_value=[{"thread_id": "thread_1", "content": "evidence"}])
    
    with patch("app.routers.chat.hybrid_search", mock_hybrid_search), \
         patch("app.routers.chat.build_evidence", mock_build_evidence), \
         patch("app.routers.chat.llm_service", mock_llm_service):
         
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/api/chat", json={
                "query_text": "hello",
                "chat_id": "chat_1"
            })
            
            assert response.status_code == 200
            
            # Since it's SSE, the response is a stream. With ASGITransport, we get the body.
            content = response.content.decode("utf-8")
            
            # The SSE format is "data: {...}\n\n"
            events = [line for line in content.split("\n") if line.startswith("data: ")]
            
            # Expected events:
            # searching
            # found 1 relevant chunks
            # analyzing
            # evidence
            # token "mock"
            # token " answer"
            # done
            
            assert len(events) >= 7
            assert "searching" in events[0]
            assert "found 1 relevant chunks" in events[1]
            assert "analyzing" in events[2]
            assert "evidence" in events[3]
            assert "mock" in events[4]
            assert " answer" in events[5]
            assert "done" in events[-1]

@pytest.mark.asyncio
async def test_chat_endpoint_no_results(override_dependencies):
    mock_hybrid_search = AsyncMock(return_value=[])
    
    with patch("app.routers.chat.hybrid_search", mock_hybrid_search):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/api/chat", json={
                "query_text": "hello",
                "chat_id": "chat_1"
            })
            
            assert response.status_code == 200
            content = response.content.decode("utf-8")
            events = [line for line in content.split("\n") if line.startswith("data: ")]
            
            assert len(events) == 3
            assert "searching" in events[0]
            assert "found 0 messages" in events[1]
            assert "error" in events[2]
            assert "Could not find any relevant messages" in events[2]

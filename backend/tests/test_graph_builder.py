import pytest
import uuid
import json
from unittest.mock import AsyncMock, MagicMock
from app.services.graph_builder import build_person_profile
from app.services.llm import llm_service

@pytest.fixture
def mock_llm_json(monkeypatch):
    async def mock_generate_json(prompt, response_schema=None):
        return {
            "summary": "Alice is a planner",
            "roles": ["planner"],
            "key_attributes": ["organized"],
            "topics_of_interest": ["trips"],
            "notable_quotes": ["Let's go!"]
        }
    monkeypatch.setattr(llm_service, "generate_json", mock_generate_json)

@pytest.mark.asyncio
async def test_build_person_profile(mock_llm_json):
    user_id = str(uuid.uuid4())
    chat_id = str(uuid.uuid4())
    person_id = str(uuid.uuid4())
    
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    
    import datetime
    # Mock person fetchrow
    # First fetchrow is the person, next is messages
    mock_conn.fetchrow.side_effect = [{"canonical_name": "Alice"}]
    mock_conn.fetch.side_effect = [[{"content": "Let us go on a trip", "timestamp": datetime.datetime.now()}]]
    
    await build_person_profile(mock_pool, user_id, person_id, chat_id)
    
    # Check that it executed an UPSERT into analysis_cache
    assert mock_conn.execute.call_count == 1
    call_args = mock_conn.execute.call_args[0]
    assert "INSERT INTO public.analysis_cache" in call_args[0]
    
    # Check that the JSON data passed in the execute contains our roles
    json_data = call_args[5] # $5 is the jsonb
    data = json.loads(json_data)
    assert data["roles"] == ["planner"]

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.investigator import investigator_service

@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__.return_value = conn
    pool.acquire.return_value = ctx
    return pool, conn

@pytest.fixture
def mock_llm_service():
    with patch('app.services.investigator.llm_service') as mock:
        mock.generate_json = AsyncMock()
        yield mock

@pytest.fixture
def mock_hybrid_search():
    with patch('app.services.investigator.hybrid_search') as mock:
        yield mock

@pytest.mark.asyncio
@patch('app.services.investigator.get_pool')
@patch('app.services.investigator.get_person_id_by_name')
@patch('app.services.investigator.get_connections_for_person')
@patch('app.services.investigator.get_events_for_persons')
async def test_investigate(
    mock_get_events,
    mock_get_conns,
    mock_get_pid,
    mock_get_pool,
    mock_hybrid_search,
    mock_llm_service,
    mock_pool
):
    pool, conn = mock_pool
    mock_get_pool.return_value = pool
    
    # 1. Mock Extraction LLM call
    def llm_side_effect(prompt, response_schema):
        if "Extract the names" in prompt:
            return {"names": ["Aimi", "Abdullah"]}
        else:
            return {
                "summary": "This is a summary of the relationship.",
                "direct_mentions": 5,
                "connections": ["Ali"],
                "timeline": [{"date": "2026-01-01", "description": "Met at a party", "message_ids": ["1"]}]
            }
            
    mock_llm_service.generate_json.side_effect = llm_side_effect
    
    # 2. Mock Graph Queries
    mock_get_pid.side_effect = ["id-aimi", "id-abdullah"]
    mock_get_conns.return_value = [{"name": "Ali", "interaction_count": 10}]
    
    # 3. Mock Events
    mock_get_events.return_value = [{"detected_at": "2026-01-01", "type": "fight", "description": "Fight"}]
    
    # 4. Mock Search
    mock_hybrid_search.return_value = [{"payload": {"content": "Hello", "message_ids": ["1"]}}]
    
    # Execute
    report = await investigator_service.investigate("user1", "chat1", "Did Aimi and Abdullah fight?")
    
    assert report["summary"] == "This is a summary of the relationship."
    assert report["direct_mentions"] == 5
    assert len(report["connections"]) == 1
    assert report["connections"][0] == "Ali"
    assert len(report["timeline"]) == 1
    
    # Verify calls
    assert mock_llm_service.generate_json.call_count == 2
    mock_hybrid_search.assert_called_once_with("user1", "chat1", "Did Aimi and Abdullah fight?", limit=10)
    assert mock_get_events.call_count == 1

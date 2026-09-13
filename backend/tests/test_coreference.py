import pytest
from unittest.mock import AsyncMock, MagicMock
import uuid
from app.services.coreference import process_extracted_entities

@pytest.mark.asyncio
async def test_process_extracted_entities():
    user_id = str(uuid.uuid4())
    chat_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    
    # Mock pool and conn
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    
    # --- Test 1: EXACT match ---
    # fetchrow returns a dict-like object (mocking existing alias)
    mock_conn.fetchrow.side_effect = [{"id": "alias1"}]
    
    entities = [{"text": "Abdullah", "label": "Person"}]
    await process_extracted_entities(mock_pool, user_id, chat_id, message_id, "Abdullah is here", entities)
    
    # Should only call fetchrow once to check exact match, and NOT execute inserts
    assert mock_conn.execute.call_count == 0
    
    # --- Test 2: FUZZY match high confidence (auto-merge) ---
    mock_conn.reset_mock()
    # First fetchrow: no exact match. Second fetchrow: fuzzy match > 0.85
    mock_conn.fetchrow.side_effect = [
        None, 
        {"person_id": "p1", "canonical_name": "Abdullah", "sim": 0.90}
    ]
    
    entities = [{"text": "Abdulah", "label": "Person"}]
    await process_extracted_entities(mock_pool, user_id, chat_id, message_id, "Abdulah is here", entities)
    
    # Should call execute to insert into aliases
    assert mock_conn.execute.call_count == 1
    call_args = mock_conn.execute.call_args[0]
    assert "INSERT INTO public.aliases" in call_args[0]
    
    # --- Test 3: LOW confidence (new person suggestion) ---
    mock_conn.reset_mock()
    # First fetchrow: no exact match. Second: fuzzy match < 0.5. Third: existing suggestion (None)
    mock_conn.fetchrow.side_effect = [
        None,
        {"person_id": "p1", "canonical_name": "Abdullah", "sim": 0.30},
        None
    ]
    
    entities = [{"text": "Zayd", "label": "Person"}]
    await process_extracted_entities(mock_pool, user_id, chat_id, message_id, "Zayd is here", entities)
    
    assert mock_conn.execute.call_count == 1
    call_args = mock_conn.execute.call_args[0]
    assert "INSERT INTO public.alias_suggestions" in call_args[0]

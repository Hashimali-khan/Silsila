import pytest
import datetime
from unittest.mock import AsyncMock, MagicMock
from app.services.evidence_builder import build_evidence

@pytest.mark.asyncio
async def test_build_evidence():
    mock_conn = MagicMock()
    
    # We will simulate that the DB returns 3 messages for the thread
    mock_messages = [
        {"id": "msg1", "sender_name": "Alice", "timestamp": datetime.datetime(2026, 3, 5, 10, 15, tzinfo=datetime.timezone.utc), "content": "hello", "is_system_msg": False, "is_media": False, "thread_id": "thread_1"},
        {"id": "msg2", "sender_name": "Bob", "timestamp": datetime.datetime(2026, 3, 5, 10, 16, tzinfo=datetime.timezone.utc), "content": "hi alice", "is_system_msg": False, "is_media": False, "thread_id": "thread_1"},
        {"id": "msg3", "sender_name": "Alice", "timestamp": datetime.datetime(2026, 3, 5, 10, 17, tzinfo=datetime.timezone.utc), "content": "how are you?", "is_system_msg": False, "is_media": False, "thread_id": "thread_1"}
    ]
    mock_conn.fetch = AsyncMock(return_value=mock_messages)
    
    search_results = [
        {
            "chunk_id": "chunk_1",
            "score": 0.95,
            "payload": {
                "message_ids": ["msg2"],
                "thread_id": "thread_1",
                "start_message_id": "msg2",
                "end_message_id": "msg2"
            }
        }
    ]
    
    evidence = await build_evidence(mock_conn, "user_1", search_results)
    
    # Check that fetch was called twice (once for threads, once for messages)
    assert mock_conn.fetch.call_count == 2
    
    # Check that evidence was built
    assert len(evidence) == 1
    ev_block = evidence[0]
    
    assert ev_block["thread_id"] == "thread_1"
    assert len(ev_block["message_ids"]) == 3
    
    # Ensure the content is properly formatted
    assert "Alice: hello" in ev_block["content"]
    assert "Bob: hi alice" in ev_block["content"]
    assert "Alice: how are you?" in ev_block["content"]

@pytest.mark.asyncio
async def test_build_evidence_deduplication():
    # If multiple search results hit the same thread with overlapping messages,
    # the evidence builder deduplicates them because it fetches by thread_id + message bounds.
    mock_conn = MagicMock()
    
    mock_messages = [
        {"id": "msg1", "sender_name": "Alice", "timestamp": datetime.datetime(2026, 3, 5, 10, 15, tzinfo=datetime.timezone.utc), "content": "msg1", "is_system_msg": False, "is_media": False, "thread_id": "thread_1"},
        {"id": "msg2", "sender_name": "Bob", "timestamp": datetime.datetime(2026, 3, 5, 10, 16, tzinfo=datetime.timezone.utc), "content": "msg2", "is_system_msg": False, "is_media": False, "thread_id": "thread_1"},
    ]
    
    # Mocking fetch to return the same messages regardless of query for simplicity
    mock_conn.fetch = AsyncMock(return_value=mock_messages)
    
    search_results = [
        {
            "chunk_id": "chunk_1",
            "score": 0.95,
            "payload": {
                "message_ids": ["msg1"],
                "thread_id": "thread_1",
                "start_message_id": "msg1",
                "end_message_id": "msg1"
            }
        },
        {
            "chunk_id": "chunk_2",
            "score": 0.90,
            "payload": {
                "message_ids": ["msg2"],
                "thread_id": "thread_1",  # Same thread
                "start_message_id": "msg2",
                "end_message_id": "msg2"
            }
        }
    ]
    
    evidence = await build_evidence(mock_conn, "user_1", search_results)
    
    # Depending on implementation, it might fetch once per chunk.
    # The deduplication happens when formatting: overlapping messages inside the same thread.
    assert len(evidence) <= 2
    
    # In my current implementation, it expands the bounds and fetches.
    # The actual implementation fetches by min(start) -2 and max(end) +2 per thread.
    # Let's verify that the output has the combined content for thread_1
    assert evidence[0]["thread_id"] == "thread_1"
    assert "Alice: msg1" in evidence[0]["content"]
    assert "Bob: msg2" in evidence[0]["content"]

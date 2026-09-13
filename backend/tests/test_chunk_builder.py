import pytest
from datetime import datetime, timezone
import uuid
from unittest.mock import AsyncMock, MagicMock
from app.services.chunk_builder import build_chunks_for_thread, process_chat_chunks

def create_dummy_message(idx: int, is_system: bool = False, is_media: bool = False):
    return {
        "_db_id": f"msg_{idx}",
        "timestamp": datetime(2026, 3, 5, 10, idx % 60, tzinfo=timezone.utc),
        "sender_name": "Alice" if idx % 2 == 0 else "Bob",
        "content": f"Message content {idx}",
        "is_system_msg": is_system,
        "is_media": is_media
    }

def test_build_chunks_sliding_window():
    # 10 messages -> chunk 1 (0-7), chunk 2 (5-9) (since step is 5)
    thread_msgs = [create_dummy_message(i) for i in range(10)]
    
    chunks = build_chunks_for_thread(thread_msgs)
    assert len(chunks) == 2
    
    # Chunk 1
    assert chunks[0]["message_count"] == 8
    assert chunks[0]["start_message_id"] == "msg_0"
    assert chunks[0]["end_message_id"] == "msg_7"
    assert len(chunks[0]["message_ids"]) == 8
    
    # Chunk 2
    assert chunks[1]["message_count"] == 5
    assert chunks[1]["start_message_id"] == "msg_5"
    assert chunks[1]["end_message_id"] == "msg_9"
    assert len(chunks[1]["message_ids"]) == 5

def test_build_chunks_skip_system_only():
    # 8 system messages
    thread_msgs = [create_dummy_message(i, is_system=True) for i in range(8)]
    chunks = build_chunks_for_thread(thread_msgs)
    assert len(chunks) == 0

def test_build_chunks_formatting():
    # Test formatting of system, media, and normal messages
    msgs = [
        create_dummy_message(0, is_system=True),
        create_dummy_message(1, is_media=True),
        create_dummy_message(2)
    ]
    chunks = build_chunks_for_thread(msgs)
    assert len(chunks) == 1
    content = chunks[0]["content"]
    
    assert "SYSTEM: Message content 0" in content
    assert "<Media omitted>" in content
    assert "Alice: Message content 2" in content

@pytest.mark.asyncio
async def test_process_chat_chunks():
    mock_conn = MagicMock()
    mock_conn.copy_records_to_table = AsyncMock()
    
    threads_msgs = [
        [create_dummy_message(i) for i in range(5)], # thread 1
        [create_dummy_message(i) for i in range(10)] # thread 2
    ]
    thread_ids = ["thread_1", "thread_2"]
    
    result = await process_chat_chunks(
        conn=mock_conn, 
        user_id="user_1", 
        chat_id="chat_1", 
        threads_msgs=threads_msgs, 
        thread_ids=thread_ids
    )
    
    # 1 chunk from thread 1, 2 chunks from thread 2 -> total 3
    assert len(result) == 3
    
    mock_conn.copy_records_to_table.assert_called_once()
    args, kwargs = mock_conn.copy_records_to_table.call_args
    assert args[0] == "message_chunks"
    assert len(kwargs["records"]) == 3

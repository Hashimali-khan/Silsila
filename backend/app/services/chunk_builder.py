import logging
import uuid
from typing import List, Dict, Any

import asyncpg

logger = logging.getLogger(__name__)

CHUNK_SIZE = 8
OVERLAP = 3

def build_chunks_for_thread(thread_msgs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Given a list of message dicts for a single thread,
    builds overlapping chunks of messages.
    Returns a list of chunk dicts.
    """
    chunks = []
    if not thread_msgs:
        return chunks

    n = len(thread_msgs)
    step = CHUNK_SIZE - OVERLAP
    if step <= 0:
        step = 1

    for i in range(0, n, step):
        chunk_msgs = thread_msgs[i : i + CHUNK_SIZE]
        
        # Skip if entirely system msgs or media
        non_skip = [m for m in chunk_msgs if not m.get("is_system_msg") and not m.get("is_media")]
        if not non_skip:
            if i + CHUNK_SIZE >= n:
                break
            continue
            
        start_msg = chunk_msgs[0]
        end_msg = chunk_msgs[-1]
        
        # Format content
        formatted_texts = []
        for m in chunk_msgs:
            if m.get("is_system_msg"):
                formatted_texts.append(f"[{m['timestamp'].strftime('%Y-%m-%d %H:%M')}] SYSTEM: {m['content']}")
            elif m.get("is_media"):
                formatted_texts.append(f"[{m['timestamp'].strftime('%Y-%m-%d %H:%M')}] {m['sender_name']}: <Media omitted>")
            else:
                formatted_texts.append(f"[{m['timestamp'].strftime('%Y-%m-%d %H:%M')}] {m['sender_name']}: {m['content']}")
                
        content = "\n".join(formatted_texts)
        
        chunks.append({
            "_db_id": str(uuid.uuid4()),
            "start_message_id": start_msg["_db_id"],
            "end_message_id": end_msg["_db_id"],
            "start_time": start_msg["timestamp"],
            "end_time": end_msg["timestamp"],
            "content": content,
            "message_ids": [m["_db_id"] for m in chunk_msgs if m.get("_db_id")],
            "message_count": len(chunk_msgs)
        })
        
        if i + CHUNK_SIZE >= n:
            break
            
    return chunks

async def process_chat_chunks(conn: asyncpg.Connection, user_id: str, chat_id: str, threads_msgs: List[List[Dict[str, Any]]], thread_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Builds and inserts chunks for all threads in a chat.
    Returns the list of chunks created.
    """
    all_chunks = []
    
    for thread_msgs, thread_id in zip(threads_msgs, thread_ids):
        chunks = build_chunks_for_thread(thread_msgs)
        for c in chunks:
            c["thread_id"] = thread_id
        all_chunks.extend(chunks)
        
    if not all_chunks:
        return []
        
    # Bulk insert
    records = []
    for c in all_chunks:
        records.append((
            c["_db_id"],
            user_id,
            chat_id,
            c["thread_id"],
            c["_db_id"], # qdrant_id same as id
            c["start_message_id"],
            c["end_message_id"],
            c["start_time"],
            c["end_time"],
            c["content"],
            c["message_ids"],
            c["message_count"]
        ))
        
    await conn.executemany(
        """
        INSERT INTO public.message_chunks
            (id, user_id, chat_id, thread_id, qdrant_id, start_message_id, end_message_id, start_time, end_time, content, message_ids, message_count)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        """,
        records,
    )
    
    return all_chunks

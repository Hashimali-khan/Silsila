import logging
from typing import List, Dict, Any, Set
import asyncpg
import json

logger = logging.getLogger(__name__)

# Very rough estimate: 1 word ~ 1.3 tokens
def estimate_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)

async def build_evidence(
    conn: asyncpg.Connection,
    user_id: str,
    search_results: List[Dict[str, Any]],
    context_expansion: int = 2,
    max_tokens: int = 4000
) -> List[Dict[str, Any]]:
    """
    Given Qdrant search results (chunks), expands context by ±N messages within the same thread.
    Deduplicates messages and formats them into evidence blocks up to a token budget.
    """
    if not search_results:
        return []

    # Extract all relevant message_ids from chunks, plus some expansion
    # To do context expansion efficiently, we can fetch the messages around the matching chunk's boundaries.
    
    # We will gather the target message IDs from the payloads first.
    target_message_ids = set()
    chunk_scores = {}
    
    for res in search_results:
        payload = res.get("payload", {})
        m_ids = payload.get("message_ids", [])
        if not m_ids:
            continue
            
        for m_id in m_ids:
            target_message_ids.add(m_id)
            chunk_scores[m_id] = max(chunk_scores.get(m_id, 0), res.get("score", 0))

    if not target_message_ids:
        return []

    # Fetch those messages and their thread_id from message_threads
    # We need to expand context. Instead of fetching all threads, we can get the thread_ids,
    # then for each thread, fetch the messages that are within ±context_expansion of the matched messages.
    
    # Let's get the original messages with their timestamps and thread_ids
    records = await conn.fetch(
        """
        SELECT m.id, m.chat_id, m.sender_name, m.timestamp, m.content, m.is_system_msg, m.is_media, mt.thread_id
        FROM public.messages m
        JOIN public.message_threads mt ON m.id = mt.message_id
        WHERE m.id = ANY($1::uuid[]) AND m.user_id = $2
        """,
        list(target_message_ids), user_id
    )
    
    thread_ids = set(r["thread_id"] for r in records)
    
    evidence_blocks = []
    total_tokens = 0
    seen_message_ids: Set[str] = set()
    
    # For each thread, fetch all messages, ordered by timestamp
    for thread_id in thread_ids:
        thread_msgs = await conn.fetch(
            """
            SELECT m.id, m.sender_name, m.timestamp, m.content, m.is_system_msg, m.is_media
            FROM public.messages m
            JOIN public.message_threads mt ON m.id = mt.message_id
            WHERE mt.thread_id = $1 AND m.user_id = $2
            ORDER BY m.timestamp ASC
            """,
            thread_id, user_id
        )
        
        # Find indices of matched messages
        matched_indices = []
        for i, m in enumerate(thread_msgs):
            if str(m["id"]) in target_message_ids:
                matched_indices.append(i)
                
        if not matched_indices:
            continue
            
        # Determine the ranges to include (with expansion)
        ranges_to_include = []
        for idx in matched_indices:
            start_idx = max(0, idx - context_expansion)
            end_idx = min(len(thread_msgs) - 1, idx + context_expansion)
            ranges_to_include.append((start_idx, end_idx))
            
        # Merge overlapping ranges
        ranges_to_include.sort()
        merged_ranges = []
        for r in ranges_to_include:
            if not merged_ranges:
                merged_ranges.append(r)
            else:
                last_r = merged_ranges[-1]
                if r[0] <= last_r[1] + 1: # overlap or adjacent
                    merged_ranges[-1] = (last_r[0], max(last_r[1], r[1]))
                else:
                    merged_ranges.append(r)
                    
        # Extract blocks for this thread
        for start_idx, end_idx in merged_ranges:
            block_msgs = thread_msgs[start_idx:end_idx+1]
            
            # Filter out messages we've already included (deduplication)
            block_msgs = [m for m in block_msgs if str(m["id"]) not in seen_message_ids]
            if not block_msgs:
                continue
                
            formatted_texts = []
            block_msg_ids = []
            
            for m in block_msgs:
                m_id = str(m["id"])
                seen_message_ids.add(m_id)
                block_msg_ids.append(m_id)
                
                if m["is_system_msg"]:
                    formatted_texts.append(f"[{m['timestamp'].strftime('%Y-%m-%d %H:%M')}] SYSTEM: {m['content']}")
                elif m["is_media"]:
                    formatted_texts.append(f"[{m['timestamp'].strftime('%Y-%m-%d %H:%M')}] {m['sender_name']}: <Media omitted>")
                else:
                    formatted_texts.append(f"[{m['timestamp'].strftime('%Y-%m-%d %H:%M')}] {m['sender_name']}: {m['content']}")
                    
            block_content = "\n".join(formatted_texts)
            block_tokens = estimate_tokens(block_content)
            
            if total_tokens + block_tokens > max_tokens:
                # Reached limit
                return evidence_blocks
                
            evidence_blocks.append({
                "thread_id": str(thread_id),
                "content": block_content,
                "message_ids": block_msg_ids
            })
            total_tokens += block_tokens
            
    return evidence_blocks

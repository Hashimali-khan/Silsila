from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse
import json
import logging
import asyncio
import re

from app.dependencies import get_current_user_id
from app.db.connection import get_pool, set_rls_user
from app.services.hybrid_search import hybrid_search
from app.services.evidence_builder import build_evidence
from app.services.llm import llm_service
from app.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

STOPWORDS = {
    "what", "when", "where", "which", "who", "whom", "whose", "why", "how",
    "is", "are", "was", "were", "been", "being", "have", "has", "had", "do",
    "does", "did", "a", "an", "the", "and", "but", "if", "or", "because", "as",
    "until", "while", "of", "at", "by", "for", "with", "about", "against", "between",
    "into", "through", "during", "before", "after", "above", "below", "to", "from",
    "up", "down", "in", "out", "on", "off", "over", "under", "again", "further",
    "then", "once", "here", "there", "all", "any", "both", "each", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same",
    "so", "than", "too", "very", "can", "will", "just", "don", "should", "now",
    "our", "we", "us", "me", "my", "you", "your", "they", "them", "it", "its"
}

class ChatQueryRequest(BaseModel):
    query_text: str
    chat_id: str
    person_id: Optional[str] = None

async def fetch_conversation_windows(
    conn,
    chat_id: str,
    anchor_records: list,
    interval_minutes: int = 4,
    max_total: int = 65
) -> list:
    """
    Given matched anchor messages, retrieves the cohesive dialogue window
    (preceding and following messages within ±interval_minutes) so the LLM sees
    the entire conversational setup, banter, and reactions rather than isolated 1-liners.
    """
    if not anchor_records:
        return []
    
    seen_ids = set()
    all_msgs = []
    
    for r in anchor_records[:8]:
        ts = r.get("timestamp")
        if not ts:
            continue
        window_rows = await conn.fetch(
            """
            SELECT m.id, m.sender_name, m.timestamp, m.content, mt.thread_id
            FROM public.messages m
            LEFT JOIN public.message_threads mt ON m.id = mt.message_id
            WHERE m.chat_id = $1::uuid
              AND m.is_system_msg = false
              AND m.content != ''
              AND m.timestamp BETWEEN $2::timestamptz - ($3 || ' minutes')::interval 
                                  AND $2::timestamptz + ($3 || ' minutes')::interval
            ORDER BY m.timestamp ASC
            LIMIT 15
            """,
            chat_id, ts, str(interval_minutes)
        )
        for w in window_rows:
            wid = str(w["id"])
            if wid not in seen_ids:
                seen_ids.add(wid)
                all_msgs.append(dict(w))
            if len(all_msgs) >= max_total:
                break
        if len(all_msgs) >= max_total:
            break

    all_msgs.sort(key=lambda x: x["timestamp"])
    return all_msgs

@router.post("/chat")
@limiter.limit("30/minute")
async def chat_endpoint(
    request: Request,
    body: ChatQueryRequest,
    user_id: str = Depends(get_current_user_id),
    pool = Depends(get_pool)
):
    """
    Streaming Q&A endpoint using SSE with hybrid search and windowed conversational RAG.
    """
    async def event_generator():
        yield {"data": json.dumps({"type": "status", "content": "Searching chat archive..."})}
        
        evidence_blocks = []

        # 1. Check if chat has precomputed vector chunks
        has_chunks = False
        async with pool.acquire() as conn:
            await set_rls_user(conn, user_id)
            has_chunks = bool(await conn.fetchval(
                "SELECT 1 FROM public.message_chunks WHERE chat_id = $1::uuid LIMIT 1",
                body.chat_id
            ))

        # 2. If vector chunks exist, try Hybrid Search
        if has_chunks:
            try:
                search_results = await asyncio.wait_for(
                    hybrid_search(
                        user_id=user_id,
                        chat_id=body.chat_id,
                        query_text=body.query_text,
                        person_id=body.person_id,
                        limit=10
                    ),
                    timeout=8.0
                )
                if search_results:
                    async with pool.acquire() as conn:
                        await set_rls_user(conn, user_id)
                        evidence_blocks = await build_evidence(
                            conn=conn,
                            user_id=user_id,
                            search_results=search_results
                        )
            except Exception as e:
                logger.warning(f"Vector search skipped/failed: {e}")

        # 3. Conversational RAG with Dialogue Windowing
        if not evidence_blocks:
            async with pool.acquire() as conn:
                await set_rls_user(conn, user_id)

                q_lower = body.query_text.lower()
                is_first_chat = any(w in q_lower for w in [
                    "first", "start", "begin", "kab", "pehla", "pehli", "meet", "earliest", "origin", "shuru"
                ])
                is_sender_stats = any(w in q_lower for w in [
                    "most message", "who send", "who text", "who sent", "more message", "active", "who talk"
                ])
                is_humor = any(w in q_lower for w in [
                    "joke", "jokes", "inside joke", "funny", "laugh", "lmao", "lol", "humor", "banter",
                    "teasing", "meme", "mazak", "roast", "funniest", "ajeeb", "bhai"
                ])
                is_trip = any(w in q_lower for w in [
                    "plan", "plans", "trip", "trips", "travel", "vacation", "tour", "milte",
                    "flight", "hotel", "ticket", "drive", "chalein", "chal", "party"
                ])

                kw_records = []
                extra_context = ""

                if is_first_chat:
                    # Retrieve the very first messages exchanged in this chat
                    kw_records = await conn.fetch(
                        """
                        SELECT m.id, m.sender_name, m.timestamp, m.content, mt.thread_id
                        FROM public.messages m
                        LEFT JOIN public.message_threads mt ON m.id = mt.message_id
                        WHERE m.chat_id = $1::uuid AND m.is_system_msg = false
                        ORDER BY m.timestamp ASC
                        LIMIT 40
                        """,
                        body.chat_id
                    )
                elif is_sender_stats:
                    # Provide exact sender counts + active sample dialogues
                    stats_records = await conn.fetch(
                        """
                        SELECT sender_name, COUNT(*) AS msg_count
                        FROM public.messages
                        WHERE chat_id = $1::uuid AND is_system_msg = false
                        GROUP BY sender_name
                        ORDER BY msg_count DESC
                        LIMIT 10
                        """,
                        body.chat_id
                    )
                    if stats_records:
                        summary_lines = [f"- {r['sender_name']}: {r['msg_count']} messages" for r in stats_records]
                        extra_context = "MESSAGE COUNT STATISTICS:\n" + "\n".join(summary_lines) + "\n\nSAMPLE RECENT DIALOGUES:\n"

                    kw_records = await conn.fetch(
                        """
                        SELECT m.id, m.sender_name, m.timestamp, m.content, mt.thread_id
                        FROM public.messages m
                        LEFT JOIN public.message_threads mt ON m.id = mt.message_id
                        WHERE m.chat_id = $1::uuid AND m.is_system_msg = false
                        ORDER BY m.timestamp DESC
                        LIMIT 35
                        """,
                        body.chat_id
                    )
                elif is_humor:
                    # Targeted retrieval of laughter, banter, and humorous exchanges
                    anchor_humor = await conn.fetch(
                        """
                        SELECT m.id, m.sender_name, m.timestamp, m.content, mt.thread_id
                        FROM public.messages m
                        LEFT JOIN public.message_threads mt ON m.id = mt.message_id
                        WHERE m.chat_id = $1::uuid
                          AND m.is_system_msg = false
                          AND m.content != ''
                          AND (
                              m.content ILIKE '%haha%'
                              OR m.content ILIKE '%😂%'
                              OR m.content ILIKE '%🤣%'
                              OR m.content ILIKE '%lmao%'
                              OR m.content ILIKE '%lol%'
                              OR m.content ILIKE '%rofl%'
                              OR m.content ILIKE '%mazak%'
                              OR m.content ILIKE '%joke%'
                              OR m.content ILIKE '%ajeeb%'
                              OR m.content ILIKE '%pagal%'
                          )
                        ORDER BY m.timestamp DESC
                        LIMIT 10
                        """,
                        body.chat_id
                    )
                    # Expand around banter moments so LLM sees the setup, jokes, and reactions
                    kw_records = await fetch_conversation_windows(conn, body.chat_id, anchor_humor, interval_minutes=4, max_total=70)
                elif is_trip:
                    # Targeted retrieval of plans, trips, and meetups
                    anchor_trips = await conn.fetch(
                        """
                        SELECT m.id, m.sender_name, m.timestamp, m.content, mt.thread_id
                        FROM public.messages m
                        LEFT JOIN public.message_threads mt ON m.id = mt.message_id
                        WHERE m.chat_id = $1::uuid
                          AND m.is_system_msg = false
                          AND m.content != ''
                          AND (
                              m.content ILIKE '%plan%'
                              OR m.content ILIKE '%trip%'
                              OR m.content ILIKE '%chal%'
                              OR m.content ILIKE '%ticket%'
                              OR m.content ILIKE '%hotel%'
                              OR m.content ILIKE '%tour%'
                              OR m.content ILIKE '%meet%'
                              OR m.content ILIKE '%milte%'
                              OR m.content ILIKE '%dinner%'
                          )
                        ORDER BY m.timestamp DESC
                        LIMIT 10
                        """,
                        body.chat_id
                    )
                    kw_records = await fetch_conversation_windows(conn, body.chat_id, anchor_trips, interval_minutes=5, max_total=70)
                else:
                    # Extract meaningful keywords for full-text search
                    words = [
                        w for w in re.findall(r'\b[a-zA-Z0-9_\u0600-\u06FF]{3,}\b', q_lower)
                        if w not in STOPWORDS
                    ]

                    anchors = []
                    if words:
                        tsquery_str = " | ".join(words)
                        try:
                            anchors = await conn.fetch(
                                """
                                SELECT m.id, m.sender_name, m.timestamp, m.content, mt.thread_id,
                                       ts_rank(m.search_vector, to_tsquery('simple', $2)) AS rank
                                FROM public.messages m
                                LEFT JOIN public.message_threads mt ON m.id = mt.message_id
                                WHERE m.chat_id = $1::uuid
                                  AND m.content != ''
                                  AND m.search_vector IS NOT NULL
                                  AND m.search_vector @@ to_tsquery('simple', $2)
                                ORDER BY rank DESC, m.timestamp DESC
                                LIMIT 10
                                """,
                                body.chat_id, tsquery_str
                            )
                        except Exception as e:
                            logger.warning(f"to_tsquery failed with '{tsquery_str}': {e}")

                    # Fallback to plain search / ILIKE if no hits
                    if not anchors:
                        anchors = await conn.fetch(
                            """
                            SELECT m.id, m.sender_name, m.timestamp, m.content, mt.thread_id
                            FROM public.messages m
                            LEFT JOIN public.message_threads mt ON m.id = mt.message_id
                            WHERE m.chat_id = $1::uuid
                              AND m.content != ''
                              AND (
                                  (m.search_vector IS NOT NULL AND m.search_vector @@ plainto_tsquery('simple', $2))
                                  OR m.content ILIKE '%' || $2 || '%'
                              )
                            ORDER BY m.timestamp DESC
                            LIMIT 10
                            """,
                            body.chat_id, body.query_text
                        )

                    if anchors:
                        kw_records = await fetch_conversation_windows(conn, body.chat_id, anchors, interval_minutes=4, max_total=60)
                    else:
                        kw_records = await conn.fetch(
                            """
                            SELECT m.id, m.sender_name, m.timestamp, m.content, mt.thread_id
                            FROM public.messages m
                            LEFT JOIN public.message_threads mt ON m.id = mt.message_id
                            WHERE m.chat_id = $1::uuid AND m.is_system_msg = false
                            ORDER BY m.timestamp DESC
                            LIMIT 40
                            """,
                            body.chat_id
                        )

                if kw_records or extra_context:
                    dialogue_lines = []
                    for r in kw_records:
                        ts_str = r['timestamp'].strftime('%Y-%m-%d %H:%M') if r.get('timestamp') else ''
                        mid = str(r['id'])[:8]
                        raw_msg = r.get('content') or ''
                        # Cap excessively long single messages so they don't blow up token windows or network buffers
                        if len(raw_msg) > 1500:
                            msg_display = raw_msg[:1500] + "... [truncated]"
                        else:
                            msg_display = raw_msg
                        dialogue_lines.append(f"[{ts_str}] [id: {mid}] {r['sender_name']}: {msg_display}")
                    
                    content_text = extra_context + "\n".join(dialogue_lines)
                    safe_messages = [
                        {
                            "id": str(r["id"]),
                            "sender_name": r.get("sender_name") or "Unknown",
                            "timestamp": r["timestamp"].isoformat() if r.get("timestamp") else None,
                            "content": (r.get("content")[:1500] + "... [truncated]") if len(r.get("content") or "") > 1500 else (r.get("content") or ""),
                            "thread_id": str(r["thread_id"]) if r.get("thread_id") else None,
                        }
                        for r in kw_records
                    ]
                    evidence_blocks = [{
                        "thread_id": str(kw_records[0]["thread_id"]) if kw_records and kw_records[0].get("thread_id") else "conversation_history",
                        "content": content_text,
                        "messages": safe_messages
                    }]

        if not evidence_blocks:
            yield {"data": json.dumps({"type": "error", "content": "No messages found in this chat to answer from."})}
            return

        yield {"data": json.dumps({"type": "status", "content": "Analyzing conversation memories..."})}
        
        # Send lightweight evidence blocks to client for citations UI (only thread_id & messages needed)
        client_evidence = [
            {
                "thread_id": b.get("thread_id"),
                "messages": b.get("messages", [])
            }
            for b in evidence_blocks
        ]
        yield {"data": json.dumps({"type": "evidence", "content": client_evidence}, default=str)}
        
        # 4. Stream LLM answer
        try:
            async for token_msg in llm_service.stream_answer(body.query_text, evidence_blocks):
                yield {"data": token_msg}
        except Exception as e:
            logger.exception(f"Error streaming LLM tokens: {e}")
            yield {"data": json.dumps({"type": "error", "content": f"LLM generation failed: {str(e)}"})}
            return
            
        yield {"data": json.dumps({"type": "done"})}

    async def safe_event_generator():
        try:
            async for event in event_generator():
                yield event
        except Exception as e:
            logger.exception(f"Fatal error in chat stream: {e}")
            yield {"data": json.dumps({"type": "error", "content": f"Server error: {str(e)}"})}

    return EventSourceResponse(safe_event_generator())

from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse
import json
import logging
import asyncio

from app.dependencies import get_current_user_id
from app.db.connection import get_pool, set_rls_user
from app.services.hybrid_search import hybrid_search
from app.services.evidence_builder import build_evidence
from app.services.llm import llm_service
from app.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

class ChatQueryRequest(BaseModel):
    query_text: str
    chat_id: str
    person_id: Optional[str] = None

@router.post("/chat")
@limiter.limit("30/minute")
async def chat_endpoint(
    request: Request,
    body: ChatQueryRequest,
    user_id: str = Depends(get_current_user_id),
    pool = Depends(get_pool)
):
    """
    Streaming Q&A endpoint using SSE with hybrid search and fast Postgres fallback.
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

        # 2. If vector chunks exist, try Hybrid Search (capped at 3s)
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
                    timeout=3.0
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

        # 3. Direct Postgres Search (instant across all 18K+ messages)
        if not evidence_blocks:
            async with pool.acquire() as conn:
                await set_rls_user(conn, user_id)

                q_lower = body.query_text.lower()
                is_first_chat = any(w in q_lower for w in [
                    "first", "start", "begin", "kab", "pehla", "pehli", "meet", "earliest", "origin", "shuru"
                ])

                if is_first_chat:
                    # Retrieve the very first messages exchanged in this chat
                    kw_records = await conn.fetch(
                        """
                        SELECT m.id, m.sender_name, m.timestamp, m.content, mt.thread_id
                        FROM public.messages m
                        LEFT JOIN public.message_threads mt ON m.id = mt.message_id
                        WHERE m.chat_id = $1::uuid AND m.is_system_msg = false
                        ORDER BY m.timestamp ASC
                        LIMIT 35
                        """,
                        body.chat_id
                    )
                else:
                    # Keyword full-text search
                    kw_records = await conn.fetch(
                        """
                        SELECT m.id, m.sender_name, m.timestamp, m.content, mt.thread_id
                        FROM public.messages m
                        LEFT JOIN public.message_threads mt ON m.id = mt.message_id
                        WHERE m.chat_id = $1::uuid
                          AND m.content != ''
                          AND (
                              m.content_tsv @@ plainto_tsquery('simple', $2)
                              OR m.content ILIKE '%' || $2 || '%'
                          )
                        ORDER BY m.timestamp DESC
                        LIMIT 25
                        """,
                        body.chat_id, body.query_text
                    )

                    # Fallback to recent conversational context if no exact keyword hit
                    if not kw_records:
                        kw_records = await conn.fetch(
                            """
                            SELECT m.id, m.sender_name, m.timestamp, m.content, mt.thread_id
                            FROM public.messages m
                            LEFT JOIN public.message_threads mt ON m.id = mt.message_id
                            WHERE m.chat_id = $1::uuid AND m.is_system_msg = false
                            ORDER BY m.timestamp DESC
                            LIMIT 30
                            """,
                            body.chat_id
                        )

                if kw_records:
                    content_text = "\n".join(
                        f"[{r['timestamp'].strftime('%Y-%m-%d %H:%M') if r.get('timestamp') else ''}] [id: {str(r['id'])[:8]}] {r['sender_name']}: {r['content']}"
                        for r in kw_records
                    )
                    safe_messages = [
                        {
                            "id": str(r["id"]),
                            "sender_name": r.get("sender_name") or "Unknown",
                            "timestamp": r["timestamp"].isoformat() if r.get("timestamp") else None,
                            "content": r.get("content") or "",
                            "thread_id": str(r["thread_id"]) if r.get("thread_id") else None,
                        }
                        for r in kw_records
                    ]
                    evidence_blocks = [{
                        "thread_id": str(kw_records[0]["thread_id"]) if kw_records[0].get("thread_id") else "archive_timeline",
                        "content": content_text,
                        "messages": safe_messages
                    }]

        if not evidence_blocks:
            yield {"data": json.dumps({"type": "error", "content": "No messages found in this chat to answer from."})}
            return

        yield {"data": json.dumps({"type": "status", "content": "Analyzing conversation memories..."})}
        
        # Send evidence blocks to client for citations UI
        yield {"data": json.dumps({"type": "evidence", "content": evidence_blocks}, default=str)}
        
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

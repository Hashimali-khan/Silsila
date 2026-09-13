from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse
import json

from app.dependencies import get_current_user_id
from app.db.connection import get_pool
from app.services.hybrid_search import hybrid_search
from app.services.evidence_builder import build_evidence
from app.services.llm import llm_service

router = APIRouter()

class ChatQueryRequest(BaseModel):
    query_text: str
    chat_id: str
    person_id: Optional[str] = None

@router.post("/chat")
async def chat_endpoint(
    request: Request,
    body: ChatQueryRequest,
    user_id: str = Depends(get_current_user_id),
    pool = Depends(get_pool)
):
    """
    Streaming Q&A endpoint using SSE.
    """
    async def event_generator():
        yield {"data": json.dumps({"type": "status", "content": "searching"})}
        
        # 1. Hybrid Search
        search_results = await hybrid_search(
            user_id=user_id,
            chat_id=body.chat_id,
            query_text=body.query_text,
            person_id=body.person_id,
            limit=10
        )
        
        if not search_results:
            yield {"data": json.dumps({"type": "status", "content": "found 0 messages"})}
            yield {"data": json.dumps({"type": "error", "content": "Could not find any relevant messages for this query."})}
            return
            
        yield {"data": json.dumps({"type": "status", "content": f"found {len(search_results)} relevant chunks"})}
        
        # 2. Build Evidence
        async with pool.acquire() as conn:
            evidence_blocks = await build_evidence(
                conn=conn,
                user_id=user_id,
                search_results=search_results
            )
            
        if not evidence_blocks:
            yield {"data": json.dumps({"type": "error", "content": "Failed to extract evidence messages from the database."})}
            return
            
        yield {"data": json.dumps({"type": "status", "content": "analyzing"})}
        
        # Send the evidence blocks to the client so they can be rendered in the UI
        yield {"data": json.dumps({"type": "evidence", "content": evidence_blocks})}
        
        # 3. Stream LLM answer
        async for token_msg in llm_service.stream_answer(body.query_text, evidence_blocks):
            yield {"data": token_msg}
            
        yield {"data": json.dumps({"type": "done"})}

    return EventSourceResponse(event_generator())

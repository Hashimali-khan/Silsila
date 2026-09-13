"""Search router — full-text keyword search within a chat."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.db.connection import get_pool, set_rls_user
from app.db.queries.search import keyword_search, keyword_search_count
from app.dependencies import get_current_user_id
from app.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter()


class SearchResult(BaseModel):
    id: str
    sender_name: str
    timestamp: Any
    content: str
    person_id: str | None
    highlight: str  # HTML with <mark> tags from ts_headline


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResult]


@router.get("/search", response_model=SearchResponse)
@limiter.limit("30/minute")
async def search_messages(
    request: Request,
    chat_id: str = Query(..., description="UUID of the chat to search within"),
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user_id),
):
    """
    Full-text keyword search within a specific chat.

    Uses Postgres tsvector with the 'simple' config (multilingual-safe for
    Urdu, Hinglish, English). ts_headline wraps matches in <mark> tags.

    Returns results ordered by relevance rank then recency.
    """
    pool = await get_pool()

    async with pool.acquire() as conn:
        await set_rls_user(conn, user_id)

        # Validate chat belongs to user (RLS enforces this, but we want a clear 404)
        exists = await conn.fetchval(
            "SELECT 1 FROM public.chats WHERE id = $1::uuid",
            chat_id,
        )
        if not exists:
            raise HTTPException(status_code=404, detail="Chat not found.")

        results = await keyword_search(conn, chat_id, q, limit, offset)
        total = await keyword_search_count(conn, chat_id, q)

    logger.info("Search '%s' in chat %s: %d results", q, chat_id, total)

    return SearchResponse(
        query=q,
        total=total,
        results=[SearchResult(**r) for r in results],
    )

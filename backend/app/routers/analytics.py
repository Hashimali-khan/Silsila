"""Analytics router — chat list, chat metadata, basic stats, activity charts."""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from pydantic import BaseModel

from app.db.connection import get_pool, set_rls_user
from app.db.queries.messages import get_chat_list, get_chat_by_id, get_messages_page
from app.db.queries.people import get_people_for_chat
from app.db.queries.analytics import get_chat_stats, get_messages_per_day, get_messages_per_sender
from app.dependencies import get_current_user_id
from app.services.qdrant_client import qdrant_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Chat list ──────────────────────────────────────────────────────────────────

class ChatCard(BaseModel):
    id: str
    name: str
    participant_count: int
    message_count: int
    first_message_at: Any
    last_message_at: Any
    created_at: Any


@router.get("/chats", response_model=list[ChatCard])
async def list_chats(user_id: str = Depends(get_current_user_id)):
    """
    List all chats uploaded by the authenticated user.
    Ordered by most recent message. Used for the dashboard chat grid.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await set_rls_user(conn, user_id)
        chats = await get_chat_list(conn)
    return [ChatCard(**c) for c in chats]


# ── Chat detail ────────────────────────────────────────────────────────────────

class PersonSummary(BaseModel):
    id: str
    canonical_name: str
    message_count: int


class ChatDetailResponse(BaseModel):
    id: str
    name: str
    participant_count: int
    message_count: int
    first_message_at: Any
    last_message_at: Any
    people: list[PersonSummary]


@router.get("/chats/{chat_id}", response_model=ChatDetailResponse)
async def get_chat_detail(
    chat_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get full chat metadata including participant list."""
    try:
        uuid.UUID(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat ID format.")

    pool = await get_pool()
    async with pool.acquire() as conn:
        await set_rls_user(conn, user_id)
        chat = await get_chat_by_id(conn, chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found.")
        people = await get_people_for_chat(conn, chat_id)

    return ChatDetailResponse(
        **chat,
        people=[PersonSummary(**p) for p in people],
    )


@router.delete("/chats/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """
    Permanently deletes a specific chat and cascades to all its messages, threads, and chunks.
    """
    try:
        uuid.UUID(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat ID format.")

    pool = await get_pool()
    async with pool.acquire() as conn:
        await set_rls_user(conn, user_id)
        chat = await conn.fetchrow(
            "SELECT id FROM public.chats WHERE id = $1::uuid AND user_id = $2",
            chat_id, user_id
        )
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found.")

        async with conn.transaction():
            await conn.execute("DELETE FROM public.ingestion_jobs WHERE chat_id = $1::uuid", chat_id)
            await conn.execute("DELETE FROM public.chats WHERE id = $1::uuid AND user_id = $2", chat_id, user_id)

    # Clean up Qdrant vectors for this chat asynchronously
    try:
        await qdrant_service.delete_by_chat_id(chat_id)
    except Exception as e:
        logger.warning(f"Could not clean up Qdrant points for deleted chat {chat_id}: {e}")

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Messages pagination ────────────────────────────────────────────────────────

class MessageItem(BaseModel):
    id: str
    sender_name: str
    timestamp: Any
    content: str
    is_media: bool
    person_id: str | None


class MessagesPageResponse(BaseModel):
    chat_id: str
    messages: list[MessageItem]
    has_more: bool
    oldest_timestamp: str | None  # cursor for next page


@router.get("/chats/{chat_id}/messages", response_model=MessagesPageResponse)
async def get_chat_messages(
    chat_id: str,
    before: str | None = Query(None, description="ISO timestamp cursor — fetch messages before this time"),
    limit: int = Query(100, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
):
    """
    Paginated message browser. Used for infinite scroll in the chat view.

    Pass `before` (ISO timestamp) to fetch older messages (scroll up to load more).
    First call: omit `before` to get the most recent messages.
    """
    try:
        uuid.UUID(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat ID format.")

    pool = await get_pool()
    async with pool.acquire() as conn:
        await set_rls_user(conn, user_id)

        chat = await get_chat_by_id(conn, chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found.")

        msgs = await get_messages_page(conn, chat_id, limit=limit + 1, before_timestamp=before)

    has_more = len(msgs) > limit
    if has_more:
        msgs = msgs[-limit:]  # trim extra (we fetched limit+1 to detect has_more)

    oldest_ts = msgs[0]["timestamp"].isoformat() if msgs else None

    return MessagesPageResponse(
        chat_id=chat_id,
        messages=[MessageItem(**m) for m in msgs],
        has_more=has_more,
        oldest_timestamp=oldest_ts,
    )


# ── Stats ──────────────────────────────────────────────────────────────────────

class DailyActivity(BaseModel):
    date: str
    message_count: int
    active_senders: int


class SenderBreakdown(BaseModel):
    sender_name: str
    message_count: int


class ChatStatsResponse(BaseModel):
    total_messages: int
    thread_count: int
    participants: list[str]
    messages_per_sender: dict[str, int]
    date_range: dict[str, str]
    daily_activity: list[DailyActivity]
    sender_breakdown: list[SenderBreakdown]


@router.get("/chats/{chat_id}/stats", response_model=ChatStatsResponse)
async def get_chat_statistics(
    chat_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """
    Full analytics for a chat: pre-computed stats + time-series activity.
    Used for the stats section in the chat view.
    """
    try:
        uuid.UUID(chat_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat ID format.")

    pool = await get_pool()
    async with pool.acquire() as conn:
        await set_rls_user(conn, user_id)

        chat = await get_chat_by_id(conn, chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found.")

        stats = await get_chat_stats(conn, chat_id)
        daily = await get_messages_per_day(conn, chat_id)
        by_sender = await get_messages_per_sender(conn, chat_id)
        thread_cnt = await conn.fetchval(
            "SELECT count(*) FROM public.conversation_threads WHERE chat_id = $1::uuid",
            chat_id,
        ) or 0

    # Fallback if analysis_cache hasn't been populated yet
    if not stats:
        stats = {
            "total_messages": chat["message_count"],
            "thread_count": thread_cnt,
            "participants": [s["sender_name"] for s in by_sender],
            "messages_per_sender": {s["sender_name"]: s["message_count"] for s in by_sender},
            "date_range": {
                "start": chat["first_message_at"].isoformat() if chat.get("first_message_at") else "",
                "end": chat["last_message_at"].isoformat() if chat.get("last_message_at") else "",
            },
        }
    else:
        if not stats.get("participants"):
            stats["participants"] = [s["sender_name"] for s in by_sender]
        if stats.get("thread_count", 0) == 0 and thread_cnt > 0:
            stats["thread_count"] = thread_cnt

    return ChatStatsResponse(
        **stats,
        daily_activity=[DailyActivity(**d) for d in daily],
        sender_breakdown=[SenderBreakdown(**s) for s in by_sender],
    )

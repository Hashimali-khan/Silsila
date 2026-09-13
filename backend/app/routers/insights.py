from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict, Any

from app.auth import get_current_user
from app.db.connection import get_pool
from app.db.queries.sentiment import get_emotion_trajectory
from app.db.queries.events import get_events
from app.services.insights import insights_service

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.get("/{chat_id}/emotions")
async def get_chat_emotions(
    chat_id: str,
    user_id: str = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get aggregated emotion trajectory over time for the Emotion Graph.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET LOCAL app.user_id = $1", user_id)
        # Check if chat exists and belongs to user
        chat = await conn.fetchrow("SELECT id FROM public.chats WHERE id = $1::uuid", chat_id)
        if not chat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
            
        return await get_emotion_trajectory(conn, chat_id)


@router.get("/{chat_id}/events")
async def get_chat_events(
    chat_id: str,
    user_id: str = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get all detected life events for a chat.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET LOCAL app.user_id = $1", user_id)
        chat = await conn.fetchrow("SELECT id FROM public.chats WHERE id = $1::uuid", chat_id)
        if not chat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
            
        return await get_events(conn, chat_id)


@router.get("/{chat_id}/memory-cards")
async def get_chat_memory_cards(
    chat_id: str,
    user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get memory cards (First Conversation, Longest Silence, etc.) for a chat.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET LOCAL app.user_id = $1", user_id)
        chat = await conn.fetchrow("SELECT id FROM public.chats WHERE id = $1::uuid", chat_id)
        if not chat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
            
    return await insights_service.get_memory_cards(user_id, chat_id)


@router.get("/{chat_id}/story")
async def get_chat_story(
    chat_id: str,
    user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get the 5-chapter story mode narrative for a chat.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET LOCAL app.user_id = $1", user_id)
        chat = await conn.fetchrow("SELECT id FROM public.chats WHERE id = $1::uuid", chat_id)
        if not chat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
            
    return await insights_service.get_story_mode(user_id, chat_id)

import logging
import json
from typing import Dict, Any, List

from app.db.connection import get_pool
from app.db.queries.insights import (
    get_cached_insight,
    set_cached_insight,
    get_longest_silence,
    get_most_romantic_exchange
)
from app.db.queries.events import get_events
from app.services.llm import llm_service
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class Chapter(BaseModel):
    title: str = Field(description="The title of the chapter")
    summary: str = Field(description="A 2-3 sentence narrative summary of this phase of the relationship")
    events: List[str] = Field(description="List of key events that happened in this chapter")

class StoryResult(BaseModel):
    chapters: List[Chapter] = Field(description="Exactly 5 chapters that form a narrative arc of the relationship")

class InsightsService:
    """
    Service for generating Memory Cards and Story Mode narratives.
    """

    @staticmethod
    async def get_memory_cards(user_id: str, chat_id: str) -> Dict[str, Any]:
        """
        Generates and caches memory cards for a chat.
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("SET LOCAL app.user_id = $1", user_id)
            
            # Check cache first
            cached = await get_cached_insight(conn, chat_id, "memory_cards")
            if cached:
                return cached
                
            # If not cached, calculate them
            longest_silence = await get_longest_silence(conn, chat_id)
            romantic = await get_most_romantic_exchange(conn, chat_id)
            
            # Also get first conversation
            first_msg_row = await conn.fetchrow(
                """
                SELECT sender_name, content, timestamp 
                FROM public.messages 
                WHERE chat_id = $1::uuid AND is_system_msg = FALSE 
                ORDER BY timestamp ASC LIMIT 1
                """, chat_id
            )
            first_msg = dict(first_msg_row) if first_msg_row else None
            if first_msg:
                first_msg["timestamp"] = first_msg["timestamp"].isoformat()
            
            cards = {
                "longest_silence": longest_silence,
                "most_romantic": romantic,
                "first_message": first_msg
            }
            
            # Cache it
            await set_cached_insight(conn, user_id, chat_id, "memory_cards", cards)
            
            return cards

    @staticmethod
    async def get_story_mode(user_id: str, chat_id: str) -> Dict[str, Any]:
        """
        Generates a 5-chapter story mode narrative for the chat using the LLM.
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("SET LOCAL app.user_id = $1", user_id)
            
            # Check cache first
            cached = await get_cached_insight(conn, chat_id, "story_mode")
            if cached:
                return cached
                
            # Fetch events to build the narrative
            events = await get_events(conn, chat_id)
            
            # Prepare prompt for LLM
            prompt = (
                "You are an empathetic AI that writes beautiful relationship narratives.\n"
                "Based on the following detected life events from a chat history, synthesize a structured 5-chapter story.\n"
                "The 5 chapters should ideally follow a narrative arc (e.g., The Beginning, Growing Closer, Challenges, Milestones, The Present).\n\n"
                "Events Timeline:\n"
            )
            
            if not events:
                prompt += "No major events detected. The conversation has been steady and continuous.\n"
            else:
                for e in events:
                    prompt += f"- {e['detected_at']}: {e['type'].capitalize()} - {e.get('description', '')}\n"
                    
            try:
                result = await llm_service.generate_json(prompt, response_schema=StoryResult)
                
                # Cache it
                if result:
                    await set_cached_insight(conn, user_id, chat_id, "story_mode", result)
                    
                return result or {"chapters": []}
            except Exception as e:
                logger.error(f"Failed to generate story mode: {e}")
                return {"chapters": []}

insights_service = InsightsService()

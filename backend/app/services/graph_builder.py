import logging
import json
from typing import List, Dict, Any
import asyncpg
from pydantic import BaseModel, Field

from app.services.llm import llm_service
from google.genai import types as genai_types

logger = logging.getLogger(__name__)

class PersonProfileSchema(BaseModel):
    summary: str = Field(description="A 1-2 sentence summary of who this person is in the context of the chat.")
    roles: list[str] = Field(description="Roles this person plays (e.g. planner, joker, peacemaker).")
    key_attributes: list[str] = Field(description="Key personality traits based on their messages.")
    topics_of_interest: list[str] = Field(description="Common topics they talk about.")
    notable_quotes: list[str] = Field(description="A few exact quotes that perfectly capture their personality.")

async def build_person_profile(pool: asyncpg.Pool, user_id: str, person_id: str, chat_id: str) -> None:
    """
    Builds an AI profile for a person by analyzing their messages in a chat.
    Updates the `people` table with the generated profile JSON.
    """
    logger.info(f"Building profile for person {person_id} in chat {chat_id}")
    
    async with pool.acquire() as conn:
        # Fetch the person's canonical name
        person = await conn.fetchrow("SELECT canonical_name FROM public.people WHERE id = $1 AND user_id = $2", person_id, user_id)
        if not person:
            logger.warning(f"Person {person_id} not found")
            return
            
        canonical_name = person["canonical_name"]
        
        # Fetch a sample of their messages (up to 100 recent/longest messages for context)
        # We can also fetch the surrounding thread context, but for a simple profile, just their messages + some context is enough.
        # To save tokens, we'll just fetch their 50 most substantial messages
        messages = await conn.fetch(
            """
            SELECT content, timestamp 
            FROM public.messages 
            WHERE person_id = $1 AND chat_id = $2 AND is_system_msg = false AND is_media = false
            ORDER BY length(content) DESC, timestamp DESC
            LIMIT 50
            """,
            person_id, chat_id
        )
        
        if not messages:
            logger.info(f"Not enough messages to build profile for {canonical_name}")
            return
            
        message_texts = [f"[{m['timestamp'].strftime('%Y-%m-%d %H:%M')}] {m['content']}" for m in messages]
        formatted_messages = "\n".join(message_texts)
        
        prompt = f"""
        You are an expert behavioral analyst profiling a person based on their WhatsApp messages.
        
        PERSON NAME: {canonical_name}
        
        MESSAGES:
        {formatted_messages}
        
        Based ONLY on the messages above, generate a profile for {canonical_name}. 
        Identify their role, personality, what they care about, and pick out some notable quotes that define them.
        """
        
        try:
            profile_dict = await llm_service.generate_json(
                prompt=prompt,
                response_schema=PersonProfileSchema
            )
            
            # Upsert into people table (we can store this in a metadata column, or analysis_cache)
            # The schema doesn't have a profile JSON column in 'people' table directly, 
            # let's store it in analysis_cache
            await conn.execute(
                """
                INSERT INTO public.analysis_cache (user_id, chat_id, metric_type, data)
                VALUES ($1, $2, 'person_profile', $3::jsonb)
                ON CONFLICT (user_id, chat_id, metric_type) 
                DO UPDATE SET data = jsonb_set(
                    COALESCE(public.analysis_cache.data, '{}'::jsonb),
                    array[$4::text],
                    $5::jsonb,
                    true
                )
                """,
                user_id, chat_id, json.dumps({person_id: profile_dict}), person_id, json.dumps(profile_dict)
            )
            
            logger.info(f"Successfully generated profile for {canonical_name}")
            
        except Exception as e:
            logger.error(f"Failed to generate profile for {canonical_name}: {e}")


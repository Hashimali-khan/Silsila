import logging
from typing import List, Dict, Any, Optional
import asyncpg
from pydantic import BaseModel, Field

from app.services.llm import llm_service

logger = logging.getLogger(__name__)

class CorefSuggestionResult(BaseModel):
    is_new_person: bool = Field(description="True if this appears to be a completely new person. False if it refers to a known person.")
    suggested_canonical_name: Optional[str] = Field(description="If it matches a known person, their exact canonical name from the list provided.")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0.")
    reasoning: str = Field(description="Brief reasoning for this resolution based on context.")

async def _fetch_message_context(conn: asyncpg.Connection, user_id: str, chat_id: str, message_timestamp: Any, window: int = 20) -> str:
    """Fetches +/- `window` messages around a given timestamp to provide LLM context."""
    records = await conn.fetch(
        """
        (
            SELECT sender_name, content, timestamp 
            FROM public.messages 
            WHERE chat_id = $2 AND timestamp <= $3 
            ORDER BY timestamp DESC 
            LIMIT $4
        )
        UNION ALL
        (
            SELECT sender_name, content, timestamp 
            FROM public.messages 
            WHERE chat_id = $2 AND timestamp > $3 
            ORDER BY timestamp ASC 
            LIMIT $4
        )
        ORDER BY timestamp ASC
        """,
        user_id, chat_id, message_timestamp, window
    )
    
    context = []
    for r in records:
        context.append(f"[{r['timestamp'].strftime('%Y-%m-%d %H:%M')}] {r['sender_name']}: {r['content']}")
    return "\n".join(context)

async def process_extracted_entities(
    pool: asyncpg.Pool, 
    user_id: str, 
    chat_id: str, 
    message_id: str, 
    content: str, 
    entities: List[Dict[str, Any]]
) -> None:
    """
    Process entities extracted from a message.
    Uses LLM with +/- 20 message context to suggest entity resolution.
    Suggestions are stored for Human-in-the-Loop review.
    """
    if not entities:
        return
        
    person_entities = [e for e in entities if e.get("label") == "Person"]
    if not person_entities:
        return
        
    async with pool.acquire() as conn:
        # Get the timestamp of the message
        msg_record = await conn.fetchrow("SELECT timestamp FROM public.messages WHERE id = $1", message_id)
        if not msg_record:
            return
            
        timestamp = msg_record["timestamp"]
        
        # Get all known people for this user
        people_records = await conn.fetch("SELECT id, canonical_name FROM public.people WHERE user_id = $1", user_id)
        known_people = {p["canonical_name"].lower(): str(p["id"]) for p in people_records}
        known_people_names = [p["canonical_name"] for p in people_records]
        
        # Fetch the message context
        context_str = await _fetch_message_context(conn, user_id, chat_id, timestamp, window=20)
        
        for entity in person_entities:
            name = entity.get("text", "").strip()
            if not name or len(name) < 2:
                continue
                
            # 1. Check if name already exists as an exact alias
            existing = await conn.fetchrow(
                "SELECT id FROM public.aliases WHERE user_id = $1 AND lower(alias) = lower($2)",
                user_id, name
            )
            if existing:
                continue
                
            # 2. Ask Gemini LLM for resolution
            prompt = f"""
            We found the name "{name}" in the following chat conversation.
            
            KNOWN PEOPLE: {known_people_names}
            
            CONVERSATION CONTEXT (+/- 20 messages):
            {context_str}
            
            Based on the context, does "{name}" refer to one of the KNOWN PEOPLE listed above, or is it a new person?
            """
            
            try:
                result_dict = await llm_service.generate_json(prompt, response_schema=CorefSuggestionResult)
                result = CorefSuggestionResult.model_validate(result_dict)
                
                suggested_person_id = None
                if not result.is_new_person and result.suggested_canonical_name:
                    suggested_person_id = known_people.get(result.suggested_canonical_name.lower())
                
                # Check if it already exists in pending suggestions
                existing_suggestion = await conn.fetchrow(
                    "SELECT id FROM public.alias_suggestions WHERE user_id = $1 AND lower(suggested_alias) = lower($2) AND status = 'pending'",
                    user_id, name
                )
                
                if existing_suggestion:
                    await conn.execute(
                        """
                        UPDATE public.alias_suggestions 
                        SET evidence_message_ids = array_append(evidence_message_ids, $3)
                        WHERE id = $4 AND NOT ($3 = ANY(evidence_message_ids))
                        """,
                        user_id, name, message_id, existing_suggestion["id"]
                    )
                else:
                    logger.info(f"Creating alias suggestion for '{name}' (Target: {result.suggested_canonical_name}, Confidence: {result.confidence})")
                    # Save a robust context snippet (first 500 chars of the context block for preview)
                    snippet = context_str[:500] + "..." if len(context_str) > 500 else context_str
                    
                    await conn.execute(
                        """
                        INSERT INTO public.alias_suggestions 
                        (user_id, suggested_alias, suggested_person_id, confidence, evidence_message_ids, context_snippet)
                        VALUES ($1, $2, $3, $4, ARRAY[$5::uuid], $6)
                        """,
                        user_id, name, suggested_person_id, float(result.confidence), message_id, snippet
                    )
            except Exception as e:
                logger.error(f"Failed to process coreference for '{name}': {e}")

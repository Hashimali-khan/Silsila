import logging
from typing import List, Dict, Any
import asyncpg

logger = logging.getLogger(__name__)

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
    Currently focuses on 'Person' entities for alias resolution.
    """
    if not entities:
        return
        
    person_entities = [e for e in entities if e.get("label") == "Person"]
    
    if not person_entities:
        return
        
    async with pool.acquire() as conn:
        for entity in person_entities:
            name = entity.get("text", "").strip()
            if not name or len(name) < 2:
                continue
                
            # 1. Check if name already exists as an exact alias or canonical name
            existing = await conn.fetchrow(
                "SELECT id FROM public.aliases WHERE user_id = $1 AND lower(alias) = lower($2)",
                user_id, name
            )
            if existing:
                continue
                
            # 2. Not an exact match. Find the best fuzzy match using pg_trgm
            # We want to compare against people canonical_names and existing aliases
            best_match = await conn.fetchrow(
                """
                SELECT p.id as person_id, p.canonical_name, similarity(lower(a.alias), lower($2)) as sim
                FROM public.aliases a
                JOIN public.people p ON a.person_id = p.id
                WHERE a.user_id = $1
                ORDER BY sim DESC
                LIMIT 1
                """,
                user_id, name
            )
            
            sim = best_match["sim"] if best_match else 0.0
            
            if sim > 0.85:
                # High confidence -> auto-merge
                logger.info(f"Auto-merging alias '{name}' to person '{best_match['canonical_name']}' (sim: {sim})")
                await conn.execute(
                    """
                    INSERT INTO public.aliases (user_id, person_id, alias, confidence)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT DO NOTHING
                    """,
                    user_id, best_match["person_id"], name, float(sim)
                )
            elif sim > 0.5:
                # Medium confidence -> human in the loop
                # Check if it already exists in pending suggestions
                existing_suggestion = await conn.fetchrow(
                    "SELECT id FROM public.alias_suggestions WHERE user_id = $1 AND lower(suggested_alias) = lower($2) AND status = 'pending'",
                    user_id, name
                )
                
                if existing_suggestion:
                    # Just append the evidence message
                    await conn.execute(
                        """
                        UPDATE public.alias_suggestions 
                        SET evidence_message_ids = array_append(evidence_message_ids, $3)
                        WHERE id = $4 AND NOT ($3 = ANY(evidence_message_ids))
                        """,
                        user_id, name, message_id, existing_suggestion["id"]
                    )
                else:
                    # Create new suggestion
                    # We can use the message content as the context snippet
                    # Let's extract a ±30 char window around the entity for snippet
                    start = max(0, entity.get("start", 0) - 30)
                    end = min(len(content), entity.get("end", 0) + 30)
                    snippet = f"...{content[start:end]}..."
                    
                    logger.info(f"Creating alias suggestion for '{name}' -> '{best_match['canonical_name']}' (sim: {sim})")
                    await conn.execute(
                        """
                        INSERT INTO public.alias_suggestions 
                        (user_id, suggested_alias, suggested_person_id, confidence, evidence_message_ids, context_snippet)
                        VALUES ($1, $2, $3, $4, ARRAY[$5::uuid], $6)
                        """,
                        user_id, name, best_match["person_id"], float(sim), message_id, snippet
                    )
            else:
                # Low confidence -> We could suggest it as a completely new person, but 
                # let's just create a suggestion without a suggested_person_id (so the user creates a new person)
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
                    start = max(0, entity.get("start", 0) - 30)
                    end = min(len(content), entity.get("end", 0) + 30)
                    snippet = f"...{content[start:end]}..."
                    
                    logger.info(f"Creating NEW PERSON suggestion for '{name}' (sim: {sim})")
                    await conn.execute(
                        """
                        INSERT INTO public.alias_suggestions 
                        (user_id, suggested_alias, suggested_person_id, confidence, evidence_message_ids, context_snippet)
                        VALUES ($1, $2, NULL, $3, ARRAY[$4::uuid], $5)
                        """,
                        user_id, name, float(sim), message_id, snippet
                    )

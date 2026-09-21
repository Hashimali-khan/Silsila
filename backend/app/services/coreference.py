"""coreference.py — Entity-Anchored Coreference Resolution

Implements the "local window + global registry" architecture:

LOCAL WINDOW  → ±20 messages around the current message (handles the common case:
                pronouns and references established in recent conversation).
GLOBAL REGISTRY → compact name→aliases lookup from all confirmed people
                  (handles long-range references: a nickname from 3 months ago).

For each Person entity extracted from a message:
  1. If it already exists as an exact alias → record entity_mention immediately.
  2. Otherwise → ask Gemini with local window + global registry.
  3. If confidence >= 0.9 → write entity_mention directly (auditable, reversible).
  4. If confidence < 0.9 → queue alias_suggestion for HITL review.

Original messages.content is NEVER modified. Annotations live in entity_mentions.
"""

import logging
from typing import List, Dict, Any, Optional
import asyncpg
from pydantic import BaseModel, Field

from app.services.llm import llm_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic schema for structured Gemini response
# ---------------------------------------------------------------------------

class CorefSuggestionResult(BaseModel):
    is_new_person: bool = Field(
        description="True if this appears to be a completely new person not in KNOWN PEOPLE."
    )
    suggested_canonical_name: Optional[str] = Field(
        default=None,
        description="If it matches a known person, their EXACT canonical name from the KNOWN PEOPLE list."
    )
    confidence: float = Field(
        description="Confidence score between 0.0 and 1.0."
    )
    reasoning: str = Field(
        description="Brief reasoning for this resolution based on the conversation context."
    )


# ---------------------------------------------------------------------------
# Helper: fetch ±window messages for local context
# ---------------------------------------------------------------------------

async def _fetch_local_context(
    conn: asyncpg.Connection,
    chat_id: str,
    message_timestamp: Any,
    window: int = 20,
) -> str:
    """Returns ±window messages around `message_timestamp` as a formatted string."""
    records = await conn.fetch(
        """
        (
            SELECT sender_name, content, timestamp
            FROM public.messages
            WHERE chat_id = $1 AND timestamp <= $2 AND is_system_msg = false
            ORDER BY timestamp DESC
            LIMIT $3
        )
        UNION ALL
        (
            SELECT sender_name, content, timestamp
            FROM public.messages
            WHERE chat_id = $1 AND timestamp > $2 AND is_system_msg = false
            ORDER BY timestamp ASC
            LIMIT $3
        )
        ORDER BY timestamp ASC
        """,
        chat_id, message_timestamp, window,
    )
    lines = [
        f"[{r['timestamp'].strftime('%Y-%m-%d %H:%M')}] {r['sender_name']}: {r['content']}"
        for r in records
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helper: build compact global entity registry
# ---------------------------------------------------------------------------

async def _build_global_registry(
    conn: asyncpg.Connection,
    user_id: str,
) -> tuple[str, dict[str, str]]:
    """
    Returns:
      registry_str  — compact text block for the LLM prompt
      name_to_id    — mapping of lowercase canonical_name → person_id
    """
    people = await conn.fetch(
        """
        SELECT p.id, p.canonical_name, p.message_count,
               COALESCE(array_agg(a.alias) FILTER (WHERE a.alias IS NOT NULL
                        AND lower(a.alias) != lower(p.canonical_name)), '{}') AS aliases
        FROM public.people p
        LEFT JOIN public.aliases a ON a.person_id = p.id AND a.user_id = $1
        WHERE p.user_id = $1
        GROUP BY p.id, p.canonical_name, p.message_count
        ORDER BY p.message_count DESC
        """,
        user_id,
    )

    lines = ["KNOWN PEOPLE (name | aliases | message count):"]
    name_to_id: dict[str, str] = {}

    for p in people:
        canonical = p["canonical_name"]
        aliases = [a for a in (p["aliases"] or []) if a]
        alias_str = ", ".join(aliases) if aliases else "—"
        lines.append(f"  - {canonical} (aliases: {alias_str}) — {p['message_count']} msgs")
        name_to_id[canonical.lower()] = str(p["id"])
        for a in aliases:
            name_to_id[a.lower()] = str(p["id"])

    return "\n".join(lines), name_to_id


# ---------------------------------------------------------------------------
# Helper: write a confirmed entity_mention
# ---------------------------------------------------------------------------

async def _write_entity_mention(
    conn: asyncpg.Connection,
    user_id: str,
    message_id: str,
    person_id: str,
    mention_text: str,
    resolution_method: str,
    confidence: float,
) -> None:
    """Inserts an entity_mention row. ON CONFLICT DO NOTHING preserves idempotency."""
    await conn.execute(
        """
        INSERT INTO public.entity_mentions
            (user_id, message_id, person_id, mention_text, resolution_method, confidence)
        VALUES ($1, $2::uuid, $3::uuid, $4, $5, $6)
        ON CONFLICT (message_id, person_id, mention_text) DO NOTHING
        """,
        user_id, message_id, person_id, mention_text, resolution_method, confidence,
    )


# ---------------------------------------------------------------------------
# Main entry point called by ingestion pipeline
# ---------------------------------------------------------------------------

async def process_extracted_entities(
    pool: asyncpg.Pool,
    user_id: str,
    chat_id: str,
    message_id: str,
    content: str,
    entities: List[Dict[str, Any]],
) -> None:
    """
    Process GLiNER/LLM-extracted entities from one message.

    For each Person entity:
    - Exact alias match  → entity_mention (resolution_method='exact_alias', confidence=1.0)
    - LLM high-conf ≥0.9 → entity_mention (resolution_method='llm_coref')
    - LLM low-conf  <0.9 → alias_suggestion (pending HITL)
    - is_new_person=True → alias_suggestion with no suggested_person_id
    """
    if not entities:
        return

    person_entities = [e for e in entities if e.get("label") == "Person"]
    if not person_entities:
        return

    async with pool.acquire() as conn:
        # Fetch message timestamp (needed for local context window)
        msg_record = await conn.fetchrow(
            "SELECT timestamp FROM public.messages WHERE id = $1::uuid", message_id
        )
        if not msg_record:
            return
        timestamp = msg_record["timestamp"]

        # Build global entity registry once per message (cheap — small list)
        registry_str, name_to_id = await _build_global_registry(conn, user_id)
        known_names = list(name_to_id.keys())

        # Fetch local context window once per message
        local_context = await _fetch_local_context(conn, chat_id, timestamp, window=20)

        for entity in person_entities:
            name = entity.get("text", "").strip()
            if not name or len(name) < 2:
                continue

            # ── 1. Exact alias match → write entity_mention immediately ──────
            exact_row = await conn.fetchrow(
                """
                SELECT a.person_id FROM public.aliases a
                WHERE a.user_id = $1 AND lower(a.alias) = lower($2)
                """,
                user_id, name,
            )
            if exact_row:
                await _write_entity_mention(
                    conn, user_id, message_id,
                    str(exact_row["person_id"]), name,
                    "exact_alias", 1.0,
                )
                continue

            # ── 2. LLM resolution with local window + global registry ────────
            prompt = f"""You are resolving an entity mention in a WhatsApp chat.

{registry_str}

LOCAL CONVERSATION CONTEXT (±20 messages):
{local_context}

TASK: The name or reference "{name}" appears in this conversation.
Does it refer to one of the KNOWN PEOPLE listed above, or is it a completely new person?

Respond with JSON only."""

            try:
                result_dict = await llm_service.generate_json(
                    prompt, response_schema=CorefSuggestionResult
                )
                result = CorefSuggestionResult.model_validate(result_dict)
            except Exception as e:
                logger.error("LLM coreference failed for '%s': %s", name, e)
                continue

            # ── 3. High-confidence → write entity_mention directly ───────────
            if not result.is_new_person and result.suggested_canonical_name and result.confidence >= 0.9:
                person_id = name_to_id.get(result.suggested_canonical_name.lower())
                if person_id:
                    await _write_entity_mention(
                        conn, user_id, message_id, person_id, name,
                        "llm_coref", result.confidence,
                    )
                    logger.debug(
                        "llm_coref '%s' → '%s' (conf=%.2f)",
                        name, result.suggested_canonical_name, result.confidence,
                    )
                    continue

            # ── 4. Low-confidence or new person → HITL alias_suggestion ─────
            # Check if a pending suggestion already exists to avoid duplicates
            existing = await conn.fetchrow(
                """
                SELECT id FROM public.alias_suggestions
                WHERE user_id = $1
                  AND lower(suggested_alias) = lower($2)
                  AND status = 'pending'
                """,
                user_id, name,
            )

            if existing:
                # Append evidence message id to the existing suggestion
                await conn.execute(
                    """
                    UPDATE public.alias_suggestions
                    SET evidence_message_ids = array_append(evidence_message_ids, $3::uuid)
                    WHERE id = $4
                      AND NOT ($3::uuid = ANY(evidence_message_ids))
                    """,
                    user_id, name, message_id, existing["id"],
                )
            else:
                suggested_person_id = None
                if not result.is_new_person and result.suggested_canonical_name:
                    suggested_person_id = name_to_id.get(
                        result.suggested_canonical_name.lower()
                    )

                # Context snippet: first 500 chars of the local window is enough for review
                snippet = local_context[:500] + "…" if len(local_context) > 500 else local_context

                await conn.execute(
                    """
                    INSERT INTO public.alias_suggestions
                        (user_id, suggested_alias, suggested_person_id,
                         confidence, evidence_message_ids, context_snippet)
                    VALUES ($1, $2, $3, $4, ARRAY[$5::uuid], $6)
                    """,
                    user_id, name, suggested_person_id,
                    float(result.confidence), message_id, snippet,
                )
                logger.info(
                    "HITL suggestion queued: '%s' → '%s' (conf=%.2f, new=%s)",
                    name, result.suggested_canonical_name,
                    result.confidence, result.is_new_person,
                )

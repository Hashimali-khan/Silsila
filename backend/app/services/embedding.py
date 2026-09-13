import logging
from typing import List, Dict, Any, Optional, Tuple
import voyageai
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from app.config import settings
import asyncpg

logger = logging.getLogger(__name__)

# Note: Voyage AI batch limit for voyage-4 is 128 texts
BATCH_SIZE = 128
VOYAGE_BUDGET = getattr(settings, "voyage_token_budget", 200_000_000)

class EmbeddingError(Exception):
    pass

class VoyageAIClient:
    def __init__(self):
        self.api_key = getattr(settings, "voyage_api_key", None)
        self.model = getattr(settings, "voyage_model", "voyage-4")
        if not self.api_key:
            logger.warning("VOYAGE_API_KEY is not set. Embeddings will fail.")
            self.client = None
        else:
            self.client = voyageai.AsyncClient(api_key=self.api_key)

    @retry(
        wait=wait_exponential(multiplier=2, min=2, max=8),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def embed_batch(self, texts: List[str]) -> Tuple[List[List[float]], int]:
        """
        Embeds a batch of texts using Voyage AI.
        Returns a tuple of (embeddings, total_tokens_used).
        Retries on failure (e.g., 429 Rate Limit) with exponential backoff.
        """
        if not self.client:
            raise EmbeddingError("VOYAGE_API_KEY is not configured.")

        if not texts:
            return [], 0

        # Enforce batch limit (just in case)
        if len(texts) > BATCH_SIZE:
            logger.warning(f"Batch size {len(texts)} exceeds max {BATCH_SIZE}. Truncating.")
            texts = texts[:BATCH_SIZE]

        try:
            response = await self.client.embed(
                texts,
                model=self.model,
                input_type="document"
            )
            return response.embeddings, response.total_tokens
        except Exception as e:
            logger.error(f"Voyage AI embedding error: {e}")
            raise EmbeddingError(f"Embedding failed: {e}") from e

async def record_token_usage(conn: asyncpg.Connection, user_id: str, job_id: str, tokens_used: int) -> int:
    """
    Records token usage in the voyage_token_ledger table.
    Returns the new cumulative total for the system (across all users).
    """
    # 1. Get current cumulative total
    record = await conn.fetchrow(
        "SELECT cumulative FROM public.voyage_token_ledger ORDER BY recorded_at DESC LIMIT 1"
    )
    current_cumulative = record["cumulative"] if record else 0
    new_cumulative = current_cumulative + tokens_used

    # 2. Insert new ledger entry
    await conn.execute(
        """
        INSERT INTO public.voyage_token_ledger (user_id, job_id, tokens_used, cumulative)
        VALUES ($1, $2, $3, $4)
        """,
        user_id, job_id, tokens_used, new_cumulative
    )

    # 3. Check milestone alerts (ADR §5)
    if current_cumulative < 150_000_000 and new_cumulative >= 150_000_000:
        logger.warning(f"🚨 VOYAGE AI TOKEN BUDGET ALERT: 150M tokens used out of 200M budget!")
    elif current_cumulative < VOYAGE_BUDGET and new_cumulative >= VOYAGE_BUDGET:
        logger.error(f"🚨 VOYAGE AI TOKEN BUDGET EXHAUSTED: Over {VOYAGE_BUDGET} tokens used!")

    return new_cumulative

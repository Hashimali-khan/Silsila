import asyncio
import logging
import json
from typing import Optional, Dict, Any, Callable, Awaitable
import asyncpg
from datetime import datetime, timezone
import traceback

from app.db.connection import get_pool

logger = logging.getLogger(__name__)

async def enqueue_job(user_id: str, chat_id: Optional[str], metadata: Dict[str, Any]) -> str:
    """Enqueues a job into the ingestion_jobs table returning the job_id."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        job_id = await conn.fetchval(
            """INSERT INTO public.ingestion_jobs (user_id, chat_id, status, metadata)
               VALUES ($1, $2, 'pending', $3)
               RETURNING id""",
            user_id, chat_id, json.dumps(metadata)
        )
        return str(job_id)

class JobQueueWorker:
    def __init__(self, process_func: Callable[[str, str, Dict[str, Any]], Awaitable[None]]):
        self.process_func = process_func
        self.is_running = False
        self._task = None

    async def _fetch_and_lock_job(self, conn: asyncpg.Connection) -> Optional[asyncpg.Record]:
        """Atomically fetch and lock a pending job using SKIP LOCKED."""
        return await conn.fetchrow(
            """
            UPDATE public.ingestion_jobs
            SET status = 'processing',
                updated_at = NOW()
            WHERE id = (
                SELECT id FROM public.ingestion_jobs
                WHERE status IN ('pending', 'processing')
                ORDER BY created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING id, user_id, metadata
            """
        )

    async def start(self):
        self.is_running = True
        logger.info("Worker started, waiting for jobs...")
        pool = await get_pool()

        while self.is_running:
            try:
                async with pool.acquire() as conn:
                    # Explicit transaction so the lock holds
                    async with conn.transaction():
                        job = await self._fetch_and_lock_job(conn)
                        if job:
                            job_id = str(job['id'])
                            user_id = str(job['user_id'])
                            metadata_str = job['metadata']
                            metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else (metadata_str or {})
                            
                            logger.info(f"Acquired lock for job {job_id}")
                            try:
                                await self.process_func(job_id, user_id, metadata)
                                # The process_func is responsible for marking as complete or failed.
                                # But we'll just log success here.
                                logger.info(f"Successfully processed job {job_id}")
                            except Exception as e:
                                logger.error(f"Failed to process job {job_id}: {e}\n{traceback.format_exc()}")
                                await conn.execute(
                                    """UPDATE public.ingestion_jobs
                                       SET status = 'failed', error_message = $2,
                                           completed_at = NOW()
                                       WHERE id = $1""",
                                    job_id, str(e)[:2000]
                                )
                        else:
                            # No jobs found, wait before polling again
                            await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                await asyncio.sleep(5)

    async def stop(self):
        self.is_running = False
        logger.info("Worker gracefully stopped.")

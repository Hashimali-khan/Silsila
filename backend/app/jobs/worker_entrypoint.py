import asyncio
import logging
import signal
import sys
import os

# Ensure the app package is in the Python path when running this script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.jobs.queue import JobQueueWorker
from app.workers.ingestion import run_ingestion
from app.db.connection import get_pool

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

async def process_job_wrapper(job_id: str, user_id: str, metadata: dict):
    """Wrapper to map queue metadata to the ingestion function."""
    # Assuming file_content and file_name are temporarily stored elsewhere or passed differently,
    # but for this MVP we'll extract them from metadata if provided, though typically
    # large files should be fetched from GCS/S3.
    file_content = metadata.get("file_content", "")
    file_name = metadata.get("file_name", "chat.txt")
    await run_ingestion(job_id, user_id, file_content, file_name)

async def main():
    pool = await get_pool()
    worker = JobQueueWorker(process_func=process_job_wrapper)

    # Graceful shutdown handler
    def shutdown_handler():
        logger.info("Received shutdown signal. Stopping worker...")
        asyncio.create_task(worker.stop())

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown_handler)

    try:
        await worker.start()
    except asyncio.CancelledError:
        pass
    finally:
        await pool.close()
        logger.info("Worker shutdown complete.")

if __name__ == "__main__":
    asyncio.run(main())

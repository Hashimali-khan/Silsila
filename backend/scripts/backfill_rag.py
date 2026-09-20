import sys
sys.path.insert(0, ".")
import asyncio
import uuid
import logging
from app.db.connection import get_pool, set_rls_user
from app.services.thread_detector import detect_threads, get_thread_stats
from app.services.chunk_builder import process_chat_chunks
from app.services.embedding import VoyageAIClient
from app.services.qdrant_client import qdrant_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backfill")

async def run():
    pool = await get_pool()
    async with pool.acquire() as conn:
        chat = await conn.fetchrow("SELECT id, user_id, name, message_count FROM public.chats LIMIT 1")
        if not chat:
            logger.error("No chat found")
            return
        chat_id = str(chat["id"])
        user_id = chat["user_id"]
        logger.info(f"Target Chat: {chat['name']} (ID: {chat_id}), User: {user_id}")

        await set_rls_user(conn, user_id)

        # 1. Fetch all messages
        logger.info("Fetching messages from Postgres...")
        msg_rows = await conn.fetch(
            """
            SELECT id, user_id, chat_id, person_id, sender_name, timestamp, content,
                   is_system_msg, is_media, metadata
            FROM public.messages
            WHERE chat_id = $1::uuid
            ORDER BY timestamp ASC
            """,
            chat_id
        )
        logger.info(f"Loaded {len(msg_rows)} messages.")

        # Convert to dicts for detect_threads
        messages = []
        for r in msg_rows:
            d = dict(r)
            d["_db_id"] = str(d["id"])
            messages.append(d)

        non_system = [m for m in messages if not m["is_system_msg"]]

        # 2. Clear old threads & chunks if any partial ones exist
        await conn.execute("DELETE FROM public.conversation_threads WHERE chat_id = $1::uuid", chat_id)
        await conn.execute("DELETE FROM public.message_chunks WHERE chat_id = $1::uuid", chat_id)

        # 3. Detect threads
        logger.info("Detecting conversation threads...")
        threads = detect_threads(non_system)
        logger.info(f"Detected {len(threads)} threads: {get_thread_stats(threads)}")

        thread_records = []
        junction_records = []
        thread_ids = []
        threads_msgs = []

        for thread_msgs in threads:
            if not thread_msgs:
                continue
            tid = str(uuid.uuid4())
            thread_ids.append(tid)
            threads_msgs.append(thread_msgs)

            start_ts = thread_msgs[0]["timestamp"]
            end_ts = thread_msgs[-1]["timestamp"]
            thread_records.append((
                tid, user_id, chat_id, start_ts, end_ts, len(thread_msgs)
            ))
            for msg in thread_msgs:
                if msg.get("_db_id"):
                    junction_records.append((msg["_db_id"], tid))

        logger.info("Bulk inserting conversation_threads...")
        await conn.copy_records_to_table(
            "conversation_threads",
            records=thread_records,
            columns=["id", "user_id", "chat_id", "start_time", "end_time", "message_count"],
            schema_name="public",
        )

        logger.info(f"Bulk inserting {len(junction_records)} message_threads junctions...")
        await conn.copy_records_to_table(
            "message_threads",
            records=junction_records,
            columns=["message_id", "thread_id"],
            schema_name="public",
        )

        # 4. Generate Chunks
        logger.info("Building message chunks...")
        chunks = await process_chat_chunks(conn, user_id, chat_id, threads_msgs, thread_ids)
        logger.info(f"Created {len(chunks)} chunks in Postgres!")

    # 5. Embed with Voyage AI & upsert to Qdrant
    if chunks:
        logger.info(f"Initializing Qdrant and Voyage for {len(chunks)} chunks...")
        voyage_client = VoyageAIClient()
        await qdrant_service.ensure_collection()

        CHUNK_BATCH_SIZE = 128
        total_batches = (len(chunks) + CHUNK_BATCH_SIZE - 1) // CHUNK_BATCH_SIZE

        for idx, i in enumerate(range(0, len(chunks), CHUNK_BATCH_SIZE)):
            batch = chunks[i : i + CHUNK_BATCH_SIZE]
            texts = [c["content"] for c in batch]
            logger.info(f"Embedding batch {idx + 1}/{total_batches} ({len(batch)} chunks)...")

            embeddings, tokens = await voyage_client.embed_batch(texts)
            for c in batch:
                c["user_id"] = user_id
                c["chat_id"] = chat_id

            await qdrant_service.batch_upsert(batch, embeddings)
            logger.info(f"Upserted batch {idx + 1}/{total_batches} to Qdrant successfully!")

    logger.info("=== BACKFILL COMPLETE! Full RAG is now live! ===")

if __name__ == "__main__":
    asyncio.run(run())

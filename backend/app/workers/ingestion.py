"""Ingestion background pipeline — Phase 1.

Full pipeline: Parse → People → Chat → Messages → Threads → Stats
All progress persisted to ingestion_jobs table (ADR §11 idempotency).
Survives Heroku Eco dyno restarts mid-job.

Steps:
  1. parsing     — WhatsApp parser
  2. creating    — create Chat + People rows
  3. storing     — bulk insert messages (asyncpg copy)
  4. threading   — adaptive thread detection
  5. stats       — update message/people counts
  6. complete    — mark job done

Phase 2 will add:  chunking → embedding (Voyage) → qdrant upsert
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

import asyncpg

from app.db.connection import get_pool, set_rls_user
from app.services.whatsapp_parser import parse_whatsapp_export, extract_unique_senders
from app.services.thread_detector import detect_threads, get_thread_stats
from app.services.chunk_builder import process_chat_chunks
from app.services.embedding import VoyageAIClient, record_token_usage
from app.services.qdrant_client import qdrant_service
from app.services.entity_extractor import entity_extractor
from app.services.coreference import process_extracted_entities
from app.services.graph_builder import build_person_profile
from app.workers.analytics import process_chat_sentiment_background

logger = logging.getLogger(__name__)


# ── Job status helpers ────────────────────────────────────────────────────────

async def _update_job(
    pool: asyncpg.Pool,
    job_id: str,
    user_id: str,
    **fields,
) -> None:
    """Update ingestion_jobs row. Called after each pipeline step."""
    set_clauses = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(fields))
    values = list(fields.values())
    await pool.execute(
        f"UPDATE public.ingestion_jobs SET {set_clauses} WHERE id = $1",
        job_id,
        *values,
    )


async def _fail_job(pool: asyncpg.Pool, job_id: str, error: str) -> None:
    await pool.execute(
        """UPDATE public.ingestion_jobs
           SET status = 'failed', error_message = $2,
               current_step = 'failed', completed_at = NOW()
           WHERE id = $1""",
        job_id,
        error[:2000],  # truncate to fit column
    )


# ── Main pipeline ─────────────────────────────────────────────────────────────

async def run_ingestion(
    job_id: str,
    user_id: str,
    file_content: str,
    file_name: str,
) -> None:
    """
    Run the full ingestion pipeline as a background task.

    Uses RLS-bypass via service role approach: we bypass RLS for the
    ingestion worker by using the pool directly and setting app.user_id
    so all queries are correctly scoped.

    Progress is written to ingestion_jobs after every step, so a dyno
    restart can resume from the last completed step.
    """
    pool = await get_pool()
    logger.info("Ingestion job %s started for user %s", job_id, user_id)

    try:
        # ── STEP 1: Parse ────────────────────────────────────────────────────
        await _update_job(pool, job_id, user_id,
                          status="parsing", current_step="parsing",
                          started_at=datetime.now(timezone.utc))

        messages = parse_whatsapp_export(file_content)
        if not messages:
            await _fail_job(pool, job_id, "No messages found. Is this a valid WhatsApp export?")
            return

        non_system = [m for m in messages if not m["is_system_msg"]]
        senders = extract_unique_senders(non_system)

        await _update_job(pool, job_id, user_id,
                          total_messages=len(non_system))

        logger.info("Job %s: parsed %d messages, %d senders", job_id, len(non_system), len(senders))

        # ── STEP 2: Create People + Chat ─────────────────────────────────────
        await _update_job(pool, job_id, user_id, current_step="creating")

        async with pool.acquire() as conn:
            # Set RLS context for this connection
            await set_rls_user(conn, user_id)

            # Ensure profile exists (upsert)
            await conn.execute(
                """INSERT INTO public.profiles (id) VALUES ($1)
                   ON CONFLICT (id) DO NOTHING""",
                user_id,
            )

            # Create people rows + alias map
            person_map: dict[str, str] = {}  # sender_name → person_id
            for sender in senders:
                person_id = str(uuid.uuid4())
                await conn.execute(
                    """INSERT INTO public.people
                       (id, user_id, canonical_name, first_seen_at, last_seen_at)
                       VALUES ($1, $2, $3, $4, $5)
                       ON CONFLICT DO NOTHING""",
                    person_id,
                    user_id,
                    sender,
                    min((m["timestamp"] for m in messages if m["sender_name"] == sender), default=None),
                    max((m["timestamp"] for m in messages if m["sender_name"] == sender), default=None),
                )
                # Create canonical alias
                await conn.execute(
                    """INSERT INTO public.aliases (user_id, person_id, alias, confidence)
                       VALUES ($1, $2, $3, 1.0) ON CONFLICT DO NOTHING""",
                    user_id, person_id, sender,
                )
                person_map[sender] = person_id

            # Derive chat name from file name or senders
            chat_name = file_name.replace(".txt", "").replace(".zip", "").strip()
            if not chat_name:
                chat_name = " & ".join(senders[:3])

            timestamps = [m["timestamp"] for m in non_system]
            chat_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO public.chats
                   (id, user_id, name, participant_count, message_count,
                    first_message_at, last_message_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                chat_id,
                user_id,
                chat_name,
                len(senders),
                len(non_system),
                min(timestamps),
                max(timestamps),
            )
            # Link job to chat
            await pool.execute(
                "UPDATE public.ingestion_jobs SET chat_id = $2 WHERE id = $1",
                job_id, chat_id,
            )

        logger.info("Job %s: created chat %s with %d people", job_id, chat_id, len(senders))

        # ── STEP 3: Bulk Insert Messages ─────────────────────────────────────
        await _update_job(pool, job_id, user_id, current_step="storing")

        BATCH_SIZE = 500
        total_inserted = 0

        async with pool.acquire() as conn:
            await set_rls_user(conn, user_id)

            for i in range(0, len(non_system), BATCH_SIZE):
                batch = non_system[i : i + BATCH_SIZE]
                records = []
                for msg in batch:
                    msg_id = str(uuid.uuid4())
                    person_id = person_map.get(msg["sender_name"])
                    records.append((
                        msg_id,
                        user_id,
                        chat_id,
                        person_id,
                        msg["sender_name"],
                        msg["timestamp"],
                        msg["content"],
                        msg["is_system_msg"],
                        msg["is_media"],
                        json.dumps({"is_deleted": msg["is_deleted"]}),
                    ))
                    # Store msg_id back for thread step
                    msg["_db_id"] = msg_id

                await conn.copy_records_to_table(
                    "messages",
                    records=records,
                    columns=[
                        "id", "user_id", "chat_id", "person_id",
                        "sender_name", "timestamp", "content",
                        "is_system_msg", "is_media", "metadata",
                    ],
                    schema_name="public",
                )
                total_inserted += len(batch)
                await _update_job(pool, job_id, user_id,
                                  processed_messages=total_inserted)

        logger.info("Job %s: inserted %d messages", job_id, total_inserted)

        # ── STEP 4: Thread Detection ──────────────────────────────────────────
        await _update_job(pool, job_id, user_id, current_step="threading")

        threads = detect_threads(non_system)
        stats = get_thread_stats(threads)
        logger.info("Job %s: %s", job_id, stats)

        thread_records = []
        junction_records = []

        for thread_msgs in threads:
            if not thread_msgs:
                continue
            thread_id = str(uuid.uuid4())
            start_ts = thread_msgs[0]["timestamp"]
            end_ts = thread_msgs[-1]["timestamp"]

            thread_records.append((
                thread_id, user_id, chat_id, start_ts, end_ts, len(thread_msgs)
            ))

            for msg in thread_msgs:
                if msg.get("_db_id"):
                    junction_records.append((msg["_db_id"], thread_id))

        async with pool.acquire() as conn:
            await set_rls_user(conn, user_id)

            if thread_records:
                await conn.copy_records_to_table(
                    "conversation_threads",
                    records=thread_records,
                    columns=["id", "user_id", "chat_id", "start_time", "end_time", "message_count"],
                    schema_name="public",
                )

            if junction_records:
                await conn.copy_records_to_table(
                    "message_threads",
                    records=junction_records,
                    columns=["message_id", "thread_id"],
                    schema_name="public",
                )

        # ── STEP 5: Update People Stats ───────────────────────────────────────
        await _update_job(pool, job_id, user_id, current_step="stats")

        async with pool.acquire() as conn:
            await set_rls_user(conn, user_id)
            for sender, person_id in person_map.items():
                sender_msgs = [m for m in non_system if m["sender_name"] == sender]
                await conn.execute(
                    """UPDATE public.people
                       SET message_count = $2, first_seen_at = $3, last_seen_at = $4
                       WHERE id = $1""",
                    person_id,
                    len(sender_msgs),
                    min(m["timestamp"] for m in sender_msgs),
                    max(m["timestamp"] for m in sender_msgs),
                )

            # Compute basic stats and store in analysis_cache
            msg_per_sender = {s: sum(1 for m in non_system if m["sender_name"] == s) for s in senders}
            basic_stats_data = {
                "total_messages": len(non_system),
                "thread_count": len(threads),
                "participants": senders,
                "messages_per_sender": msg_per_sender,
                "date_range": {
                    "start": min(timestamps).isoformat(),
                    "end": max(timestamps).isoformat(),
                },
            }
            await conn.execute(
                """INSERT INTO public.analysis_cache
                   (user_id, chat_id, metric_type, data)
                   VALUES ($1, $2, 'basic_stats', $3::jsonb)
                   ON CONFLICT DO NOTHING""",
                user_id,
                chat_id,
                json.dumps(basic_stats_data),
            )

        # ── STEP 5.1: Chunking ────────────────────────────────────────────────
        await _update_job(pool, job_id, user_id, current_step="chunking")
        
        async with pool.acquire() as conn:
            await set_rls_user(conn, user_id)
            
            # Get all threads and messages for this chat
            thread_records = await conn.fetch("SELECT id FROM public.conversation_threads WHERE chat_id = $1 ORDER BY start_time ASC", chat_id)
            thread_ids = [r["id"] for r in thread_records]
            
            threads_msgs = []
            for tid in thread_ids:
                msg_records = await conn.fetch(
                    """
                    SELECT m.*, m.id as _db_id
                    FROM public.messages m
                    JOIN public.message_threads mt ON m.id = mt.message_id
                    WHERE mt.thread_id = $1
                    ORDER BY m.timestamp ASC
                    """, tid
                )
                threads_msgs.append([dict(r) for r in msg_records])
                
            chunks = await process_chat_chunks(conn, user_id, chat_id, threads_msgs, [str(tid) for tid in thread_ids])
            await _update_job(pool, job_id, user_id, total_chunks=len(chunks))
            logger.info("Job %s: created %d chunks", job_id, len(chunks))

        # ── STEP 5.2: Embedding & Qdrant Upsert ───────────────────────────────
        if chunks:
            await _update_job(pool, job_id, user_id, current_step="embedding")
            
            voyage_client = VoyageAIClient()
            await qdrant_service.ensure_collection()
            
            CHUNK_BATCH_SIZE = 128
            embedded_chunks = 0
            
            async with pool.acquire() as conn:
                await set_rls_user(conn, user_id)
                for i in range(0, len(chunks), CHUNK_BATCH_SIZE):
                    batch = chunks[i : i + CHUNK_BATCH_SIZE]
                    texts = [c["content"] for c in batch]
                    
                    try:
                        embeddings, tokens = await voyage_client.embed_batch(texts)
                        await record_token_usage(conn, user_id, job_id, tokens)
                        
                        # Add metadata for Qdrant
                        for c in batch:
                            c["user_id"] = user_id
                            c["chat_id"] = chat_id
                            
                        await qdrant_service.batch_upsert(batch, embeddings)
                        
                        embedded_chunks += len(batch)
                        await _update_job(pool, job_id, user_id, embedded_chunks=embedded_chunks)
                    except Exception as e:
                        logger.error(f"Failed to embed and upsert chunk batch: {e}")
                        # Depending on resilience requirements, might want to fail the job or continue
                        raise

            logger.info("Job %s: embedded and upserted %d chunks", job_id, embedded_chunks)

        # ── STEP 5.3: Entity Extraction ───────────────────────────────────────
        await _update_job(pool, job_id, user_id, current_step="entity_extraction")

        async with pool.acquire() as conn:
            await set_rls_user(conn, user_id)
            
            # We process non_system messages in batches
            EXTRACT_BATCH_SIZE = 10
            extracted_messages = 0
            
            for i in range(0, len(non_system), EXTRACT_BATCH_SIZE):
                batch = non_system[i : i + EXTRACT_BATCH_SIZE]
                
                # Filter batch to only messages that pass the heuristic
                flagged_messages = []
                for msg in batch:
                    if entity_extractor.heuristic_scan(msg["content"]):
                        flagged_messages.append(msg)
                        
                if not flagged_messages:
                    continue
                    
                # Extract entities for the flagged messages
                texts = [m["content"] for m in flagged_messages]
                batch_entities = await entity_extractor.extract_entities_batch(texts)
                
                # Process the extracted entities
                for msg, entities in zip(flagged_messages, batch_entities):
                    if entities:
                        await process_extracted_entities(
                            pool=pool, 
                            user_id=user_id, 
                            chat_id=chat_id, 
                            message_id=msg["_db_id"], 
                            content=msg["content"], 
                            entities=entities
                        )
                
                extracted_messages += len(flagged_messages)
                
            logger.info("Job %s: extracted entities from %d flagged messages", job_id, extracted_messages)

        # ── STEP 5.4: Build People Profiles ───────────────────────────────────
        await _update_job(pool, job_id, user_id, current_step="people_profiles")
        
        # We don't need a connection here as build_person_profile manages its own
        for sender, person_id in person_map.items():
            try:
                await build_person_profile(pool, user_id, person_id, chat_id)
            except Exception as e:
                logger.error("Job %s: failed to build profile for person %s: %s", job_id, person_id, e)

        # ── STEP 6: Complete ──────────────────────────────────────────────────
        await _update_job(
            pool,
            job_id,
            user_id,
            status="complete",
            current_step="complete",
            completed_at=datetime.now(timezone.utc),
            processed_messages=total_inserted,
        )
        logger.info("Job %s: complete. chat_id=%s", job_id, chat_id)
        
        # ── STEP 7: Trigger Phase 4 Analytics ─────────────────────────────────
        # Run slowly in the background without holding up this ingestion task
        asyncio.create_task(process_chat_sentiment_background(chat_id, user_id))

    except Exception as exc:
        logger.exception("Job %s failed: %s", job_id, exc)
        await _fail_job(pool, job_id, str(exc))

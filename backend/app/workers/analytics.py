import asyncio
import logging
from app.db.connection import get_db_pool
from app.services.sentiment import sentiment_service
from app.services.event_detector import event_detector
from app.db.queries.sentiment import (
    get_unprocessed_messages_for_sentiment,
    insert_emotion_labels
)
from app.db.queries.events import insert_events

logger = logging.getLogger(__name__)

async def process_chat_sentiment_background(chat_id: str, user_id: str):
    """
    Background worker that slowly processes sentiment for a chat.
    It takes batches of messages and processes them with deliberate delays
    to avoid hitting LLM API rate limits.
    """
    logger.info(f"Starting background sentiment analysis for chat {chat_id}")
    pool = await get_db_pool()
    
    BATCH_SIZE = 20
    # Wait 10 seconds between batches to respect rate limits (Gemini free tier has 15 RPM)
    DELAY_BETWEEN_BATCHES_SEC = 10 
    
    # We use a standalone connection for the background loop to avoid holding
    # a pool connection for too long, or we just acquire it per batch.
    
    processed_total = 0
    while True:
        try:
            async with pool.acquire() as conn:
                # Need to set RLS context since we are a background task!
                await conn.execute("SET LOCAL app.user_id = $1", user_id)
                
                messages = await get_unprocessed_messages_for_sentiment(
                    conn, chat_id, limit=BATCH_SIZE
                )
                
            if not messages:
                logger.info(f"Finished sentiment analysis for chat {chat_id}. Total processed: {processed_total}")
                break
                
            # Process the batch using Gemini
            labels = await sentiment_service.analyze_sentiment_batch(messages)
            
            if labels:
                async with pool.acquire() as conn:
                    await conn.execute("SET LOCAL app.user_id = $1", user_id)
                    await insert_emotion_labels(conn, user_id, labels)
                    processed_total += len(labels)
                    logger.info(f"Inserted {len(labels)} emotion labels for chat {chat_id}")
            else:
                logger.warning(f"No labels returned for batch in chat {chat_id}, might be a rate limit or error.")
                # If we got no labels, maybe we hit an error. Let's delay longer to backoff.
                await asyncio.sleep(DELAY_BETWEEN_BATCHES_SEC * 2)
                continue
                
            # Deliberate delay to avoid rate limits
            await asyncio.sleep(DELAY_BETWEEN_BATCHES_SEC)
            
        except asyncio.CancelledError:
            logger.info(f"Sentiment analysis for chat {chat_id} was cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in background sentiment analysis for chat {chat_id}: {e}")
            # Backoff on error
            await asyncio.sleep(30)
            
    # Now run Event Detection across the entire chat
    logger.info(f"Starting event detection for chat {chat_id}")
    try:
        async with pool.acquire() as conn:
            await conn.execute("SET LOCAL app.user_id = $1", user_id)
            
            # Fetch all messages with emotions in chronological order
            rows = await conn.fetch(
                """
                SELECT m.id, m.sender_name, m.timestamp, m.content, e.emotion
                FROM public.messages m
                JOIN public.emotion_labels e ON m.id = e.message_id
                WHERE m.chat_id = $1::uuid
                  AND m.is_system_msg = FALSE
                  AND m.is_media = FALSE
                ORDER BY m.timestamp ASC
                """,
                chat_id
            )
            
            messages_with_emotions = [dict(r) for r in rows]
            
            if messages_with_emotions:
                detected_events = event_detector.detect_events(messages_with_emotions)
                if detected_events:
                    await insert_events(conn, user_id, chat_id, detected_events)
                    logger.info(f"Inserted {len(detected_events)} events for chat {chat_id}")
                else:
                    logger.info(f"No events detected for chat {chat_id}")
    except Exception as e:
        logger.error(f"Error in event detection for chat {chat_id}: {e}")

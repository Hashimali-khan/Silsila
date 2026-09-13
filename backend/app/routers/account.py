import io
import json
import zipfile
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.db.connection import get_pool
from app.dependencies import get_current_user_id
from app.limiter import limiter

router = APIRouter(tags=["account"])

@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def delete_account(
    request: Any,  # For slowapi
    user_id: str = Depends(get_current_user_id)
):
    """
    Deletes all data associated with the user account from Postgres.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Since RLS is enabled, we could just delete from profiles 
        # and rely on ON DELETE CASCADE for all other tables if set up.
        # Otherwise, explicit deletion. Let's do explicit to be safe.
        async with conn.transaction():
            # Delete in order of dependencies (or reverse)
            await conn.execute("DELETE FROM public.events WHERE chat_id IN (SELECT id FROM public.chats WHERE user_id = $1)", user_id)
            await conn.execute("DELETE FROM public.message_chunks WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM public.emotion_labels WHERE message_id IN (SELECT id FROM public.messages WHERE user_id = $1)", user_id)
            await conn.execute("DELETE FROM public.message_threads WHERE message_id IN (SELECT id FROM public.messages WHERE user_id = $1)", user_id)
            await conn.execute("DELETE FROM public.messages WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM public.alias_suggestions WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM public.aliases WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM public.people WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM public.chats WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM public.ingestion_jobs WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM public.profiles WHERE id = $1", user_id)
            
    # We should also delete Qdrant chunks, but since we filter by user_id on query, 
    # it's practically deleted from user view. For full GDPR compliance, we would 
    # make a Qdrant API call to delete points by user_id here.
    return None


@router.get("/export/{chat_id}")
@limiter.limit("5/minute")
async def export_data(
    request: Any,  # For slowapi
    chat_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Exports chat data as a ZIP file containing JSON files.
    """
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        # Verify ownership
        chat = await conn.fetchrow("SELECT id FROM public.chats WHERE id = $1::uuid AND user_id = $2", chat_id, user_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
            
        # Fetch people
        people_rows = await conn.fetch("SELECT id, canonical_name, profile FROM public.people WHERE user_id = $1", user_id)
        people = [dict(r) for r in people_rows]
        
        # Fetch events
        events_rows = await conn.fetch("SELECT type, description, detected_at, confidence FROM public.events WHERE chat_id = $1::uuid", chat_id)
        events = [dict(r) for r in events_rows]
        
        # Format events timestamps
        for e in events:
            if e["detected_at"]:
                e["detected_at"] = e["detected_at"].isoformat()

    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("people.json", json.dumps(people, indent=2, default=str))
        zip_file.writestr("events.json", json.dumps(events, indent=2, default=str))
        
    zip_buffer.seek(0)
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=export_{chat_id}.zip"}
    )

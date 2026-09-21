"""Parse router — WhatsApp file upload endpoint + SSE job progress stream."""

import asyncio
import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, status, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.db.connection import get_pool, set_rls_user
from app.dependencies import get_current_user_id
from app.workers.ingestion import run_ingestion
from app.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024   # 50 MB
MAX_LINES = 500_000


class UploadResponse(BaseModel):
    job_id: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    current_step: str
    total_messages: int
    processed_messages: int
    error_message: str | None
    chat_id: str | None


@router.post("/parse/whatsapp", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def upload_whatsapp(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """
    Accept a WhatsApp .txt export file, create an ingestion job, and
    start background processing. Returns immediately with job_id.

    The frontend should poll GET /api/parse/jobs/{job_id} or subscribe
    to server-sent events for real-time progress.
    """
    # ── Validation ────────────────────────────────────────────────────────────
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    ext = file.filename.lower().rsplit(".", 1)[-1]
    if ext not in ("txt", "zip"):
        raise HTTPException(
            status_code=400,
            detail="Only .txt or .zip WhatsApp exports are supported.",
        )

    content_bytes = await file.read()

    if len(content_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 50 MB limit.")

    if ext == "zip":
        import zipfile
        import io
        try:
            with zipfile.ZipFile(io.BytesIO(content_bytes)) as z:
                # Find the first .txt file in the zip
                txt_files = [f for f in z.namelist() if f.lower().endswith(".txt")]
                if not txt_files:
                    raise HTTPException(status_code=422, detail="No .txt file found inside the ZIP archive.")
                # Read the first .txt file (WhatsApp usually names it _chat.txt)
                content_bytes = z.read(txt_files[0])
                if len(content_bytes) > MAX_FILE_SIZE_BYTES:
                    raise HTTPException(status_code=413, detail="Extracted file exceeds the 50 MB limit.")
        except zipfile.BadZipFile:
            raise HTTPException(status_code=422, detail="Invalid ZIP file.")

    # Validate UTF-8 (reject binary files disguised as .txt)
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            content = content_bytes.decode("utf-16")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=422,
                detail="File is not valid text. Is this a genuine WhatsApp export?",
            )

    line_count = content.count("\n")
    if line_count > MAX_LINES:
        raise HTTPException(
            status_code=422,
            detail=f"File has {line_count:,} lines. Maximum is {MAX_LINES:,}.",
        )

    # ── Create ingestion job ──────────────────────────────────────────────────
    pool = await get_pool()
    job_id = str(uuid.uuid4())

    async with pool.acquire() as conn:
        await set_rls_user(conn, user_id)
        await conn.execute(
            """INSERT INTO public.ingestion_jobs
               (id, user_id, status, file_name, current_step, created_at)
               VALUES ($1, $2, 'pending', $3, 'queued', $4)""",
            job_id,
            user_id,
            file.filename,
            datetime.now(timezone.utc),
        )

    # ── Kick off background pipeline ──────────────────────────────────────────
    background_tasks.add_task(
        run_ingestion,
        job_id=job_id,
        user_id=user_id,
        file_content=content,
        file_name=file.filename,
    )

    logger.info("Created ingestion job %s for user %s (%s)", job_id, user_id, file.filename)
    return UploadResponse(
        job_id=job_id,
        message="Processing started. Poll /api/parse/jobs/{job_id} for progress.",
    )


@router.get("/parse/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Fetch current ingestion job status (polling fallback)."""
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format.")

    pool = await get_pool()
    async with pool.acquire() as conn:
        await set_rls_user(conn, user_id)
        row = await conn.fetchrow(
            """SELECT id::text AS job_id, status, current_step, total_messages,
                      processed_messages, error_message,
                      chat_id::text
               FROM public.ingestion_jobs
               WHERE id = $1::uuid AND user_id = $2""",
            job_id,
            user_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobStatusResponse(**dict(row))


@router.get("/parse/jobs/{job_id}/stream")
async def stream_job_progress(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """
    Server-Sent Events stream for real-time ingestion progress.

    Emits a JSON event every second with current job status until
    the job reaches 'complete' or 'failed'. The frontend subscribes
    to this endpoint for live progress bar updates.

    Event format:  data: {status, current_step, total_messages, processed_messages, chat_id}
    """
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format.")

    pool = await get_pool()

    # Verify job ownership before streaming
    async with pool.acquire() as conn:
        await set_rls_user(conn, user_id)
        row = await conn.fetchrow(
            "SELECT id FROM public.ingestion_jobs WHERE id = $1::uuid AND user_id = $2",
            job_id,
            user_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found.")

    async def event_generator():
        terminal_states = {"complete", "failed"}
        poll_interval = 1.0  # seconds between DB polls
        max_polls = 600       # timeout after 10 minutes

        for _ in range(max_polls):
            async with pool.acquire() as conn:
                await set_rls_user(conn, user_id)
                record = await conn.fetchrow(
                    """SELECT status, current_step, total_messages,
                              processed_messages, error_message, chat_id::text
                       FROM public.ingestion_jobs
                       WHERE id = $1::uuid""",
                    job_id,
                )
            if not record:
                yield {"event": "error", "data": '{"error": "Job not found"}'}
                return

            import json
            data = json.dumps({
                "status": record["status"],
                "current_step": record["current_step"],
                "total_messages": record["total_messages"],
                "processed_messages": record["processed_messages"],
                "error_message": record["error_message"],
                "chat_id": record["chat_id"],
            })
            yield {"event": "progress", "data": data}

            if record["status"] in terminal_states:
                return

            await asyncio.sleep(poll_interval)

        yield {"event": "error", "data": '{"error": "Stream timeout"}'}

    return EventSourceResponse(event_generator())

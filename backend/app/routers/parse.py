"""Parse router — WhatsApp file upload endpoint."""

import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel

from app.db.connection import get_pool
from app.dependencies import get_current_user_id
from app.workers.ingestion import run_ingestion

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
async def upload_whatsapp(
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

    await pool.execute(
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
    pool = await get_pool()
    row = await pool.fetchrow(
        """SELECT id, status, current_step, total_messages,
                  processed_messages, error_message,
                  chat_id::text
           FROM public.ingestion_jobs
           WHERE id = $1 AND user_id = $2""",
        job_id,
        user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobStatusResponse(**dict(row))

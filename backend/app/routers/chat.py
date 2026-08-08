"""Streaming Q&A chat endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/chat", tags=["Chat"])

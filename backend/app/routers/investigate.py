from fastapi import APIRouter, Depends, Request
from typing import Dict, Any
import asyncpg

from app.db.connection import get_pool, set_rls_user
from app.dependencies import get_current_user
from app.services.graph import build_relationship_graph

router = APIRouter(prefix="/insights", tags=["insights"])

@router.get("/graph/{chat_id}")
async def get_social_graph(
    chat_id: str,
    request: Request,
    user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get the social graph (nodes and edges) for a chat."""
    pool: asyncpg.Pool = request.app.state.pool
    return await build_relationship_graph(pool, user_id, chat_id)

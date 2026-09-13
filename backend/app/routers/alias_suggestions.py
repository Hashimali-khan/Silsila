from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import asyncpg

from app.db.connection import get_pool, set_rls_user
from app.dependencies import get_current_user

router = APIRouter(prefix="/aliases", tags=["aliases"])

class AliasSuggestionResponse(BaseModel):
    id: str
    suggested_alias: str
    suggested_person_id: Optional[str]
    confidence: float
    status: str
    context_snippet: Optional[str]

class ResolveSuggestionRequest(BaseModel):
    action: str # "approve", "reject", "new_person"
    person_id: Optional[str] = None # required if action is "approve" or "new_person" if existing is provided

@router.get("/suggestions", response_model=List[AliasSuggestionResponse])
async def get_suggestions(request: Request, user_id: str = Depends(get_current_user)):
    """Get all pending alias suggestions for the user."""
    pool: asyncpg.Pool = request.app.state.pool
    async with pool.acquire() as conn:
        await set_rls_user(conn, user_id)
        rows = await conn.fetch(
            "SELECT * FROM public.alias_suggestions WHERE status = 'pending' ORDER BY confidence DESC"
        )
        return [dict(r) for r in rows]

@router.post("/suggestions/{suggestion_id}/resolve")
async def resolve_suggestion(
    suggestion_id: str, 
    payload: ResolveSuggestionRequest,
    request: Request, 
    user_id: str = Depends(get_current_user)
):
    """Resolve an alias suggestion (approve, reject, new)."""
    pool: asyncpg.Pool = request.app.state.pool
    async with pool.acquire() as conn:
        await set_rls_user(conn, user_id)
        
        sugg = await conn.fetchrow("SELECT * FROM public.alias_suggestions WHERE id = $1", suggestion_id)
        if not sugg:
            raise HTTPException(status_code=404, detail="Suggestion not found")
            
        if sugg["status"] != "pending":
            raise HTTPException(status_code=400, detail="Suggestion already resolved")
            
        if payload.action == "reject":
            await conn.execute("UPDATE public.alias_suggestions SET status = 'rejected' WHERE id = $1", suggestion_id)
            return {"status": "rejected"}
            
        elif payload.action == "approve":
            target_person_id = payload.person_id or sugg["suggested_person_id"]
            if not target_person_id:
                raise HTTPException(status_code=400, detail="person_id required for approve action")
                
            async with conn.transaction():
                # Add to aliases table
                await conn.execute(
                    """
                    INSERT INTO public.aliases (user_id, person_id, alias, confidence)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT DO NOTHING
                    """,
                    user_id, target_person_id, sugg["suggested_alias"], sugg["confidence"]
                )
                # Mark resolved
                await conn.execute("UPDATE public.alias_suggestions SET status = 'approved' WHERE id = $1", suggestion_id)
            return {"status": "approved"}
            
        elif payload.action == "new_person":
            # Create a new person
            async with conn.transaction():
                person_id = payload.person_id # If frontend pre-generated UUID, else we could gen one
                if not person_id:
                    import uuid
                    person_id = str(uuid.uuid4())
                    
                await conn.execute(
                    "INSERT INTO public.people (id, user_id, canonical_name) VALUES ($1, $2, $3)",
                    person_id, user_id, sugg["suggested_alias"]
                )
                await conn.execute(
                    """
                    INSERT INTO public.aliases (user_id, person_id, alias, confidence)
                    VALUES ($1, $2, $3, $4)
                    """,
                    user_id, person_id, sugg["suggested_alias"], 1.0
                )
                await conn.execute("UPDATE public.alias_suggestions SET status = 'approved' WHERE id = $1", suggestion_id)
            return {"status": "created", "person_id": person_id}
            
        else:
            raise HTTPException(status_code=400, detail="Invalid action")

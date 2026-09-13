import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import asyncpg

from app.db.connection import get_pool
from app.services.llm import llm_service
from app.services.hybrid_search import hybrid_search
from app.db.queries.investigator import (
    get_person_id_by_name,
    get_connections_for_person,
    get_events_for_persons
)

logger = logging.getLogger(__name__)

class TimelineEvent(BaseModel):
    date: str = Field(description="Approximate date of the event")
    description: str = Field(description="What happened")
    message_ids: List[str] = Field(description="Evidence message IDs", default_factory=list)

class InvestigationReport(BaseModel):
    summary: str = Field(description="A detailed narrative summary answering the query.")
    direct_mentions: int = Field(description="Estimated number of relevant direct mentions")
    connections: List[str] = Field(description="Names of closely related people involved in this query")
    timeline: List[TimelineEvent] = Field(description="Chronological timeline of events answering the query")

class InvestigatorService:
    
    @staticmethod
    async def investigate(user_id: str, chat_id: str, query: str) -> Dict[str, Any]:
        """
        Orchestrates an investigation based on a natural language query.
        """
        pool = await get_pool()
        
        # 1. Ask LLM to extract entities from the query to guide our search
        extraction_prompt = f"""
        Extract the names of people mentioned in this query.
        Return ONLY a comma-separated list of names. If none, return 'NONE'.
        Query: {query}
        """
        # We can just use the standard generate_json for a simple schema
        class Extraction(BaseModel):
            names: List[str]
            
        extraction = await llm_service.generate_json(extraction_prompt, response_schema=Extraction)
        names_to_investigate = extraction.get("names", []) if extraction else []
        
        person_ids = []
        connections_text = ""
        
        async with pool.acquire() as conn:
            await conn.execute("SET LOCAL app.user_id = $1", user_id)
            
            # 2. Gather Graph Context
            for name in names_to_investigate:
                pid = await get_person_id_by_name(conn, user_id, name)
                if pid:
                    person_ids.append(pid)
                    conns = await get_connections_for_person(conn, user_id, pid, chat_id)
                    conn_names = [c["name"] for c in conns]
                    connections_text += f"{name} frequently interacts with: {', '.join(conn_names)}.\n"
            
            # 3. Gather Timeline Events
            events = await get_events_for_persons(conn, user_id, chat_id, person_ids)
            
        # 4. Gather Semantic Evidence from Qdrant
        # We do a hybrid search using the query to find exact messages
        search_results = await hybrid_search(user_id, chat_id, query, limit=10)
        
        # 5. Synthesize the Final Report
        evidence_prompt = f"""
        You are an AI Detective. Synthesize an investigative report based on the following query and evidence.
        
        Query: "{query}"
        
        Social Graph Context:
        {connections_text if connections_text else "No specific graph context available."}
        
        Timeline Events in Chat:
        """
        for e in events[-5:]:  # Just take the last 5 major events to save context
            evidence_prompt += f"- {e['detected_at']}: {e['type']} - {e.get('description', '')}\n"
            
        evidence_prompt += "\nRelevant Messages Found:\n"
        for result in search_results:
            payload = result.get("payload", {})
            msg = payload.get("content", "")
            msg_ids = payload.get("message_ids", [])
            evidence_prompt += f"[Messages: {msg_ids}] {msg}\n"
            
        evidence_prompt += "\nProvide a structured JSON report."
        
        try:
            report = await llm_service.generate_json(evidence_prompt, response_schema=InvestigationReport)
            return report or {
                "summary": "Failed to generate report.",
                "direct_mentions": 0,
                "connections": [],
                "timeline": []
            }
        except Exception as e:
            logger.error(f"Investigation failed: {e}")
            return {
                "summary": f"Investigation error: {str(e)}",
                "direct_mentions": 0,
                "connections": [],
                "timeline": []
            }

investigator_service = InvestigatorService()

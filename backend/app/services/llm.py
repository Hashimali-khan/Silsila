import logging
from typing import AsyncGenerator, List, Dict, Any
import json
import asyncio

from groq import AsyncGroq
from google import genai
from google.genai import types as genai_types

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an empathetic, highly analytical AI assistant analyzing personal chat histories.
Your goal is to answer the user's questions based strictly on the provided evidence blocks.

RULES:
1. ONLY use the provided evidence to answer. Do not hallucinate or guess outside the evidence.
2. CITATIONS ARE MANDATORY. Every claim you make MUST end with a citation to the specific message ID(s) that support it.
   Format: "They went to the park. [id: 12345, 67890]"
3. MULTILINGUAL SUPPORT: You will often see English, Urdu, and Hinglish. Understand the context and reply in the same language as the user's query, while maintaining an empathetic tone.
4. If the evidence does not contain the answer, politely state that you cannot find the answer in the provided chat history.
"""

class LLMService:
    def __init__(self):
        self.groq_key = getattr(settings, "GROQ_API_KEY", None)
        self.gemini_key = getattr(settings, "GEMINI_API_KEY", None)
        
        self.groq_client = AsyncGroq(api_key=self.groq_key) if self.groq_key else None
        self.gemini_client = genai.Client(api_key=self.gemini_key) if self.gemini_key else None
        
        self.groq_model = getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")
        self.gemini_model = getattr(settings, "GEMINI_FLASH_MODEL", "gemini-2.5-flash")

    async def stream_answer(
        self, 
        query: str, 
        evidence_blocks: List[Dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        """
        Streams the answer using Groq as primary, falling back to Gemini on failure.
        Yields JSON-encoded strings for SSE.
        """
        # Format evidence
        formatted_evidence = "EVIDENCE BLOCKS:\n"
        for block in evidence_blocks:
            formatted_evidence += f"\n--- Thread {block.get('thread_id', 'unknown')} ---\n"
            formatted_evidence += block.get("content", "") + "\n"
            
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{formatted_evidence}\n\nUSER QUESTION: {query}"}
        ]

        # Try Groq first
        if self.groq_client:
            try:
                stream = await self.groq_client.chat.completions.create(
                    model=self.groq_model,
                    messages=messages,
                    stream=True,
                    temperature=0.3
                )
                async for chunk in stream:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield json.dumps({"type": "token", "content": content})
                return
            except Exception as e:
                logger.error(f"Groq LLM failed, falling back to Gemini: {e}")
        else:
            logger.warning("Groq not configured, trying Gemini fallback directly.")

        # Fallback to Gemini
        if self.gemini_client:
            try:
                # Format for Gemini
                contents = [
                    genai_types.Content(role="user", parts=[
                        genai_types.Part.from_text(text=f"{SYSTEM_PROMPT}\n\n{formatted_evidence}\n\nUSER QUESTION: {query}")
                    ])
                ]
                
                # Use standard synchronous call wrapped in asyncio if there's no async generate_content_stream
                # The latest google-genai package has async client support or we can just iterate.
                response = await self.gemini_client.aio.models.generate_content_stream(
                    model=self.gemini_model,
                    contents=contents,
                    config=genai_types.GenerateContentConfig(
                        temperature=0.3,
                    )
                )
                
                async for chunk in response:
                    if chunk.text:
                        yield json.dumps({"type": "token", "content": chunk.text})
                return
            except Exception as e:
                logger.error(f"Gemini LLM fallback failed: {e}")
                yield json.dumps({"type": "error", "content": "Failed to generate answer. Both primary and fallback LLMs are unavailable."})
        else:
            yield json.dumps({"type": "error", "content": "No LLM configured."})

    async def generate_json(
        self,
        prompt: str,
        response_schema: Any = None
    ) -> Dict[str, Any]:
        """
        Generates structured JSON using Gemini Flash (best for structured tasks).
        """
        if not self.gemini_client:
            raise ValueError("Gemini API key not configured. Gemini is required for structured JSON generation.")
            
        try:
            config = genai_types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            )
            if response_schema:
                config.response_schema = response_schema

            response = await self.gemini_client.aio.models.generate_content(
                model=self.gemini_model,
                contents=prompt,
                config=config
            )
            
            # Parse the JSON text
            if response.text:
                return json.loads(response.text)
            return {}
        except Exception as e:
            logger.error(f"Failed to generate structured JSON: {e}")
            raise

llm_service = LLMService()

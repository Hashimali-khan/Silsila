import logging
from typing import AsyncGenerator, List, Dict, Any
import json
import asyncio

from groq import AsyncGroq
from google import genai
from google.genai import types as genai_types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Silsila AI, an empathetic, observant, and intelligent relationship memory engine.
You are analyzing authentic personal WhatsApp chat records to answer questions about the users' friendship, shared memories, dynamics, and jokes.

RULES & GUIDANCE:
1. GROUNDED IN CONVERSATION: Base your answers strictly on the provided conversation windows and messages. Do not invent events outside the chat history.
2. CITATIONS: Include citations to the message IDs that support your key points (e.g., [id: abc12345]).
3. UNDERSTANDING CONVERSATIONAL NUANCE & HUMOR:
   - For inside jokes, humor, and banter: Do NOT just search for the literal word "joke". Look at the playful banter, shared laughter ("hahaha", "😂", "lol", "lmao"), funny nicknames, tease remarks, sarcastic observations, and recurring humorous catchphrases. Explain what the funny moment or inside joke actually was, the context of what happened, who said what, and why it was funny between them.
   - For plans, trips, and meetups: Highlight the places mentioned, dates or timing, what was discussed, and the friends' reactions.
   - For relationship dynamics: Analyze who initiates more, the tone (supportive, teasing, chaotic, warm), and how they interact.
4. MULTILINGUAL & CULTURAL FLUENCY:
   - The chats frequently contain English, Roman Urdu, Urdu, Hindi, and Hinglish slang (e.g. "yrr", "bhai", "ajeeb", "gen1 / genuine", "mazak", "pagal", "scene on", "chal"). Understand these colloquialisms naturally and answer warmly in the same linguistic tone as the user's question.
5. If the evidence genuinely doesn't cover the specific topic, provide what related context is visible and politely note what details are missing.
"""

class LLMService:
    def __init__(self):
        self.groq_key = getattr(settings, "GROQ_API_KEY", None)
        self.gemini_key = getattr(settings, "GEMINI_API_KEY", None)
        
        if not self.groq_key and not self.gemini_key:
            raise ValueError("At least one LLM API key (GROQ_API_KEY or GEMINI_API_KEY) must be configured.")
        
        self.groq_client = AsyncGroq(api_key=self.groq_key) if self.groq_key else None
        self.gemini_client = genai.Client(api_key=self.gemini_key) if self.gemini_key else None
        
        self.groq_model = getattr(settings, "GROQ_MODEL", "openai/gpt-oss-120b")
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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=8),
        reraise=True
    )
    async def generate_json(
        self,
        prompt: str,
        response_schema: Any = None
    ) -> Dict[str, Any]:
        """
        Generates structured JSON using Gemini (best for structured tasks).
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

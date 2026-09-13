import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.llm import LLMService

@pytest.mark.asyncio
async def test_stream_answer_success():
    service = LLMService()
    
    # Mock Groq client
    mock_groq_client = MagicMock()
    
    async def mock_groq_create(*args, **kwargs):
        async def stream():
            mock_chunk = MagicMock()
            mock_chunk.choices = [MagicMock()]
            mock_chunk.choices[0].delta.content = "mock answer"
            yield mock_chunk
        return stream()
        
    mock_groq_client.chat.completions.create = mock_groq_create
    service.groq_client = mock_groq_client
    
    evidence = [{"thread_id": "thread_1", "content": "Alice: hello"}]
    
    tokens = []
    async for token_msg in service.stream_answer("query", evidence):
        tokens.append(token_msg)
        
    assert len(tokens) == 1
    data = json.loads(tokens[0])
    assert data["type"] == "token"
    assert data["content"] == "mock answer"

@pytest.mark.asyncio
async def test_stream_answer_fallback():
    # If Groq fails, fallback to Gemini
    service = LLMService()
    
    # Mock Groq client to raise exception
    mock_groq_client = MagicMock()
    
    async def mock_groq_create_fail(*args, **kwargs):
        raise Exception("Groq failed")
        
    mock_groq_client.chat.completions.create = mock_groq_create_fail
    service.groq_client = mock_groq_client
    
    # Mock Gemini client
    mock_gemini_client = MagicMock()
    
    async def mock_gemini_generate(*args, **kwargs):
        async def stream():
            mock_chunk = MagicMock()
            mock_chunk.text = "fallback gemini answer"
            yield mock_chunk
        return stream()
        
    mock_gemini_client.aio.models.generate_content_stream = mock_gemini_generate
    service.gemini_client = mock_gemini_client
    
    evidence = [{"thread_id": "thread_1", "content": "Alice: hello"}]
    
    tokens = []
    with patch("app.services.llm.logger") as mock_logger:
        async for token_msg in service.stream_answer("query", evidence):
            tokens.append(token_msg)
            
        mock_logger.error.assert_called_with("Groq LLM failed, falling back to Gemini: Groq failed")
        
    assert len(tokens) == 1
    data = json.loads(tokens[0])
    assert data["type"] == "token"
    assert data["content"] == "fallback gemini answer"

import pytest
from unittest.mock import AsyncMock, patch
from app.services.sentiment import sentiment_service

@pytest.fixture
def mock_llm_service():
    with patch('app.services.sentiment.llm_service') as mock_llm:
        mock_llm.generate_json = AsyncMock()
        yield mock_llm

@pytest.mark.asyncio
async def test_analyze_sentiment_batch_empty():
    labels = await sentiment_service.analyze_sentiment_batch([])
    assert labels == []

@pytest.mark.asyncio
async def test_analyze_sentiment_batch(mock_llm_service):
    # Setup mock response
    mock_llm_service.generate_json.return_value = {
        "labels": [
            {"message_id": "1", "emotion": "Happy", "score": 0.95},
            {"message_id": "2", "emotion": "Angry", "score": 0.8}
        ]
    }
    
    messages = [
        {"id": "1", "sender_name": "A", "content": "I am so happy!"},
        {"id": "2", "sender_name": "B", "content": "I am furious."}
    ]
    
    labels = await sentiment_service.analyze_sentiment_batch(messages)
    
    assert len(labels) == 2
    assert labels[0]["message_id"] == "1"
    assert labels[0]["emotion"] == "Happy"
    assert labels[1]["emotion"] == "Angry"
    
    # Verify the LLM was called
    mock_llm_service.generate_json.assert_called_once()
    call_args = mock_llm_service.generate_json.call_args[0]
    assert "Analyze the sentiment" in call_args[0]
    assert "I am so happy!" in call_args[0]

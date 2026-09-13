"""Emotion labeling service (Phase 4)."""
import logging
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from app.services.llm import llm_service

logger = logging.getLogger(__name__)

class EmotionLabel(BaseModel):
    message_id: str = Field(description="The UUID of the message")
    emotion: str = Field(description="One of: Happy, Sad, Angry, Romantic, Awkward, Jealous, Supportive, Confused, Neutral")
    score: float = Field(description="Confidence score between 0.0 and 1.0")

class BatchEmotionResult(BaseModel):
    labels: list[EmotionLabel] = Field(description="The assigned emotion for each message in the batch")

class SentimentService:
    """
    Service for extracting sentiment and emotions from messages using the LLM.
    """
    
    @staticmethod
    async def analyze_sentiment_batch(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyzes a batch of messages and returns their emotion labels.
        
        Args:
            messages: List of message dictionaries, containing 'id', 'sender_name', and 'content'
            
        Returns:
            List of dictionaries with message_id, emotion, and score.
        """
        if not messages:
            return []
            
        prompt = (
            "Analyze the sentiment for the following chat messages. "
            "Assign ONE emotion label and a confidence score to each message.\n"
            "The allowed emotions are: Happy, Sad, Angry, Romantic, Awkward, Jealous, Supportive, Confused, Neutral.\n\n"
            "Messages:\n"
        )
        
        for m in messages:
            content = m.get('content', '')
            # Truncate very long messages to avoid token bloat
            if len(content) > 500:
                content = content[:500] + "..."
            prompt += f"Message ID: {m['id']}\nSender: {m['sender_name']}\nContent: {content}\n\n"
            
        try:
            result = await llm_service.generate_json(prompt, response_schema=BatchEmotionResult)
            
            extracted_labels = []
            if result and "labels" in result:
                for label in result["labels"]:
                    extracted_labels.append({
                        "message_id": label["message_id"],
                        "emotion": label["emotion"],
                        "score": label["score"]
                    })
            
            return extracted_labels
        except Exception as e:
            logger.error(f"Failed to extract sentiment for batch: {e}")
            return []

sentiment_service = SentimentService()

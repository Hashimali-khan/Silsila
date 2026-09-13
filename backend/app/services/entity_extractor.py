import logging
from typing import List, Dict, Any, Optional
import re
import asyncio
from pydantic import BaseModel, Field

from app.config import settings
from app.services.llm import llm_service

logger = logging.getLogger(__name__)

# Only import GLiNER if we are not using the LLM extractor exclusively
if not settings.USE_LLM_EXTRACTOR:
    try:
        from gliner import GLiNER
    except ImportError:
        pass

class EntitySchema(BaseModel):
    text: str = Field(description="The exact text of the extracted entity")
    label: str = Field(description="The label of the entity: Person, Location, Event, or Topic")

class EntityExtractionResult(BaseModel):
    entities: list[EntitySchema] = Field(description="The extracted entities")

# The target labels we want to extract
TARGET_LABELS = ["Person", "Location", "Event", "Topic"]
# The specific model we want to use (multilingual support)
MODEL_NAME = "urchade/gliner_multi-v2.1"

# Heuristic regex: matches words starting with an uppercase letter, ignoring common sentence starters
# This is a very simplistic heuristic to flag messages that MIGHT contain entities
PROPER_NOUN_HEURISTIC = re.compile(r'\b[A-Z][a-z]+\b')

class EntityExtractor:
    _instance: Optional['EntityExtractor'] = None
    _model: Optional[GLiNER] = None

    @classmethod
    def get_instance(cls) -> 'EntityExtractor':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        # We delay model loading until the first call to save memory during import
        self.is_loaded = False

    def load_model(self):
        if self.is_loaded or settings.USE_LLM_EXTRACTOR:
            return
        
        logger.info(f"Loading GLiNER model: {MODEL_NAME} (quantized, low CPU mem)")
        try:
            # We use quantize="int8" and low_cpu_mem_usage=True to fit in 512MB RAM on Heroku
            self._model = GLiNER.from_pretrained(
                MODEL_NAME, 
                quantize="int8", 
                low_cpu_mem_usage=True,
                map_location="cpu"
            )
            self.is_loaded = True
            logger.info("GLiNER model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load GLiNER model: {e}")
            raise

    def heuristic_scan(self, text: str) -> bool:
        """
        Quick regex heuristic to determine if a message is worth running through GLiNER.
        Returns True if there are capitalized words that might be entities.
        """
        if not text:
            return False
            
        # Ignore the first word of the message since it's naturally capitalized
        # Find all words matching the heuristic
        matches = PROPER_NOUN_HEURISTIC.findall(text)
        
        # If there are any capitalized words (excluding potentially just the first word),
        # flag it for GLiNER extraction.
        # This is a very generous heuristic.
        return len(matches) > 0

    async def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Extracts entities from a single text using GLiNER or Gemini based on config.
        """
        if not text or not self.heuristic_scan(text):
            return []

        if settings.USE_LLM_EXTRACTOR:
            prompt = f"Extract all named entities of types (Person, Location, Event, Topic) from the following text:\n\n{text}"
            try:
                result = await llm_service.generate_json(prompt, response_schema=EntityExtractionResult)
                return [{"text": e["text"], "label": e["label"]} for e in result.get("entities", [])]
            except Exception as e:
                logger.error(f"LLM Entity Extraction Error: {e}")
                return []
        else:
            if not self.is_loaded:
                self.load_model()
                
            try:
                # GLiNER predict_entities returns a list of dictionaries
                entities = self._model.predict_entities(text, TARGET_LABELS, flat_ner=True, threshold=0.5)
                return entities
            except Exception as e:
                logger.error(f"Error extracting entities for text: {e}")
                return []

    async def extract_entities_batch(self, texts: List[str]) -> List[List[Dict[str, Any]]]:
        """
        Extracts entities from a batch of texts.
        """
        if settings.USE_LLM_EXTRACTOR:
            # Run in parallel using asyncio.gather for LLM API calls to speed it up
            tasks = [self.extract_entities(text) for text in texts]
            return await asyncio.gather(*tasks)
        else:
            # Process sequentially for local model to keep peak memory footprint minimal
            results = []
            for text in texts:
                results.append(await self.extract_entities(text))
            return results

# Singleton instance for easy import
entity_extractor = EntityExtractor.get_instance()

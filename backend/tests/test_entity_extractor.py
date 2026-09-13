import pytest
from app.services.entity_extractor import entity_extractor

def test_heuristic_scan():
    # Should flag capitalized words that aren't the first word (actually our regex is simple)
    assert entity_extractor.heuristic_scan("hello world") == False
    assert entity_extractor.heuristic_scan("Hello world") == True # First word is capitalized
    assert entity_extractor.heuristic_scan("I went to Paris") == True
    
@pytest.mark.asyncio
async def test_extract_entities_no_match():
    # If heuristic scan returns False, extract_entities should return an empty list
    # without trying to load the model.
    text = "hello how are you"
    
    # We can mock heuristic_scan to make sure it's doing the right thing, 
    # but the text above won't match anyway.
    entities = await entity_extractor.extract_entities(text)
    assert entities == []

# Since we don't want to actually load the GLiNER model in unit tests due to memory/time,
# we should mock the model.
@pytest.fixture
def mock_gliner(monkeypatch):
    class MockModel:
        def predict_entities(self, text, labels, **kwargs):
            if "Abdullah" in text and "Lahore" in text:
                return [
                    {"text": "Abdullah", "label": "Person", "start": 4, "end": 12, "score": 0.99},
                    {"text": "Lahore", "label": "Location", "start": 19, "end": 25, "score": 0.98}
                ]
            elif "Abdullah" in text:
                return [{"text": "Abdullah", "label": "Person", "start": 0, "end": 8, "score": 0.99}]
            return []
            
    def mock_from_pretrained(*args, **kwargs):
        return MockModel()
        
    monkeypatch.setattr("app.services.entity_extractor.GLiNER.from_pretrained", mock_from_pretrained)
    # Reset state
    entity_extractor.is_loaded = False
    entity_extractor._model = None

@pytest.mark.asyncio
async def test_extract_entities_with_mock(mock_gliner):
    # This text passes the heuristic since it has capitalized words
    text = "Did Abdullah go to Lahore yesterday?"
    
    entities = await entity_extractor.extract_entities(text)
    assert len(entities) == 2
    
    # Check that it extracted Abdullah and Lahore correctly
    person = next((e for e in entities if e["label"] == "Person"), None)
    loc = next((e for e in entities if e["label"] == "Location"), None)
    
    assert person is not None
    assert person["text"] == "Abdullah"
    
    assert loc is not None
    assert loc["text"] == "Lahore"

@pytest.mark.asyncio
async def test_extract_entities_batch(mock_gliner):
    texts = ["Abdullah went to the store", "hello world"]
    res = await entity_extractor.extract_entities_batch(texts)
    assert len(res) == 2
    assert len(res[0]) == 1
    assert len(res[1]) == 0

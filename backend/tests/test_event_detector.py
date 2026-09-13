from datetime import datetime, timedelta
from app.services.event_detector import event_detector

def test_detect_no_events_if_few_messages():
    messages = [{"id": i, "sender_name": "A", "timestamp": datetime.now()} for i in range(5)]
    events = event_detector.detect_events(messages)
    assert len(events) == 0

def test_detect_ghosting():
    now = datetime(2026, 1, 1, 12, 0, 0)
    
    # Establish a baseline of fast replies (e.g. 5 minutes)
    messages = []
    for i in range(11):
        sender = "A" if i % 2 == 0 else "B"
        messages.append({
            "id": i,
            "sender_name": sender,
            "timestamp": now + timedelta(minutes=i*5),
            "content": f"msg {i}",
            "emotion": "Neutral"
        })
        
    # Make the last message from A negative
    messages[-1]["emotion"] = "Angry"
    messages[-1]["content"] = "I'm really mad at you!"
    
    # B replies 5 hours later
    messages.append({
        "id": 100,
        "sender_name": "B",
        "timestamp": messages[-1]["timestamp"] + timedelta(hours=5),
        "content": "Sorry I fell asleep",
        "emotion": "Neutral"
    })
    
    events = event_detector.detect_events(messages)
    
    assert len(events) == 1
    assert events[0]["type"] == "ghosting"
    assert "5.0 hours" in events[0]["description"]
    assert len(events[0]["evidence"]) == 2

def test_detect_fight():
    now = datetime(2026, 1, 1, 12, 0, 0)
    messages = []
    
    # 10 messages within 5 minutes, mostly angry
    for i in range(10):
        sender = "A" if i % 2 == 0 else "B"
        messages.append({
            "id": i,
            "sender_name": sender,
            "timestamp": now + timedelta(seconds=i*10),
            "content": "grr",
            "emotion": "Angry" if i % 2 == 0 else "Neutral" # 5 angry messages
        })
        
    events = event_detector.detect_events(messages)
    
    assert len(events) == 1
    assert events[0]["type"] == "fight"

def test_detect_celebration():
    now = datetime(2026, 1, 1, 12, 0, 0)
    messages = []
    
    # Happy messages with keywords
    for i in range(10):
        sender = "A" if i % 2 == 0 else "B"
        content = "Happy birthday!!" if i == 5 else "yay"
        messages.append({
            "id": i,
            "sender_name": sender,
            "timestamp": now + timedelta(seconds=i*10),
            "content": content,
            "emotion": "Happy" if i >= 5 else "Neutral" # 5 happy messages at the end
        })
        
    events = event_detector.detect_events(messages)
    
    assert len(events) == 1
    assert events[0]["type"] == "celebration"

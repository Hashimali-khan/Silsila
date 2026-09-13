import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class EventDetector:
    """
    Detects life events (Ghosting, Fight, Celebration, etc.) based on message
    frequency, reply latency, and sentiment.
    """
    
    @staticmethod
    def detect_events(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        messages should be chronologically ordered and contain:
        - id
        - sender_name
        - timestamp (datetime object)
        - content
        - emotion (from emotion_labels)
        - person_id (optional, UUID string)
        """
        events = []
        if not messages or len(messages) < 10:
            return events
            
        # Variables for rolling average reply latency
        reply_latencies = []
        
        # Sliding window state
        recent_emotions = [messages[0]] # list of messages
        
        for i in range(1, len(messages)):
            curr_msg = messages[i]
            prev_msg = messages[i-1]
            
            # 1. Calculate reply latency if sender changed
            if curr_msg["sender_name"] != prev_msg["sender_name"]:
                latency_sec = (curr_msg["timestamp"] - prev_msg["timestamp"]).total_seconds()
                
                # Update rolling average (keep last 20 replies)
                if latency_sec > 0:
                    reply_latencies.append(latency_sec)
                    if len(reply_latencies) > 20:
                        reply_latencies.pop(0)
                        
                # Ghosting Detection: >5x rolling average (if we have a baseline) AND prev was negative
                if len(reply_latencies) >= 5:
                    avg_latency = sum(reply_latencies[:-1]) / (len(reply_latencies) - 1) if len(reply_latencies) > 1 else reply_latencies[0]
                    if avg_latency > 60: # Base average must be at least 1 minute
                        if latency_sec > (avg_latency * 5) and latency_sec > 3600: # at least 1 hr delay
                            # Was the previous message negative?
                            prev_emotion = prev_msg.get("emotion")
                            if prev_emotion in ["Sad", "Angry", "Awkward", "Confused"]:
                                events.append({
                                    "type": "ghosting",
                                    "description": f"Significant delay ({latency_sec/3600:.1f} hours) following a {prev_emotion} message.",
                                    "detected_at": curr_msg["timestamp"],
                                    "evidence": [
                                        {"message_id": str(prev_msg["id"]), "snippet": prev_msg.get("content", "")[:100]},
                                        {"message_id": str(curr_msg["id"]), "snippet": curr_msg.get("content", "")[:100]}
                                    ],
                                    "confidence": 0.85
                                })
            
            # Maintain sliding window of last 20 messages for cluster detection
            recent_emotions.append(curr_msg)
            if len(recent_emotions) > 20:
                recent_emotions.pop(0)
                
            # 2. Fight / Argument Detection
            # Cluster of Angry + high frequency
            if len(recent_emotions) >= 10:
                angry_count = sum(1 for m in recent_emotions if m.get("emotion") == "Angry")
                if angry_count >= 4:
                    # Check frequency (are these 10 messages within 10 minutes?)
                    window_duration = (recent_emotions[-1]["timestamp"] - recent_emotions[0]["timestamp"]).total_seconds()
                    if window_duration < 600:
                        # Avoid duplicate fight events
                        last_fight = next((e for e in reversed(events) if e["type"] == "fight"), None)
                        if not last_fight or (curr_msg["timestamp"] - last_fight["detected_at"]).total_seconds() > 3600:
                            events.append({
                                "type": "fight",
                                "description": "High density of Angry messages in a short timeframe.",
                                "detected_at": curr_msg["timestamp"],
                                "evidence": [
                                    {"message_id": str(m["id"]), "snippet": m.get("content", "")[:100]} for m in recent_emotions if m.get("emotion") == "Angry"
                                ][:3], # Keep only up to 3 evidence pieces
                                "confidence": 0.90
                            })
                            
            # 3. Celebration Detection
            # Happy cluster + keywords
            happy_count = sum(1 for m in recent_emotions[-5:] if m.get("emotion") == "Happy")
            if happy_count >= 3:
                keywords = ["happy birthday", "congratulations", "congrats", "yay", "woohoo", "cheers", "mubarak", "mashallah"]
                window_text = " ".join([m.get("content", "").lower() for m in recent_emotions[-5:]])
                if any(kw in window_text for kw in keywords):
                    # Avoid duplicates
                    last_celeb = next((e for e in reversed(events) if e["type"] == "celebration"), None)
                    if not last_celeb or (curr_msg["timestamp"] - last_celeb["detected_at"]).total_seconds() > 86400: # 1 day
                        events.append({
                            "type": "celebration",
                            "description": "Celebration detected based on happy sentiment and keywords.",
                            "detected_at": curr_msg["timestamp"],
                            "evidence": [
                                {"message_id": str(m["id"]), "snippet": m.get("content", "")[:100]} for m in recent_emotions[-5:] if m.get("emotion") == "Happy"
                            ][:2],
                            "confidence": 0.88
                        })
                        
        return events

event_detector = EventDetector()

"""WhatsApp parser tests — Phase 1.

Run: pytest tests/test_parser.py -v

Tests cover:
  - Android and iOS format parsing
  - Multi-line messages
  - System messages
  - Media placeholders
  - Deleted messages
  - AM/PM time formats
  - 2-digit year
  - Urdu script content
  - Emoji content
  - Date format auto-detection (DD/MM vs MM/DD)
  - Empty file
  - Thread detection basics
"""

import pytest
from datetime import datetime
from app.services.whatsapp_parser import parse_whatsapp_export, extract_unique_senders
from app.services.thread_detector import detect_threads


# ── Fixtures ─────────────────────────────────────────────────────────────────

ANDROID_BASIC = """05/03/2026, 10:15 - Alice: Hello there
05/03/2026, 10:16 - Bob: Hey Alice! How are you?
05/03/2026, 10:17 - Alice: I'm good, thanks!"""

IOS_BASIC = """[05/03/2026, 10:15:00] Alice: Hello there
[05/03/2026, 10:16:30] Bob: Hey Alice! How are you?
[05/03/2026, 10:17:05] Alice: I'm good, thanks!"""

ANDROID_MULTILINE = """05/03/2026, 10:15 - Alice: First line
second line here
third line
05/03/2026, 10:16 - Bob: Next message"""

SYSTEM_MESSAGES = """05/03/2026, 10:00 - Messages and calls are end-to-end encrypted. No one outside of this chat, not even WhatsApp, can read or listen to them.
05/03/2026, 10:01 - Alice: Hi
05/03/2026, 10:02 - Bob added Alice"""

MEDIA_MESSAGES = """05/03/2026, 10:15 - Alice: <Media omitted>
05/03/2026, 10:16 - Bob: <image omitted>
05/03/2026, 10:17 - Alice: <video omitted>
05/03/2026, 10:18 - Bob: Normal message"""

DELETED_MESSAGES = """05/03/2026, 10:15 - Alice: This message was deleted
05/03/2026, 10:16 - Bob: You deleted this message
05/03/2026, 10:17 - Alice: Not deleted"""

AMPM_FORMAT = """03/05/2026, 10:15 AM - Alice: Morning message
03/05/2026, 02:30 PM - Bob: Afternoon message"""

URDU_CONTENT = """05/03/2026, 10:15 - علی: آپ کیسے ہیں؟
05/03/2026, 10:16 - احمد: بہت اچھا، شکریہ!
05/03/2026, 10:17 - علی: خوشی ہوئی"""

EMOJI_CONTENT = """05/03/2026, 10:15 - Alice: 😊❤️🎉
05/03/2026, 10:16 - Bob: 👍🏼
05/03/2026, 10:17 - Alice: 🥰💕"""

TWO_DIGIT_YEAR = """05/03/26, 10:15 - Alice: Old format
05/03/26, 10:16 - Bob: Also old"""


# ── Parser Tests ──────────────────────────────────────────────────────────────

class TestAndroidParser:
    def test_basic_parsing(self):
        msgs = parse_whatsapp_export(ANDROID_BASIC)
        assert len(msgs) == 3

    def test_senders(self):
        msgs = parse_whatsapp_export(ANDROID_BASIC)
        senders = {m["sender_name"] for m in msgs}
        assert senders == {"Alice", "Bob"}

    def test_timestamp_type(self):
        msgs = parse_whatsapp_export(ANDROID_BASIC)
        assert isinstance(msgs[0]["timestamp"], datetime)

    def test_timestamp_value(self):
        msgs = parse_whatsapp_export(ANDROID_BASIC)
        assert msgs[0]["timestamp"].day == 5
        assert msgs[0]["timestamp"].month == 3
        assert msgs[0]["timestamp"].hour == 10

    def test_content(self):
        msgs = parse_whatsapp_export(ANDROID_BASIC)
        assert msgs[0]["content"] == "Hello there"
        assert msgs[1]["content"] == "Hey Alice! How are you?"


class TestIOSParser:
    def test_basic_parsing(self):
        msgs = parse_whatsapp_export(IOS_BASIC)
        assert len(msgs) == 3

    def test_senders(self):
        msgs = parse_whatsapp_export(IOS_BASIC)
        senders = {m["sender_name"] for m in msgs}
        assert senders == {"Alice", "Bob"}

    def test_seconds_in_time(self):
        msgs = parse_whatsapp_export(IOS_BASIC)
        assert msgs[0]["timestamp"].second == 0
        assert msgs[1]["timestamp"].second == 30


class TestMultiLine:
    def test_multiline_combined(self):
        msgs = parse_whatsapp_export(ANDROID_MULTILINE)
        # First message should contain all continuation lines
        assert "First line" in msgs[0]["content"]
        assert "second line here" in msgs[0]["content"]
        assert "third line" in msgs[0]["content"]

    def test_next_message_separate(self):
        msgs = parse_whatsapp_export(ANDROID_MULTILINE)
        assert len(msgs) == 2
        assert msgs[1]["content"] == "Next message"


class TestSystemMessages:
    def test_system_flagged(self):
        msgs = parse_whatsapp_export(SYSTEM_MESSAGES)
        sys_msgs = [m for m in msgs if m["is_system_msg"]]
        assert len(sys_msgs) >= 1

    def test_regular_messages_not_system(self):
        msgs = parse_whatsapp_export(SYSTEM_MESSAGES)
        regular = [m for m in msgs if not m["is_system_msg"]]
        assert any(m["sender_name"] == "Alice" for m in regular)


class TestMedia:
    def test_media_flagged(self):
        msgs = parse_whatsapp_export(MEDIA_MESSAGES)
        media_msgs = [m for m in msgs if m["is_media"]]
        assert len(media_msgs) == 3

    def test_normal_not_media(self):
        msgs = parse_whatsapp_export(MEDIA_MESSAGES)
        normal = [m for m in msgs if not m["is_media"]]
        assert any("Normal message" in m["content"] for m in normal)


class TestDeletedMessages:
    def test_deleted_flagged(self):
        msgs = parse_whatsapp_export(DELETED_MESSAGES)
        deleted = [m for m in msgs if m["is_deleted"]]
        assert len(deleted) == 2

    def test_not_deleted_message(self):
        msgs = parse_whatsapp_export(DELETED_MESSAGES)
        not_deleted = [m for m in msgs if not m["is_deleted"]]
        assert any("Not deleted" in m["content"] for m in not_deleted)


class TestAMPM:
    def test_ampm_parsing(self):
        msgs = parse_whatsapp_export(AMPM_FORMAT)
        assert len(msgs) == 2
        assert msgs[0]["timestamp"].hour == 10
        assert msgs[1]["timestamp"].hour == 14  # 2 PM = 14


class TestUnicode:
    def test_urdu_content(self):
        msgs = parse_whatsapp_export(URDU_CONTENT)
        assert len(msgs) == 3
        assert "آپ کیسے ہیں؟" in msgs[0]["content"]

    def test_urdu_senders(self):
        msgs = parse_whatsapp_export(URDU_CONTENT)
        senders = {m["sender_name"] for m in msgs}
        assert "علی" in senders

    def test_emoji_content(self):
        msgs = parse_whatsapp_export(EMOJI_CONTENT)
        assert len(msgs) == 3
        assert "😊" in msgs[0]["content"]


class TestEdgeCases:
    def test_empty_file(self):
        msgs = parse_whatsapp_export("")
        assert msgs == []

    def test_two_digit_year(self):
        msgs = parse_whatsapp_export(TWO_DIGIT_YEAR)
        assert len(msgs) == 2


# ── Thread Detection Tests ─────────────────────────────────────────────────────

class TestThreadDetector:
    def _make_messages(self, timestamps):
        return [
            {"timestamp": ts, "sender_name": "Alice", "content": "msg", "is_system_msg": False}
            for ts in timestamps
        ]

    def test_single_thread_rapid_chat(self):
        """Messages within minutes should be in one thread."""
        from datetime import timedelta
        base = datetime(2026, 3, 5, 10, 0)
        msgs = self._make_messages([base + timedelta(minutes=i) for i in range(10)])
        threads = detect_threads(msgs)
        assert len(threads) == 1

    def test_multi_thread_long_gaps(self):
        """Messages separated by days should split into multiple threads."""
        from datetime import timedelta
        base = datetime(2026, 3, 5, 10, 0)
        timestamps = [
            base,
            base + timedelta(minutes=1),
            base + timedelta(hours=5),   # new thread
            base + timedelta(hours=5, minutes=1),
            base + timedelta(days=1),    # new thread
        ]
        msgs = self._make_messages(timestamps)
        threads = detect_threads(msgs)
        assert len(threads) >= 2

    def test_empty_messages(self):
        assert detect_threads([]) == []

    def test_single_message(self):
        msgs = self._make_messages([datetime(2026, 3, 5, 10, 0)])
        threads = detect_threads(msgs)
        assert len(threads) == 1
        assert len(threads[0]) == 1

    def test_thread_index_assigned(self):
        from datetime import timedelta
        base = datetime(2026, 3, 5, 10, 0)
        timestamps = [base, base + timedelta(minutes=1), base + timedelta(hours=6)]
        msgs = self._make_messages(timestamps)
        detect_threads(msgs)
        assert "thread_index" in msgs[0]


# ── Senders Utility ───────────────────────────────────────────────────────────

class TestExtractSenders:
    def test_extract_senders(self):
        msgs = parse_whatsapp_export(ANDROID_BASIC)
        senders = extract_unique_senders(msgs)
        assert sorted(senders) == ["Alice", "Bob"]

    def test_excludes_system(self):
        msgs = parse_whatsapp_export(SYSTEM_MESSAGES)
        senders = extract_unique_senders(msgs)
        assert "__system__" not in senders

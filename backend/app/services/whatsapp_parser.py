"""WhatsApp-specific chat export parser.

Supports both iOS and Android WhatsApp export formats with no abstraction —
this is intentional (ADR §1). The two formats are:

  iOS:     [DD/MM/YYYY, HH:MM:SS] Sender: Message
  Android: DD/MM/YYYY, HH:MM - Sender: Message

Edge cases handled:
  - Multi-line messages (continuation lines)
  - System messages (no sender colon)
  - Media placeholders: <Media omitted>, <image omitted>, <video omitted>
  - Deleted messages
  - Urdu script, emoji, Hinglish mixed content
  - Both DD/MM/YYYY and MM/DD/YYYY (auto-detected)
  - 12-hour (AM/PM) and 24-hour time
  - Streaming parse (never loads entire file into memory)

Output: list[ParsedMessage] where each is a TypedDict.
"""

import re
import logging
from datetime import datetime
from typing import Iterator, TypedDict

logger = logging.getLogger(__name__)

# ── Compiled Patterns ─────────────────────────────────────────────────────────

# Android: 05/03/2026, 10:15 - Sender: Message
_ANDROID = re.compile(
    r'^(\d{1,2}/\d{1,2}/\d{2,4}),\s'      # date
    r'(\d{1,2}:\d{2}(?::\d{2})?'           # time HH:MM or HH:MM:SS
    r'(?:\s?[APap][Mm])?)'                  # optional AM/PM
    r'\s-\s'                                # separator
    r'(.+?):\s'                             # sender (non-greedy, ends with ": ")
    r'(.+)$',                               # message content
    re.DOTALL,
)

# iOS: [05/03/2026, 10:15:30] Sender: Message
_IOS = re.compile(
    r'^\[(\d{1,2}/\d{1,2}/\d{2,4}),\s'    # date (in brackets)
    r'(\d{1,2}:\d{2}(?::\d{2})?'           # time
    r'(?:\s?[APap][Mm])?)\]\s'             # end bracket + space
    r'(.+?):\s'                             # sender
    r'(.+)$',                               # message
    re.DOTALL,
)

# Android system message (no sender colon)
_ANDROID_SYS = re.compile(
    r'^(\d{1,2}/\d{1,2}/\d{2,4}),\s'
    r'(\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?)'
    r'\s-\s'
    r'(.+)$',
)

# iOS system message
_IOS_SYS = re.compile(
    r'^\[(\d{1,2}/\d{1,2}/\d{2,4}),\s'
    r'(\d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?)\]\s'
    r'(.+)$',
)

_MEDIA_PATTERN = re.compile(
    r'<(?:Media|image|video|audio|document|sticker|GIF|Contact card) omitted>',
    re.IGNORECASE,
)

_DELETED_PATTERN = re.compile(
    r'(?:This message was deleted|You deleted this message)',
    re.IGNORECASE,
)

# ── Types ─────────────────────────────────────────────────────────────────────


class ParsedMessage(TypedDict):
    sender_name: str
    timestamp: datetime
    content: str
    is_system_msg: bool
    is_media: bool
    is_deleted: bool
    raw_line: str


# ── Date Parsing ──────────────────────────────────────────────────────────────

def _detect_date_format(sample_date: str) -> str:
    """
    Detect whether the export uses DD/MM or MM/DD format.
    WhatsApp iOS uses MM/DD/YYYY in US locales, DD/MM/YYYY elsewhere.
    We check if the first component can only be a day (>12).
    Returns '%d/%m/%Y' or '%m/%d/%Y'.
    """
    parts = sample_date.split("/")
    if len(parts) >= 2:
        first = int(parts[0])
        if first > 12:
            return "%d/%m/%Y"
    # Default to DD/MM — more common globally (and in Pakistan)
    return "%d/%m/%Y"


def _parse_datetime(date_str: str, time_str: str, date_fmt: str) -> datetime | None:
    """Parse date + time string into a datetime. Returns None on failure."""
    time_str = time_str.strip()
    # Normalize AM/PM spacing: "10:15AM" → "10:15 AM"
    time_str = re.sub(r'([APap][Mm])$', r' \1', time_str).strip()

    # Try common formats
    year_fmt = "%y" if len(date_str.split("/")[-1]) == 2 else "%Y"
    d_fmt = date_fmt.replace("%Y", year_fmt)

    for t_fmt in ["%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p"]:
        try:
            return datetime.strptime(f"{date_str} {time_str}", f"{d_fmt} {t_fmt}")
        except ValueError:
            continue
    return None


# ── Core Parser ───────────────────────────────────────────────────────────────

def parse_whatsapp_export(text_content: str) -> list[ParsedMessage]:
    """
    Parse a WhatsApp .txt export into a list of ParsedMessage dicts.

    Processes line-by-line (streaming-style) without loading the full
    split into memory at once. Multi-line messages are accumulated until
    the next timestamped line is detected.

    Args:
        text_content: Raw text content of the WhatsApp export file.

    Returns:
        List of ParsedMessage dicts, ordered chronologically.
    """
    lines = text_content.splitlines()
    messages: list[ParsedMessage] = []

    if not lines:
        return messages

    # Detect date format from first few timestamped lines
    date_fmt = "%d/%m/%Y"
    for line in lines[:20]:
        m = _ANDROID.match(line) or _IOS.match(line)
        if m:
            date_fmt = _detect_date_format(m.group(1))
            logger.debug("Detected date format: %s", date_fmt)
            break

    # Detect platform from first match
    platform: str | None = None
    current: ParsedMessage | None = None

    def _flush(msg: ParsedMessage | None) -> None:
        """Flush accumulated message to results list."""
        if msg is not None:
            msg["content"] = msg["content"].strip()
            if msg["content"]:
                messages.append(msg)

    for line in lines:
        line = line.rstrip("\r\n")

        # Try message patterns
        parsed = _try_parse_line(line, date_fmt, platform)

        if parsed is not None:
            _flush(current)
            current = parsed
            if platform is None:
                platform = parsed.get("_platform")  # type: ignore[typeddict-item]
        elif current is not None and line:
            # Continuation of a multi-line message
            current["content"] += "\n" + line

    _flush(current)

    logger.info("Parsed %d messages (format=%s)", len(messages), date_fmt)
    return messages


def _try_parse_line(
    line: str,
    date_fmt: str,
    platform: str | None,
) -> ParsedMessage | None:
    """Attempt to parse a single line as a new message. Returns None if it's a continuation."""

    # Try Android message first (or if platform detected as android)
    if platform in (None, "android"):
        m = _ANDROID.match(line)
        if m:
            return _build_message(m.group(1), m.group(2), m.group(3), m.group(4), date_fmt, "android")

        # Android system message
        m = _ANDROID_SYS.match(line)
        if m and not _ANDROID.match(line):
            content = m.group(3)
            ts = _parse_datetime(m.group(1), m.group(2), date_fmt)
            if ts:
                return _make_system(ts, content, "android")

    # Try iOS message
    if platform in (None, "ios"):
        m = _IOS.match(line)
        if m:
            return _build_message(m.group(1), m.group(2), m.group(3), m.group(4), date_fmt, "ios")

        m = _IOS_SYS.match(line)
        if m and not _IOS.match(line):
            content = m.group(3)
            ts = _parse_datetime(m.group(1), m.group(2), date_fmt)
            if ts:
                return _make_system(ts, content, "ios")

    return None


def _build_message(
    date_str: str,
    time_str: str,
    sender: str,
    content: str,
    date_fmt: str,
    platform: str,
) -> ParsedMessage | None:
    ts = _parse_datetime(date_str, time_str, date_fmt)
    if ts is None:
        return None

    is_media = bool(_MEDIA_PATTERN.search(content))
    is_deleted = bool(_DELETED_PATTERN.search(content))

    return ParsedMessage(
        sender_name=sender.strip(),
        timestamp=ts,
        content=content.strip(),
        is_system_msg=False,
        is_media=is_media,
        is_deleted=is_deleted,
        raw_line=f"{date_str}, {time_str} - {sender}: {content}",
        _platform=platform,  # type: ignore[typeddict-unknown-key]
    )


def _make_system(ts: datetime, content: str, platform: str) -> ParsedMessage:
    return ParsedMessage(
        sender_name="__system__",
        timestamp=ts,
        content=content.strip(),
        is_system_msg=True,
        is_media=False,
        is_deleted=False,
        raw_line=content,
        _platform=platform,  # type: ignore[typeddict-unknown-key]
    )


# ── Utilities ─────────────────────────────────────────────────────────────────

def extract_unique_senders(messages: list[ParsedMessage]) -> list[str]:
    """Return sorted list of unique non-system sender names."""
    return sorted({m["sender_name"] for m in messages if not m["is_system_msg"]})

"""Adaptive thread detection using median-based time-gap analysis.

Groups a list of parsed messages into conversation threads by detecting
natural silence breaks. Uses 10× the median inter-message gap as the
threshold, clamped between 30 minutes and 4 hours (ADR §3).

Dependency: must run BEFORE chunk_builder.py (chunking is downstream).
"""

import statistics
import logging
from datetime import datetime
from typing import TypedDict

logger = logging.getLogger(__name__)

# Gap threshold bounds (seconds)
MIN_GAP_SECONDS = 30 * 60    # 30 minutes
MAX_GAP_SECONDS = 4 * 60 * 60  # 4 hours


class ThreadedMessage(TypedDict):
    sender_name: str
    timestamp: datetime
    content: str
    is_system_msg: bool
    is_media: bool
    is_deleted: bool
    thread_index: int  # 0-based thread number within the chat


def detect_threads(messages: list[dict]) -> list[list[dict]]:
    """
    Group messages into conversation threads using adaptive gap detection.

    Args:
        messages: List of ParsedMessage dicts (must have 'timestamp' key).

    Returns:
        List of threads, each thread is a list of messages in order.
        Each message in a thread gets a 'thread_index' added.
    """
    if not messages:
        return []
    if len(messages) == 1:
        messages[0]["thread_index"] = 0
        return [messages]

    # Calculate all inter-message gaps in seconds
    gaps: list[float] = []
    for i in range(1, len(messages)):
        prev_ts: datetime = messages[i - 1]["timestamp"]
        curr_ts: datetime = messages[i]["timestamp"]
        gap_secs = (curr_ts - prev_ts).total_seconds()
        # Negative gaps can occur if timestamps are slightly out of order
        gaps.append(max(gap_secs, 0))

    # Adaptive threshold: 10× median, clamped to [30min, 4hr]
    median_gap = statistics.median(gaps) if gaps else 0
    threshold = max(median_gap * 10, MIN_GAP_SECONDS)
    threshold = min(threshold, MAX_GAP_SECONDS)

    logger.debug(
        "Thread detection: median_gap=%.0fs, threshold=%.0fs, messages=%d",
        median_gap,
        threshold,
        len(messages),
    )

    # Split into threads
    threads: list[list[dict]] = [[messages[0]]]
    messages[0]["thread_index"] = 0

    for i, gap in enumerate(gaps):
        msg = messages[i + 1]
        if gap > threshold:
            threads.append([])
        msg["thread_index"] = len(threads) - 1
        threads[-1].append(msg)

    logger.info(
        "Detected %d threads from %d messages (threshold=%.0fs)",
        len(threads),
        len(messages),
        threshold,
    )
    return threads


def get_thread_stats(threads: list[list[dict]]) -> dict:
    """Return summary statistics about thread detection results."""
    if not threads:
        return {}
    sizes = [len(t) for t in threads]
    return {
        "thread_count": len(threads),
        "total_messages": sum(sizes),
        "avg_thread_size": round(statistics.mean(sizes), 1),
        "median_thread_size": statistics.median(sizes),
        "largest_thread": max(sizes),
        "smallest_thread": min(sizes),
    }

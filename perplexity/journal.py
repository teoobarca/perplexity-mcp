"""
Request journal for debugging Perplexity API response format changes.

Writes one JSONL line per request with timing, structure, and status info.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import JOURNAL_FILE, JOURNAL_MAX_SIZE_MB
from .logger import get_logger

logger = get_logger("journal")


class RequestJournal:
    """Append-only JSONL journal for request/response debugging."""

    def __init__(self, path: Optional[str] = None, max_size_mb: Optional[int] = None):
        self.path = Path(path or JOURNAL_FILE)
        self.max_size_bytes = (max_size_mb or JOURNAL_MAX_SIZE_MB) * 1024 * 1024

    def record(
        self,
        *,
        query: str,
        mode: str,
        sources: list,
        client_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        status: str,
        error: Optional[str] = None,
        response_keys: Optional[List[str]] = None,
        answer_length: Optional[int] = None,
        source_count: Optional[int] = None,
        chunk_count: Optional[int] = None,
        sse_event_count: Optional[int] = None,
        step_types: Optional[List[str]] = None,
        fallback: bool = False,
    ) -> None:
        """Append a journal entry. Never raises -- failures are logged."""
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "epoch": time.time(),
            "query": query[:200],
            "mode": mode,
            "sources": sources,
            "client_id": client_id,
            "duration_ms": round(duration_ms, 1) if duration_ms is not None else None,
            "status": status,
            "error": str(error)[:500] if error else None,
            "answer_len": answer_length,
            "source_count": source_count,
            "chunk_count": chunk_count,
            "sse_events": sse_event_count,
            "step_types": step_types,
            "fallback": fallback,
            "response_keys": response_keys,
        }

        try:
            self._maybe_rotate()
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("Failed to write journal entry: %s", e)

    def _maybe_rotate(self) -> None:
        """Rotate if file exceeds max size. Keep 1 backup."""
        try:
            if self.path.exists() and self.path.stat().st_size > self.max_size_bytes:
                backup = self.path.with_suffix(".jsonl.1")
                self.path.replace(backup)
                logger.info("Journal rotated: %s -> %s", self.path, backup)
        except Exception as e:
            logger.warning("Journal rotation failed: %s", e)


# Singleton instance
_journal: Optional[RequestJournal] = None


def get_journal() -> RequestJournal:
    """Get or create the singleton RequestJournal."""
    global _journal
    if _journal is None:
        _journal = RequestJournal()
    return _journal

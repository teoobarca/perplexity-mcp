"""Tests for the request journal module."""

import json
import os
import tempfile
import unittest

from perplexity.journal import RequestJournal


class TestRequestJournal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self.tmp.close()
        self.journal = RequestJournal(path=self.tmp.name, max_size_mb=1)

    def tearDown(self):
        for path in [self.tmp.name, self.tmp.name + ".1"]:
            try:
                os.unlink(path)
            except OSError:
                pass

    def test_record_creates_valid_jsonl(self):
        self.journal.record(
            query="test query", mode="pro",             sources=["web"], status="ok", answer_length=100,
        )
        with open(self.tmp.name) as f:
            line = f.readline()
        entry = json.loads(line)
        self.assertEqual(entry["query"], "test query")
        self.assertEqual(entry["status"], "ok")
        self.assertEqual(entry["answer_len"], 100)
        self.assertIn("ts", entry)
        self.assertIn("epoch", entry)

    def test_multiple_records(self):
        for i in range(5):
            self.journal.record(
                query=f"query {i}", mode="pro",                 sources=["web"], status="ok",
            )
        with open(self.tmp.name) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 5)
        for line in lines:
            json.loads(line)  # Each line must be valid JSON

    def test_query_truncation(self):
        long_query = "x" * 500
        self.journal.record(
            query=long_query, mode="auto",             sources=["web"], status="ok",
        )
        with open(self.tmp.name) as f:
            entry = json.loads(f.readline())
        self.assertEqual(len(entry["query"]), 200)

    def test_error_recording(self):
        self.journal.record(
            query="fail query", mode="deep research",             sources=["web", "scholar"], status="error",
            error="Connection timeout after 120s",
        )
        with open(self.tmp.name) as f:
            entry = json.loads(f.readline())
        self.assertEqual(entry["status"], "error")
        self.assertIn("timeout", entry["error"])

    def test_response_keys_logged(self):
        self.journal.record(
            query="test", mode="pro",             sources=["web"], status="ok",
            response_keys=["answer", "text", "backend_uuid", "chunks"],
        )
        with open(self.tmp.name) as f:
            entry = json.loads(f.readline())
        self.assertIn("answer", entry["response_keys"])
        self.assertIn("backend_uuid", entry["response_keys"])

    def test_step_types_logged(self):
        self.journal.record(
            query="test", mode="deep research",             sources=["web"], status="ok",
            step_types=["SEARCH_RESULTS", "ACTION", "FINAL"],
        )
        with open(self.tmp.name) as f:
            entry = json.loads(f.readline())
        self.assertEqual(entry["step_types"], ["SEARCH_RESULTS", "ACTION", "FINAL"])

    def test_rotation(self):
        self.journal.max_size_bytes = 100  # Tiny limit
        for i in range(20):
            self.journal.record(
                query=f"query {i}", mode="pro",                 sources=["web"], status="ok",
            )
        self.assertTrue(os.path.exists(self.tmp.name))
        # Backup should exist after rotation
        backup = self.tmp.name + ".1"
        self.assertTrue(os.path.exists(backup))

    def test_record_never_raises(self):
        """Journal should never raise, even with a bad path."""
        bad_journal = RequestJournal(path="/nonexistent/dir/journal.jsonl")
        # Should not raise
        bad_journal.record(
            query="test", mode="auto",             sources=["web"], status="ok",
        )

    def test_all_fields_present(self):
        self.journal.record(
            query="full test", mode="deep research",             sources=["web", "scholar"], client_id="hlavný",
            duration_ms=2340.567, status="ok",
            response_keys=["text", "answer"],
            answer_length=1500, source_count=12,
            chunk_count=15, sse_event_count=42,
            step_types=["SEARCH_RESULTS", "FINAL"],
            fallback=False,
        )
        with open(self.tmp.name) as f:
            entry = json.loads(f.readline())
        self.assertEqual(entry["mode"], "deep research")
        self.assertEqual(entry["client_id"], "hlavný")
        self.assertEqual(entry["duration_ms"], 2340.6)
        self.assertEqual(entry["answer_len"], 1500)
        self.assertEqual(entry["source_count"], 12)
        self.assertEqual(entry["chunk_count"], 15)
        self.assertEqual(entry["sse_events"], 42)
        self.assertFalse(entry["fallback"])


if __name__ == "__main__":
    unittest.main()

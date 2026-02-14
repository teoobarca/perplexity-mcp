"""
Tests for deep research silent downgrade prevention.

Layer 1: Pre-request quota check in run_query() (app.py)
Layer 2: Post-response structure validation in Client.search() (client.py)
"""

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Layer 2: _validate_research_response (client.py)
# ---------------------------------------------------------------------------

class TestValidateResearchResponse:
    """Tests for Client._validate_research_response."""

    def _make_client(self):
        """Create a Client instance with mocked HTTP session."""
        with patch("perplexity.client.requests.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session_cls.return_value = mock_session
            mock_session.get.return_value = MagicMock(ok=True)
            from perplexity.client import Client
            return Client({"csrf": "test", "session": "test"})

    def test_raises_on_string_text(self):
        """String text means Perplexity returned a regular pro result, not deep research."""
        client = self._make_client()
        with pytest.raises(Exception, match="silently downgraded"):
            client._validate_research_response({"text": "This is a regular answer."})

    def test_raises_on_none_text(self):
        """None text also indicates a non-research response."""
        client = self._make_client()
        with pytest.raises(Exception, match="silently downgraded"):
            client._validate_research_response({"text": None})

    def test_passes_on_list_text(self):
        """List text is the expected deep research structure (step objects)."""
        client = self._make_client()
        response = {
            "text": [
                {"step_type": "SEARCH_RESULTS", "content": {}},
                {"step_type": "FINAL", "content": {"answer": "{}"}},
            ]
        }
        # Should not raise
        client._validate_research_response(response)

    def test_raises_on_missing_text_key(self):
        """Response without 'text' key means text is None — also a downgrade."""
        client = self._make_client()
        with pytest.raises(Exception, match="silently downgraded"):
            client._validate_research_response({"answer": "some answer"})

    def test_passes_on_empty_list_text(self):
        """Empty list is still a list — not a string downgrade."""
        client = self._make_client()
        client._validate_research_response({"text": []})


# ---------------------------------------------------------------------------
# Layer 1: Pre-request quota check in run_query() (app.py)
# ---------------------------------------------------------------------------

class TestDeepResearchQuotaCheck:
    """Tests for deep research quota filtering via get_client(mode).

    get_client("deep research") checks has_quota() which filters by
    research.available and research.remaining from rate_limits.
    """

    def _make_pool_with_client(self, client_id, rate_limits):
        """Create a mock pool with a single client that has given rate_limits."""
        from perplexity.server.client_pool import ClientWrapper

        mock_client = MagicMock()
        mock_client.own = True
        mock_client.copilot = float("inf")
        mock_client.file_upload = float("inf")

        wrapper = ClientWrapper(mock_client, client_id)
        wrapper.rate_limits = rate_limits
        wrapper.session_valid = True

        mock_pool = MagicMock()
        mock_pool.clients = {client_id: wrapper}
        mock_pool.is_fallback_to_auto_enabled.return_value = False

        # get_client(mode) delegates to has_quota — simulate the real behavior
        def fake_get_client(mode="auto"):
            if wrapper.is_available() and wrapper.has_quota(mode):
                return (client_id, mock_client)
            return (None, None)

        mock_pool.get_client.side_effect = fake_get_client

        return mock_pool, mock_client

    @patch("perplexity.server.app.get_pool")
    def test_skips_client_with_zero_research_remaining(self, mock_get_pool):
        """Client with research remaining=0 should be skipped for deep research."""
        from perplexity.server.app import run_query

        pool, client = self._make_pool_with_client("user1", {
            "pro_remaining": 100,
            "modes": {"research": {"available": True, "remaining": 0, "kind": "daily"}},
        })
        mock_get_pool.return_value = pool

        result = run_query("test query", mode="deep research", language="en-US")

        assert result["status"] == "error"
        client.search.assert_not_called()

    @patch("perplexity.server.app.get_pool")
    def test_skips_client_with_research_unavailable(self, mock_get_pool):
        """Client with research available=False should be skipped for deep research."""
        from perplexity.server.app import run_query

        pool, client = self._make_pool_with_client("user1", {
            "pro_remaining": 100,
            "modes": {"research": {"available": False, "remaining": None, "kind": None}},
        })
        mock_get_pool.return_value = pool

        result = run_query("test query", mode="deep research", language="en-US")

        assert result["status"] == "error"
        client.search.assert_not_called()

    @patch("perplexity.server.app.get_pool")
    def test_allows_client_with_research_quota(self, mock_get_pool):
        """Client with research quota available should proceed normally."""
        from perplexity.server.app import run_query

        pool, client = self._make_pool_with_client("user1", {
            "pro_remaining": 100,
            "modes": {"research": {"available": True, "remaining": 3, "kind": "daily"}},
        })
        mock_get_pool.return_value = pool

        # Mock successful search response (deep research structure)
        client.search.return_value = {
            "text": [{"step_type": "FINAL", "content": {"answer": "{}"}}],
            "answer": "The answer",
        }

        result = run_query("test query", mode="deep research", language="en-US")

        assert result["status"] == "ok"
        client.search.assert_called_once()

    @patch("perplexity.server.app.get_pool")
    def test_allows_client_without_rate_limits(self, mock_get_pool):
        """Client without rate_limits data (not yet fetched) should proceed normally."""
        from perplexity.server.app import run_query

        pool, client = self._make_pool_with_client("user1", {})
        mock_get_pool.return_value = pool

        client.search.return_value = {
            "text": [{"step_type": "FINAL", "content": {"answer": "{}"}}],
            "answer": "The answer",
        }

        result = run_query("test query", mode="deep research", language="en-US")

        assert result["status"] == "ok"
        client.search.assert_called_once()

    @patch("perplexity.server.app.get_pool")
    def test_pro_mode_ignores_research_quota(self, mock_get_pool):
        """Pro mode should NOT check research quota (only deep research does)."""
        from perplexity.server.app import run_query

        pool, client = self._make_pool_with_client("user1", {
            "pro_remaining": 100,
            "modes": {"research": {"available": False, "remaining": 0, "kind": "daily"}},
        })
        mock_get_pool.return_value = pool

        client.search.return_value = {"text": "Regular answer", "answer": "The answer"}

        result = run_query("test query", mode="pro", language="en-US")

        assert result["status"] == "ok"
        client.search.assert_called_once()

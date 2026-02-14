"""Utility tests with console-like output for user visibility."""

import pytest

from perplexity.exceptions import ValidationError
from perplexity.server.utils import sanitize_query, validate_search_params


def test_sanitize_query_trims_and_validates() -> None:
    print("console.log -> testing sanitize_query behavior")
    assert sanitize_query("  hello world  ") == "hello world"
    with pytest.raises(ValidationError):
        sanitize_query("")


def test_validate_search_params_requires_own_account() -> None:
    print("console.log -> validating search params requirements")
    validate_search_params("auto", None, ["web"], own_account=False)
    with pytest.raises(ValidationError):
        validate_search_params("pro", "sonar", ["web"], own_account=False)


def test_client_limit_pattern_matches_correctly() -> None:
    """Test that the error classification regex matches real limit errors but not false positives."""
    from perplexity.server.app import _CLIENT_LIMIT_PATTERN

    # Should match
    assert _CLIENT_LIMIT_PATTERN.search("No remaining pro queries")
    assert _CLIENT_LIMIT_PATTERN.search("Pro search quota exhausted")
    assert _CLIENT_LIMIT_PATTERN.search("Rate limit exceeded")
    assert _CLIENT_LIMIT_PATTERN.search("rate-limit reached")
    assert _CLIENT_LIMIT_PATTERN.search("0 remaining")
    assert _CLIENT_LIMIT_PATTERN.search("File upload limit")

    # Should NOT match
    assert not _CLIENT_LIMIT_PATTERN.search("Invalid model 'pro-turbo' for mode 'pro'")
    assert not _CLIENT_LIMIT_PATTERN.search("provide a valid query")
    assert not _CLIENT_LIMIT_PATTERN.search("processing error")
    assert not _CLIENT_LIMIT_PATTERN.search("account not found")

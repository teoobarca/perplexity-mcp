import json
import pytest
from unittest.mock import MagicMock, patch
from perplexity.server.app import run_query, get_pool
from perplexity.server.client_pool import ClientPool

# Load test config
TEST_CONFIG_PATH = "tests/test_data/token_pool_config.json"
with open(TEST_CONFIG_PATH, "r") as f:
    TEST_CONFIG = json.load(f)

@pytest.fixture
def mock_pool():
    """Reset global pool and return a new one initialized with test config."""
    import perplexity.server.app as app_module
    # Save original pool
    original_pool = app_module._pool
    # Create and set new pool
    pool = ClientPool(TEST_CONFIG_PATH)
    app_module._pool = pool
    yield pool
    # Restore original pool
    app_module._pool = original_pool

def test_single_account_all_retries_fail(mock_pool):
    """
    Scenario 1: Single faulty account.
    Expectation: Should retry 3 times on the same client, then fail.
    """
    # Setup: Only keep one client in the pool
    mock_pool.clients = {k: v for k, v in list(mock_pool.clients.items())[:1]}
    mock_pool._rotation_order = list(mock_pool.clients.keys())

    single_client_id = mock_pool._rotation_order[0]
    wrapper = mock_pool.clients[single_client_id]

    # Mock search on the actual client instance
    mock_search = MagicMock(side_effect=Exception("Network Error"))
    wrapper.client.search = mock_search

    # Execute
    with patch("time.sleep"):
        result = run_query("test query", mode="auto")

    # Verification
    assert result["status"] == "error"
    assert result["message"] == "Network Error"

    # Should have been called 3 times (1 initial + 2 retries)
    assert mock_search.call_count == 3

    # Verify the client was marked as failed (backoff applied)
    assert wrapper.fail_count > 0
    assert not wrapper.is_available()

def test_failover_to_next_account(mock_pool):
    """
    Scenario 2: Multi-account failover.
    Expectation: First account fails 3 times, then switches to second account which succeeds.
    """
    # Ensure we have at least 2 clients
    assert len(mock_pool.clients) >= 2
    client_ids = mock_pool._rotation_order
    first_client_id = client_ids[0]
    second_client_id = client_ids[1]

    first_wrapper = mock_pool.clients[first_client_id]
    second_wrapper = mock_pool.clients[second_client_id]

    # Track call counts per client
    call_tracker = {"first": 0, "second": 0}

    def first_client_side_effect(*args, **kwargs):
        call_tracker["first"] += 1
        raise Exception(f"Fail {call_tracker['first']}")

    def second_client_side_effect(*args, **kwargs):
        call_tracker["second"] += 1
        return {"answer": "Success", "text": []}

    # Mock search on actual client instances
    first_wrapper.client.search = MagicMock(side_effect=first_client_side_effect)
    second_wrapper.client.search = MagicMock(side_effect=second_client_side_effect)

    # Execute
    with patch("time.sleep"):
        result = run_query("test query", mode="auto")

    # Verification
    assert result["status"] == "ok"
    assert result["data"]["answer"] == "Success"

    # First client should have been called 3 times (initial + 2 retries)
    assert call_tracker["first"] == 3

    # Second client should have been called once (success)
    assert call_tracker["second"] == 1

    # First client should be marked failed
    assert first_wrapper.fail_count > 0

    # Second client should be successful (fail_count reset/0)
    assert second_wrapper.fail_count == 0

def test_pro_limit_immediate_failover(mock_pool):
    """
    Scenario 3: Pro limit error should trigger immediate failover (no retries on same client).
    """
    # Ensure we have at least 2 clients
    assert len(mock_pool.clients) >= 2
    client_ids = mock_pool._rotation_order
    first_client_id = client_ids[0]
    second_client_id = client_ids[1]

    first_wrapper = mock_pool.clients[first_client_id]
    second_wrapper = mock_pool.clients[second_client_id]

    # Track call counts per client
    call_tracker = {"first": 0, "second": 0}

    def first_client_side_effect(*args, **kwargs):
        call_tracker["first"] += 1
        raise Exception("You have reached your pro limit")

    def second_client_side_effect(*args, **kwargs):
        call_tracker["second"] += 1
        return {"answer": "Success", "text": []}

    # Mock search on actual client instances
    first_wrapper.client.search = MagicMock(side_effect=first_client_side_effect)
    second_wrapper.client.search = MagicMock(side_effect=second_client_side_effect)

    with patch("time.sleep"):
        result = run_query("test query", mode="pro")

    assert result["status"] == "ok"
    # Should only call once per client - pro limit triggers immediate failover (no retries)
    assert call_tracker["first"] == 1
    assert call_tracker["second"] == 1

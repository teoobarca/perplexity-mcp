"""
Starlette application instance and shared utilities.
"""

import os
import re
from contextlib import asynccontextmanager
from typing import Any, Dict, Iterable, List, Optional, Union

from starlette.applications import Starlette

from .client_pool import ClientPool
from ..client import Client
from ..config import SEARCH_LANGUAGES
from ..exceptions import ValidationError
from ..logger import get_logger

from .utils import (
    sanitize_query, validate_file_data, validate_query_limits, validate_search_params,
)

logger = get_logger("server.app")

_CLIENT_LIMIT_PATTERN = re.compile(
    r'\b(pro queries|pro search|rate.?limit|quota|remaining|file upload)\b',
    re.IGNORECASE,
)

# Global ClientPool singleton
_pool: Optional[ClientPool] = None


def get_pool() -> ClientPool:
    """Get or create the singleton ClientPool instance."""
    global _pool
    if _pool is None:
        _pool = ClientPool()
    return _pool


@asynccontextmanager
async def app_lifespan(app):
    """Application lifespan handler for startup/shutdown events."""
    pool = get_pool()
    if pool.is_monitor_enabled():
        pool.start_monitor()
        logger.info("Monitor started via lifespan")
    yield
    pool.stop_monitor()
    logger.info("Monitor stopped via lifespan")


def normalize_files(files: Optional[Union[Dict[str, Any], Iterable[str]]]) -> Dict[str, Any]:
    """
    Accept either a dict of filename->data or an iterable of file paths,
    and normalize to the dict format expected by Client.search.
    """
    if not files:
        return {}

    if isinstance(files, dict):
        normalized = files
    else:
        normalized = {}
        for path in files:
            filename = os.path.basename(path)
            with open(path, "rb") as fh:
                normalized[filename] = fh.read()

    validate_file_data(normalized)
    return normalized


def extract_clean_result(response: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the final answer and source links from the search response."""
    result = {}

    # Extract final answer
    if "answer" in response:
        result["answer"] = response["answer"]

    # Extract source links
    sources = []

    # Method 1: Extract web_results from SEARCH_RESULTS steps in the text field
    if "text" in response and isinstance(response["text"], list):
        for step in response["text"]:
            if isinstance(step, dict) and step.get("step_type") == "SEARCH_RESULTS":
                content = step.get("content", {})
                web_results = content.get("web_results", [])
                for web_result in web_results:
                    if isinstance(web_result, dict) and "url" in web_result:
                        source = {"url": web_result["url"]}
                        if "name" in web_result:
                            source["title"] = web_result["name"]
                        sources.append(source)

    # Method 2: Fallback - extract from chunks field (if chunks contain URLs)
    if not sources and "chunks" in response and isinstance(response["chunks"], list):
        for chunk in response["chunks"]:
            if isinstance(chunk, dict):
                source = {}
                if "url" in chunk:
                    source["url"] = chunk["url"]
                if "title" in chunk:
                    source["title"] = chunk["title"]
                if "name" in chunk and "title" not in source:
                    source["title"] = chunk["name"]
                if "url" in source:
                    sources.append(source)

    result["sources"] = sources

    return result


def run_query(
    query: str,
    mode: str,
    model: Optional[str] = None,
    sources: Optional[List[str]] = None,
    language: str = "en-US",
    incognito: bool = False,
    files: Optional[Union[Dict[str, Any], Iterable[str]]] = None,
    fallback_to_auto: bool = True,
) -> Dict[str, Any]:
    """
    Execute a Perplexity query with client pool rotation and optional fallback.

    Features:
    - Rotates through all available clients in the pool on failure
    - Prioritizes non-downgraded clients for Pro mode requests
    - Falls back to auto mode using first available downgraded client if all Pro clients exhausted
    - Validates query and files once before execution

    Args:
        fallback_to_auto: If True, attempt auto mode fallback when all Pro clients fail
    """
    from ..logger import get_logger
    logger = get_logger("server.app")

    pool = get_pool()

    # --- 1. Stateless Validation ---
    try:
        clean_query = sanitize_query(query)
        chosen_sources = sources or ["web"]

        # Ensure SEARCH_LANGUAGES is not None before using 'in'
        if SEARCH_LANGUAGES is None or language not in SEARCH_LANGUAGES:
            valid_langs = ', '.join(SEARCH_LANGUAGES) if SEARCH_LANGUAGES else "en-US"
            raise ValidationError(
                f"Invalid language '{language}'. Choose from: {valid_langs}"
            )

        normalized_files = normalize_files(files)
    except ValidationError as exc:
        return {
            "status": "error",
            "error_type": "ValidationError",
            "message": str(exc),
        }

    # --- 2. Check if fallback to auto is enabled ---
    should_fallback = fallback_to_auto and pool.is_fallback_to_auto_enabled()
    is_pro_mode = mode in ("pro", "reasoning", "deep research")

    logger.debug(f"Starting query: mode={mode}, model={model}, fallback_enabled={should_fallback}, is_pro_mode={is_pro_mode}")

    # --- 3. Client Pool Rotation ---
    # For Pro mode: first try non-downgraded clients, then fallback to auto if enabled
    attempted_clients = set()
    skipped_downgraded_clients = []
    last_error = None
    total_clients = len(pool.clients)
    seen_ids = set()

    # Try all distinct clients via round-robin
    for _ in range(total_clients * 2):  # 2x to account for round-robin wrapping
        client_id, client = pool.get_client()

        if client is None:
            if not attempted_clients:
                earliest = pool.get_earliest_available_time()
                last_error = Exception(f"All clients are currently unavailable. Earliest available at: {earliest}")
            break

        if client_id in seen_ids:
            # Saw this client already — if we've seen all clients, stop
            if len(seen_ids) >= total_clients:
                break
            continue

        seen_ids.add(client_id)

        # Check client state
        client_state = pool.get_client_state(client_id)

        logger.debug(f"[{client_id}] Checking client: state={client_state}, requested_mode={mode}")

        # For Pro mode: skip downgraded clients first, try Pro clients
        if is_pro_mode and client_state == "downgrade":
            logger.debug(f"[{client_id}] Client is DOWNGRADED, skipping for Pro mode (will retry with fallback if enabled)")
            skipped_downgraded_clients.append((client_id, client))
            continue

        attempted_clients.add(client_id)
        logger.debug(f"[{client_id}] Selected client for Pro mode, state={client_state}")

        # Pre-request quota check for deep research
        if mode == "deep research":
            wrapper = pool.clients.get(client_id)
            if wrapper and wrapper.rate_limits:
                research = wrapper.rate_limits.get("modes", {}).get("research", {})
                if research.get("available") is False or research.get("remaining") == 0:
                    logger.debug(f"[{client_id}] No research quota, skipping for deep research")
                    pool.mark_client_pro_failure(client_id)
                    continue

        try:
            # Stateful Validation
            validate_search_params(mode, model, chosen_sources, own_account=client.own)
            validate_query_limits(client.copilot, client.file_upload, mode, len(normalized_files))

            logger.debug(f"[{client_id}] Executing search: mode={mode}, model={model}")

            response = client.search(
                clean_query,
                mode=mode,
                model=model,
                sources=chosen_sources,
                files=normalized_files,
                stream=False,
                language=language,
                incognito=incognito,
            )

            if response is None:
                raise Exception("Empty response from Perplexity (connection may have dropped)")

            # Success
            pool.mark_client_success(client_id, mode=mode)
            clean_result = extract_clean_result(response)
            logger.debug(f"[{client_id}] Query succeeded with Pro mode")
            return {"status": "ok", "data": clean_result}

        except ValidationError as exc:
            last_error = exc
            error_msg = str(exc).lower()
            is_client_limit = bool(_CLIENT_LIMIT_PATTERN.search(error_msg))

            if is_client_limit:
                logger.debug(f"[{client_id}] Client limit error: {exc}")
                if mode == "pro":
                    pool.mark_client_pro_failure(client_id)
                else:
                    pool.mark_client_failure(client_id)
                continue
            else:
                logger.debug(f"[{client_id}] Validation error (user input): {exc}")
                return {
                    "status": "error",
                    "error_type": "ValidationError",
                    "message": str(exc),
                }

        except Exception as exc:
            last_error = exc
            error_msg = str(exc).lower()
            logger.debug(f"[{client_id}] Request exception: {type(exc).__name__}: {exc}")

            if mode == "pro" and _CLIENT_LIMIT_PATTERN.search(error_msg):
                pool.mark_client_pro_failure(client_id)
            else:
                pool.mark_client_failure(client_id)
            continue

    # --- 4. Fallback: Use first available downgraded client with auto mode ---
    if should_fallback and is_pro_mode and skipped_downgraded_clients:
        best_client_id, best_client = skipped_downgraded_clients[0]

        logger.info(
            f"All {len(skipped_downgraded_clients)} Pro clients are DOWNGRADED. "
            f"Fallback enabled, using client [{best_client_id}] with auto mode"
        )
        logger.warning(
            f"[{best_client_id}] DOWNGRADE FALLBACK: switching from mode='{mode}' model='{model}' to mode='auto'"
        )

        try:
            validate_search_params("auto", None, chosen_sources, own_account=best_client.own)

            logger.debug(f"[{best_client_id}] Executing fallback search: mode=auto, model=None")

            response = best_client.search(
                clean_query,
                mode="auto",
                model=None,
                sources=chosen_sources,
                files={},  # auto mode doesn't support files
                stream=False,
                language=language,
                incognito=incognito,
            )

            if response and "answer" in response:
                pool.mark_client_success(best_client_id, mode="auto")
                clean_result = extract_clean_result(response)
                clean_result["fallback"] = True
                clean_result["fallback_mode"] = "auto"
                clean_result["original_mode"] = mode
                clean_result["original_model"] = model
                logger.info(f"[{best_client_id}] DOWNGRADE FALLBACK succeeded: '{mode}' -> 'auto'")
                return {"status": "ok", "data": clean_result}
            else:
                logger.warning(f"[{best_client_id}] DOWNGRADE FALLBACK failed: no answer in response")
                last_error = Exception("Fallback search returned no answer")

        except Exception as fallback_exc:
            logger.warning(f"[{best_client_id}] DOWNGRADE FALLBACK failed: {fallback_exc}")
            last_error = fallback_exc

    # --- 5. Last resort: Anonymous auto mode fallback ---
    if should_fallback and mode != "auto":
        try:
            logger.info("All clients exhausted, attempting anonymous auto mode fallback...")

            anonymous_client = Client({})
            response = anonymous_client.search(
                clean_query,
                mode="auto",
                model=None,
                sources=chosen_sources,
                files={},
                stream=False,
                language=language,
                incognito=True,
            )

            if response and "answer" in response:
                logger.info("Anonymous auto mode fallback succeeded")
                clean_result = extract_clean_result(response)
                clean_result["fallback"] = True
                clean_result["fallback_mode"] = "anonymous_auto"
                return {"status": "ok", "data": clean_result}
            else:
                logger.warning("Anonymous auto mode fallback failed: no answer in response")
        except Exception as anon_exc:
            logger.warning(f"Anonymous auto mode fallback failed: {anon_exc}")

    # --- 6. Final Error Handling ---
    total_tried = len(attempted_clients) + len(skipped_downgraded_clients)
    logger.warning(f"Query failed after trying {total_tried} clients (Pro: {len(attempted_clients)}, Downgraded: {len(skipped_downgraded_clients)}): {last_error}")
    return {
        "status": "error",
        "error_type": last_error.__class__.__name__ if last_error else "RequestFailed",
        "message": str(last_error) if last_error else "Request failed after multiple attempts.",
    }


# Import admin routes after get_pool is defined (avoids circular import)
from .admin import routes as admin_routes  # noqa: E402

app = Starlette(lifespan=app_lifespan, routes=admin_routes)

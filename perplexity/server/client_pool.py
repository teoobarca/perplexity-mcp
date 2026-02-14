"""
Client pool for managing multiple Perplexity API tokens with load balancing.

Provides round-robin client selection with exponential backoff retry on failures.
Supports periodic monitoring to automatically verify token health via rate-limit API.
"""

import asyncio
import json
import pathlib
import os
import tempfile
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ..client import Client
from ..logger import get_logger

logger = get_logger("server.client_pool")


class ClientWrapper:
    """Wrapper for Client with failure tracking and availability status."""

    # Backoff constants
    INITIAL_BACKOFF = 60  # First failure: 60 seconds cooldown
    MAX_BACKOFF = 3600  # Maximum backoff: 1 hour

    def __init__(self, client: Client, client_id: str):
        self.client = client
        self.id = client_id
        self.fail_count = 0
        self.available_after: float = 0
        self.request_count = 0
        self.enabled = True  # Whether this client is enabled for use
        self.session_valid: Optional[bool] = None  # None=unchecked, True=valid, False=invalid
        self.last_check: Optional[float] = None  # Last health check timestamp
        self.rate_limits: dict = {}  # Cached rate-limit data from API
        self.rate_limits_updated: float = 0  # When rate_limits were last fetched

    @property
    def state(self) -> str:
        """Computed state for API/frontend display. Single source of truth."""
        if self.session_valid is False:
            return "offline"
        if self.session_valid is None:
            return "unknown"
        if self.rate_limits.get("pro_remaining", 1) > 0:
            return "normal"
        return "exhausted"

    def has_quota(self, mode: str) -> bool:
        """Check if this client has quota for the given mode.

        Returns True if quota is available or unknown (assume yes).
        """
        if self.session_valid is False:
            return False
        if mode in ("pro", "reasoning"):
            pro_rem = self.rate_limits.get("pro_remaining")
            return pro_rem is None or pro_rem > 0
        if mode == "deep research":
            research = self.rate_limits.get("modes", {}).get("research", {})
            if research.get("available") is False:
                return False
            rem = research.get("remaining")
            return rem is None or rem > 0
        return True  # auto mode always ok

    def is_available(self) -> bool:
        """Check if the client is currently available (enabled and not in backoff)."""
        return self.enabled and time.time() >= self.available_after

    def mark_failure(self) -> None:
        """Mark the client as failed, applying exponential backoff.

        First failure: 60s cooldown
        Consecutive failures: 60s * 2^(fail_count-1), max 1 hour
        """
        self.fail_count += 1
        # Exponential backoff starting from INITIAL_BACKOFF (60s)
        # 1st fail: 60s, 2nd: 120s, 3rd: 240s, 4th: 480s, ... max: 3600s
        backoff = min(self.MAX_BACKOFF, self.INITIAL_BACKOFF * (2 ** (self.fail_count - 1)))
        self.available_after = time.time() + backoff

    def mark_success(self) -> None:
        """Mark the client as successful, resetting failure state."""
        self.fail_count = 0
        self.available_after = 0
        self.request_count += 1

    def decrement_quota(self, mode: str) -> bool:
        """Locally decrement the quota counter for the given mode.

        Returns True if any counter reached 0 (needs API verification).
        """
        if not self.rate_limits:
            return False

        needs_verify = False
        modes = self.rate_limits.get("modes", {})

        if mode in ("pro", "reasoning"):
            # Decrement pro_remaining
            pro_rem = self.rate_limits.get("pro_remaining")
            if pro_rem is not None and pro_rem > 0:
                self.rate_limits["pro_remaining"] = pro_rem - 1
                if self.rate_limits["pro_remaining"] == 0:
                    needs_verify = True

            # Decrement modes.pro_search.remaining
            pro_search = modes.get("pro_search", {})
            ps_rem = pro_search.get("remaining")
            if ps_rem is not None and ps_rem > 0:
                pro_search["remaining"] = ps_rem - 1
                if pro_search["remaining"] == 0:
                    needs_verify = True

        elif mode == "deep research":
            research = modes.get("research", {})
            r_rem = research.get("remaining")
            if r_rem is not None and r_rem > 0:
                research["remaining"] = r_rem - 1
                if research["remaining"] == 0:
                    needs_verify = True

        return needs_verify

    def get_status(self) -> Dict[str, Any]:
        """Get the current status of this client."""
        available = self.is_available()
        next_available_at = None
        if not available:
            next_available_at = datetime.fromtimestamp(
                self.available_after, tz=timezone.utc
            ).isoformat()

        last_check_at = None
        if self.last_check:
            last_check_at = datetime.fromtimestamp(
                self.last_check, tz=timezone.utc
            ).isoformat()

        return {
            "id": self.id,
            "available": self.is_available(),
            "enabled": self.enabled,
            "state": self.state,
            "fail_count": self.fail_count,
            "next_available_at": next_available_at,
            "last_check_at": last_check_at,
            "request_count": self.request_count,
            "rate_limits": self.rate_limits,
        }

    async def refresh_rate_limits(self) -> dict:
        """Fetch rate limits from API (async via thread)."""
        result = await asyncio.to_thread(self.client.get_rate_limits)
        self.rate_limits = result
        self.rate_limits_updated = time.time()
        return result

    def get_user_info(self) -> Dict[str, Any]:
        """Get user session information for this client."""
        return self.client.get_user_info()


class ClientPool:
    """
    Pool of Client instances with round-robin load balancing.

    Supports dynamic addition and removal of clients at runtime.
    Supports periodic monitoring for automatic token health verification.
    """

    def __init__(self, config_path: Optional[str] = None, config_writable: bool = True):
        self.clients: Dict[str, ClientWrapper] = {}
        self._rotation_order: List[str] = []
        self._index = 0
        self._lock = threading.Lock()
        self._mode = "anonymous"
        self._config_writable = config_writable

        # Monitor configuration
        self._monitor_config: Dict[str, Any] = {
            "enable": False,
            "interval": 6,  # hours
            "tg_bot_token": None,
            "tg_chat_id": None
        }
        # Fallback configuration
        self._fallback_config: Dict[str, Any] = {
            "fallback_to_auto": True  # Enable fallback to anonymous auto mode by default
        }
        self._monitor_task: Optional[asyncio.Task] = None
        self._config_path: Optional[str] = None
        self._state_file_mtime: float = 0
        self._config_file_mtime: float = 0

        # Load initial clients from config or environment
        self._initialize(config_path)

    def _initialize(self, config_path: Optional[str] = None) -> None:
        """Initialize the pool from config file or environment variables."""
        # Priority 1: Explicit config file path
        if config_path and os.path.exists(config_path):
            self._load_from_config(config_path)
            return

        # Priority 2: Environment variable pointing to config
        env_config_path = os.getenv("PPLX_TOKEN_POOL_CONFIG")
        if env_config_path and os.path.exists(env_config_path):
            self._load_from_config(env_config_path)
            return

        # Priority 3: Default token_pool_config.json in project root
        # Look for config file relative to the module location or current working directory
        default_config_paths = [
            pathlib.Path.cwd() / "token_pool_config.json",  # Current working directory
            pathlib.Path(__file__).parent.parent / "token_pool_config.json",  # perplexity/token_pool_config.json
            pathlib.Path(__file__).parent.parent.parent / "token_pool_config.json",  # Project root
        ]
        for default_path in default_config_paths:
            logger.info(f"Checking for config at: {default_path}")
            if default_path.exists():
                logger.info(f"Found config file at: {default_path}")
                self._load_from_config(str(default_path))
                return

        # Priority 4: Single token from environment variables
        csrf_token = os.getenv("PPLX_NEXT_AUTH_CSRF_TOKEN")
        session_token = os.getenv("PPLX_SESSION_TOKEN")
        if csrf_token and session_token:
            self._add_client_internal(
                "default",
                {"next-auth.csrf-token": csrf_token, "__Secure-next-auth.session-token": session_token},
            )
            self._mode = "single"
            return

        # Priority 5: Anonymous client (no cookies)
        self._add_client_internal("anonymous", {})
        self._mode = "anonymous"

    def _load_from_config(self, config_path: str) -> None:
        """Load clients from a JSON configuration file."""
        self._config_path = config_path
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # Load monitor configuration if present (backward compat: also reads "heart_beat")
        monitor_cfg = config.get("monitor") or config.get("heart_beat")
        if monitor_cfg and isinstance(monitor_cfg, dict):
            self._monitor_config = {
                "enable": monitor_cfg.get("enable", False),
                "interval": monitor_cfg.get("interval", 6),
                "tg_bot_token": monitor_cfg.get("tg_bot_token"),
                "tg_chat_id": monitor_cfg.get("tg_chat_id")
            }

        # Load fallback configuration if present
        fallback = config.get("fallback")
        if fallback and isinstance(fallback, dict):
            self._fallback_config = {
                "fallback_to_auto": fallback.get("fallback_to_auto", True)
            }

        tokens = config.get("tokens", [])
        if not tokens:
            raise ValueError(f"No tokens found in config file: {config_path}")

        for token_entry in tokens:
            client_id = token_entry.get("id")
            csrf_token = token_entry.get("csrf_token")
            session_token = token_entry.get("session_token")

            if not all([client_id, csrf_token, session_token]):
                raise ValueError(f"Invalid token entry in config: {token_entry}")

            cookies = {
                "next-auth.csrf-token": csrf_token,
                "__Secure-next-auth.session-token": session_token,
            }
            self._add_client_internal(client_id, cookies)

        self._mode = "pool"
        # Track config file mtime for hot-reload
        try:
            self._config_file_mtime = os.path.getmtime(config_path)
        except OSError:
            self._config_file_mtime = 0

    def _add_client_internal(self, client_id: str, cookies: Dict[str, str]) -> None:
        """Internal method to add a client without locking."""
        client = Client(cookies)
        wrapper = ClientWrapper(client, client_id)
        self.clients[client_id] = wrapper
        self._rotation_order.append(client_id)

    def add_client(
        self, client_id: str, csrf_token: str, session_token: str
    ) -> Dict[str, Any]:
        """
        Add a new client to the pool at runtime.

        Returns:
            Dict with status and message
        """
        with self._lock:
            if client_id in self.clients:
                return {
                    "status": "error",
                    "message": f"Client '{client_id}' already exists",
                }

            cookies = {
                "next-auth.csrf-token": csrf_token,
                "__Secure-next-auth.session-token": session_token,
            }
            self._add_client_internal(client_id, cookies)

            # Update mode if transitioning from single/anonymous to pool
            if self._mode in ("single", "anonymous") and len(self.clients) > 1:
                self._mode = "pool"

        # Save to config file (outside lock to avoid blocking)
        if self._config_path:
            self._save_config()

        return {
            "status": "ok",
            "message": f"Client '{client_id}' added successfully",
        }

    def remove_client(self, client_id: str) -> Dict[str, Any]:
        """
        Remove a client from the pool at runtime.

        Returns:
            Dict with status and message
        """
        with self._lock:
            if client_id not in self.clients:
                return {
                    "status": "error",
                    "message": f"Client '{client_id}' not found",
                }

            if len(self.clients) <= 1:
                return {
                    "status": "error",
                    "message": "Cannot remove the last client. At least one client must remain.",
                }

            del self.clients[client_id]
            self._rotation_order.remove(client_id)

            # Adjust index if needed
            if self._index >= len(self._rotation_order):
                self._index = 0

        # Save to config file (outside lock to avoid blocking)
        if self._config_path:
            self._save_config()

        return {
            "status": "ok",
            "message": f"Client '{client_id}' removed successfully",
        }

    def list_clients(self) -> Dict[str, Any]:
        """
        List all clients with their id and availability status.

        Returns:
            Dict with status and client list
        """
        with self._lock:
            clients = [
                {
                    "id": wrapper.id,
                    "available": wrapper.is_available(),
                    "enabled": wrapper.enabled,
                }
                for wrapper in self.clients.values()
            ]
            return {"status": "ok", "data": {"clients": clients}}

    def enable_client(self, client_id: str) -> Dict[str, Any]:
        """
        Enable a client in the pool.

        Returns:
            Dict with status and message
        """
        with self._lock:
            wrapper = self.clients.get(client_id)
            if not wrapper:
                return {"status": "error", "message": f"Client '{client_id}' not found"}
            wrapper.enabled = True
            return {"status": "ok", "message": f"Client '{client_id}' enabled"}

    def disable_client(self, client_id: str) -> Dict[str, Any]:
        """
        Disable a client in the pool.

        Returns:
            Dict with status and message
        """
        with self._lock:
            wrapper = self.clients.get(client_id)
            if not wrapper:
                return {"status": "error", "message": f"Client '{client_id}' not found"}

            # Check if this is the last enabled client
            enabled_count = sum(1 for w in self.clients.values() if w.enabled)
            if enabled_count <= 1 and wrapper.enabled:
                return {
                    "status": "error",
                    "message": "Cannot disable the last enabled client. At least one client must remain enabled.",
                }

            wrapper.enabled = False
            return {"status": "ok", "message": f"Client '{client_id}' disabled"}

    def reset_client(self, client_id: str) -> Dict[str, Any]:
        """
        Reset a client's failure state.

        Returns:
            Dict with status and message
        """
        with self._lock:
            wrapper = self.clients.get(client_id)
            if not wrapper:
                return {"status": "error", "message": f"Client '{client_id}' not found"}
            wrapper.fail_count = 0
            wrapper.available_after = 0
            return {"status": "ok", "message": f"Client '{client_id}' reset successfully"}

    def get_client(self, mode: str = "auto") -> Tuple[Optional[str], Optional[Client]]:
        """
        Get the next available client using round-robin selection.

        Filters by: enabled, not in backoff, and has_quota(mode).

        Returns:
            Tuple of (client_id, Client) or (None, None) if no clients available
        """
        with self._lock:
            if not self.clients:
                return None, None

            # Round-robin among clients that are available AND have quota for this mode
            eligible_ids = {
                client_id
                for client_id in self._rotation_order
                if self.clients[client_id].is_available()
                and self.clients[client_id].has_quota(mode)
            }

            if eligible_ids:
                for _ in range(len(self._rotation_order)):
                    client_id = self._rotation_order[self._index]
                    self._index = (self._index + 1) % len(self._rotation_order)

                    if client_id in eligible_ids:
                        return client_id, self.clients[client_id].client

            # No eligible clients - check if any are available (just no quota)
            available_ids = {
                client_id
                for client_id in self._rotation_order
                if self.clients[client_id].is_available()
            }
            if not available_ids:
                # All in backoff - return soonest available with client=None
                soonest_wrapper = min(
                    self.clients.values(), key=lambda w: w.available_after
                )
                return soonest_wrapper.id, None

            # Clients available but no quota for this mode
            return None, None

    def mark_client_success(self, client_id: str, mode: str = "") -> None:
        """Mark a client as successful after a request.

        Decrements quota locally based on mode. If quota reaches 0,
        schedules an async rate-limit refresh to verify.
        """
        needs_verify = False
        with self._lock:
            wrapper = self.clients.get(client_id)
            if wrapper:
                wrapper.mark_success()
                if mode:
                    needs_verify = wrapper.decrement_quota(mode)

        # Persist state (with updated quotas)
        if mode:
            self.save_state(writer="quota_decrement")

        # If quota hit 0, schedule async verification
        if needs_verify:
            logger.info(f"[{client_id}] Quota reached 0 for mode={mode}, scheduling API verification")
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._verify_client_quota(client_id))
            except RuntimeError:
                logger.debug(f"[{client_id}] No running event loop, skipping async verification")

    async def _verify_client_quota(self, client_id: str) -> None:
        """Verify a client's quota by fetching rate limits from API."""
        try:
            with self._lock:
                wrapper = self.clients.get(client_id)
                if not wrapper:
                    return

            logger.info(f"[{client_id}] Verifying quota via API...")
            result = await wrapper.refresh_rate_limits()

            with self._lock:
                wrapper.last_check = time.time()

            self.save_state(writer="quota_verify")
            logger.info(f"[{client_id}] Quota verification complete: pro_remaining={result.get('pro_remaining')}")

        except Exception as e:
            logger.warning(f"[{client_id}] Quota verification failed: {e}")

    def mark_client_failure(self, client_id: str) -> None:
        """Mark a client as failed after a request."""
        with self._lock:
            wrapper = self.clients.get(client_id)
            if wrapper:
                wrapper.mark_failure()

    def get_status(self) -> Dict[str, Any]:
        """
        Get detailed status of the entire pool.

        Returns:
            Dict with total, available, mode, and client details
        """
        with self._lock:
            clients_status = [
                wrapper.get_status() for wrapper in self.clients.values()
            ]
            available_count = sum(
                1 for wrapper in self.clients.values() if wrapper.is_available()
            )

            return {
                "total": len(self.clients),
                "available": available_count,
                "mode": self._mode,
                "clients": clients_status,
            }

    def get_earliest_available_time(self) -> Optional[str]:
        """Get the earliest time any client will become available."""
        with self._lock:
            if not self.clients:
                return None

            # Check if any client is currently available
            for wrapper in self.clients.values():
                if wrapper.is_available():
                    return None

            # Find the earliest available time
            earliest = min(self.clients.values(), key=lambda w: w.available_after)
            return datetime.fromtimestamp(
                earliest.available_after, tz=timezone.utc
            ).isoformat()

    def get_client_user_info(self, client_id: str) -> Dict[str, Any]:
        """
        Get user session information for a specific client.

        Returns:
            Dict with user info or error message
        """
        with self._lock:
            wrapper = self.clients.get(client_id)
            if not wrapper:
                return {"status": "error", "message": f"Client '{client_id}' not found"}
        # HTTP call outside lock to avoid blocking pool operations
        return {"status": "ok", "data": wrapper.get_user_info()}

    def get_all_clients_user_info(self) -> Dict[str, Any]:
        """
        Get user session information for all clients.

        Returns:
            Dict with client_id -> user_info mapping
        """
        with self._lock:
            wrappers = list(self.clients.items())
        # HTTP calls outside lock to avoid blocking pool operations
        result = {}
        for client_id, wrapper in wrappers:
            result[client_id] = wrapper.get_user_info()
        return {"status": "ok", "data": result}

    # ==================== Monitor Methods ====================

    def get_monitor_config(self) -> Dict[str, Any]:
        """Get the current monitor configuration."""
        return self._monitor_config.copy()

    def update_monitor_config(self, new_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update monitor configuration and save to config file.

        Args:
            new_config: Dict with configuration fields to update

        Returns:
            Dict with status and updated config
        """
        old_enable = self._monitor_config.get("enable", False)
        old_interval = self._monitor_config.get("interval", 6)

        # Update in-memory config
        for key in ["enable", "interval", "tg_bot_token", "tg_chat_id"]:
            if key in new_config:
                self._monitor_config[key] = new_config[key]

        new_enable = self._monitor_config.get("enable", False)
        new_interval = self._monitor_config.get("interval", 6)

        # Hot-reload: if enabled and (was disabled or interval changed), restart
        if new_enable and (not old_enable or old_interval != new_interval):
            logger.info("Monitor config changed, restarting monitor task...")
            self.stop_monitor()
            self.start_monitor()

        if self._config_path:
            self._save_config()

        return {"status": "ok", "config": self._monitor_config.copy()}

    def is_monitor_enabled(self) -> bool:
        """Check if monitor is enabled."""
        return self._monitor_config.get("enable", False)

    # ==================== Fallback Methods ====================

    def get_fallback_config(self) -> Dict[str, Any]:
        """Get the current fallback configuration."""
        return self._fallback_config.copy()

    def is_fallback_to_auto_enabled(self) -> bool:
        """Check if fallback to auto mode is enabled."""
        return self._fallback_config.get("fallback_to_auto", True)

    def update_fallback_config(self, new_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update fallback configuration and save to config file.

        Args:
            new_config: Dict with configuration fields to update

        Returns:
            Dict with status and updated config
        """
        # Update in-memory config
        if "fallback_to_auto" in new_config:
            self._fallback_config["fallback_to_auto"] = new_config["fallback_to_auto"]

        if self._config_path:
            self._save_config()

        return {"status": "ok", "config": self._fallback_config.copy()}

    async def _send_telegram_notification(self, message: str) -> None:
        """Send a notification to Telegram."""
        bot_token = self._monitor_config.get("tg_bot_token")
        chat_id = self._monitor_config.get("tg_chat_id")

        if not bot_token or not chat_id:
            logger.warning("Telegram notification skipped: tg_bot_token or tg_chat_id not configured")
            return

        try:
            import aiohttp
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to send Telegram notification: {await resp.text()}")
                    else:
                        logger.info(f"Telegram notification sent: {message}")
        except ImportError:
            logger.warning("aiohttp not installed, Telegram notification skipped")
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")

    async def test_client(self, client_id: str) -> Dict[str, Any]:
        """
        Test a single client using rate-limit API (no queries consumed).

        Flow:
        1. get_user_info() — verify session is valid
        2. get_rate_limits() — fetch precise per-mode quotas
        3. session_valid + rate_limits are set; state is computed automatically

        Returns:
            Dict with status, state, and rate_limits
        """
        with self._lock:
            wrapper = self.clients.get(client_id)
            if not wrapper:
                return {"status": "error", "message": f"Client '{client_id}' not found"}
            client = wrapper.client

        prev_state = wrapper.state
        logger.debug(f"[{client_id}] Starting health check (rate-limit API), prev_state={prev_state}")

        try:
            # Step 1: Verify session is valid
            logger.debug(f"[{client_id}] Fetching user_info...")
            user_info = await asyncio.to_thread(client.get_user_info)
            is_logged_in = user_info and user_info.get("user")
            logger.debug(f"[{client_id}] is_logged_in={is_logged_in}")

            if not is_logged_in:
                with self._lock:
                    wrapper.session_valid = False
                    wrapper.last_check = time.time()
                logger.warning(f"Client '{client_id}' session invalid (not logged in)")

                if prev_state != "offline":
                    await self._send_telegram_notification(
                        f"⚠️ perplexity mcp: <b>{client_id}</b> session invalid."
                    )
                return {"status": "error", "state": "offline", "client_id": client_id,
                        "error": "Session invalid (not logged in)"}

            # Step 2: Fetch rate limits (zero quota consumption)
            logger.debug(f"[{client_id}] Fetching rate limits...")
            rate_limits = await asyncio.to_thread(client.get_rate_limits)
            logger.debug(f"[{client_id}] rate_limits: {rate_limits}")

            with self._lock:
                wrapper.session_valid = True
                wrapper.rate_limits = rate_limits
                wrapper.rate_limits_updated = time.time()
                wrapper.last_check = time.time()

            new_state = wrapper.state  # computed property
            logger.info(f"[{client_id}] Health check: {prev_state} -> {new_state} "
                        f"(pro_remaining={rate_limits.get('pro_remaining')})")

            # Telegram notification on state change
            if new_state == "exhausted" and prev_state != "exhausted":
                await self._send_telegram_notification(
                    f"⚠️ perplexity mcp: <b>{client_id}</b> pro quota exhausted."
                )
            elif new_state == "normal" and prev_state == "exhausted":
                await self._send_telegram_notification(
                    f"✅ perplexity mcp: <b>{client_id}</b> recovered (pro quota available)."
                )

            return {"status": "ok", "state": new_state, "client_id": client_id,
                    "rate_limits": rate_limits}

        except Exception as e:
            with self._lock:
                wrapper.session_valid = False
                wrapper.last_check = time.time()
            logger.error(f"Health check failed for client '{client_id}': {e}")

            if prev_state != "offline":
                await self._send_telegram_notification(
                    f"⚠️ perplexity mcp: <b>{client_id}</b> test failed."
                )

            return {"status": "error", "state": "offline", "client_id": client_id, "error": str(e)}

    async def test_all_clients(self) -> Dict[str, Any]:
        """
        Test all clients in the pool with concurrent execution.

        Uses asyncio.Semaphore to limit concurrency to 5 simultaneous tests
        to prevent rate limiting while improving overall test performance.

        Returns:
            Dict with status and results for each client
        """
        results: Dict[str, Any] = {}
        client_ids = list(self.clients.keys())

        if not client_ids:
            logger.info("No clients to test")
            return {"status": "ok", "results": results}

        logger.info(f"Starting concurrent test for {len(client_ids)} clients (max concurrency: 5)")

        # Limit concurrent tests to 5 to prevent rate limiting
        semaphore = asyncio.Semaphore(5)
        completed_count = 0

        async def test_with_limit(client_id: str) -> Tuple[str, Dict[str, Any]]:
            nonlocal completed_count
            logger.info(f"Testing client '{client_id}'...")
            async with semaphore:
                result = await self.test_client(client_id)
                completed_count += 1
                status = result.get("status", "unknown")
                state = result.get("state", "unknown")
                logger.info(
                    f"Client '{client_id}' test completed ({completed_count}/{len(client_ids)}): "
                    f"status={status}, state={state}"
                )
                # Small delay after each test to prevent burst requests
                await asyncio.sleep(0.5)
                return client_id, result

        # Run all tests concurrently (semaphore limits to 5 at a time)
        tasks = [test_with_limit(cid) for cid in client_ids]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        for item in completed:
            if isinstance(item, Exception):
                # Log unexpected errors but continue processing
                logger.error(f"Unexpected error during concurrent test: {item}")
                continue
            client_id, result = item
            results[client_id] = result

        # Summary log
        success_count = sum(1 for r in results.values() if r.get("status") == "ok")
        fail_count = len(results) - success_count
        logger.info(
            f"Concurrent test completed: {len(results)} clients tested, "
            f"{success_count} succeeded, {fail_count} failed"
        )

        # Persist state for cross-process sharing
        self.save_state(writer="monitor")

        return {"status": "ok", "results": results}

    async def refresh_all_rate_limits(self) -> dict:
        """Refresh rate limits for all clients via API (no queries consumed)."""
        results = {}
        for client_id, wrapper in self.clients.items():
            try:
                limits = await asyncio.to_thread(wrapper.client.get_rate_limits)
                with self._lock:
                    wrapper.rate_limits = limits
                    wrapper.rate_limits_updated = time.time()
                    if wrapper.session_valid is None:
                        wrapper.session_valid = True  # API responded, session works
                    wrapper.last_check = time.time()

                pro_remaining = limits.get("pro_remaining")
                results[client_id] = limits
                logger.info(f"[{client_id}] Rate limits refreshed: pro_remaining={pro_remaining}")
            except Exception as e:
                logger.warning(f"[{client_id}] Rate limit refresh failed: {e}")
                results[client_id] = {"error": str(e)}

        self.save_state(writer="rate_limit_check")
        return results

    def get_accounts_with_research_quota(self) -> list:
        """Get list of client IDs that have research quota remaining."""
        result = []
        with self._lock:
            for client_id, wrapper in self.clients.items():
                if not wrapper.enabled:
                    continue
                modes = wrapper.rate_limits.get("modes", {})
                research = modes.get("research", {})
                if research.get("available", True):
                    remaining = research.get("remaining")
                    # None means not tracked (assume available), > 0 means has quota
                    if remaining is None or remaining > 0:
                        result.append(client_id)
        return result

    async def _monitor_loop(self) -> None:
        """Background task that periodically tests all clients."""
        logger.info("Monitor loop started")

        while True:
            interval_hours = self._monitor_config.get("interval", 6)
            interval_seconds = interval_hours * 3600

            try:
                logger.info(f"Starting health check for all clients (interval: {interval_hours}h)...")
                try:
                    await asyncio.wait_for(self.test_all_clients(), timeout=600)
                    logger.info("Health check completed")
                except asyncio.TimeoutError:
                    logger.error("Health check timed out after 10 minutes, forcing next cycle")
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")

            await asyncio.sleep(interval_seconds)

    def start_monitor(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> bool:
        """
        Start the monitor background task.

        Args:
            loop: Optional event loop to use. If not provided, will try to get the running loop.

        Returns:
            True if monitor was started, False if disabled or already running
        """
        if not self.is_monitor_enabled():
            logger.info("Monitor is disabled, not starting")
            return False

        if self._monitor_task and not self._monitor_task.done():
            logger.info("Monitor task already running")
            return False

        try:
            if loop is None:
                loop = asyncio.get_running_loop()
            self._monitor_task = loop.create_task(self._monitor_loop())
            logger.info("Monitor task started")
            return True
        except RuntimeError:
            logger.warning("No running event loop, monitor not started")
            return False

    def stop_monitor(self) -> bool:
        """
        Stop the monitor background task.

        Returns:
            True if monitor was stopped, False if not running
        """
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            logger.info("Monitor task stopped")
            return True
        return False

    # ==================== Export/Import Methods ====================

    def export_config(self) -> Dict[str, Any]:
        """
        Export the current token pool configuration.

        Returns:
            Dict containing tokens, monitor, and fallback configuration
        """
        with self._lock:
            tokens = []
            for client_id, wrapper in self.clients.items():
                # Get the cookies from the client
                client = wrapper.client
                cookies = client._cookies if hasattr(client, '_cookies') else {}

                tokens.append({
                    "id": client_id,
                    "csrf_token": cookies.get("next-auth.csrf-token", ""),
                    "session_token": cookies.get("__Secure-next-auth.session-token", ""),
                })

            return {
                "monitor": self._monitor_config.copy(),
                "fallback": self._fallback_config.copy(),
                "tokens": tokens,
            }

    def export_single_client(self, client_id: str) -> List[Dict[str, Any]]:
        """
        Export a single client's token configuration as array.

        Args:
            client_id: The ID of the client to export

        Returns:
            List containing the single token configuration
        """
        with self._lock:
            wrapper = self.clients.get(client_id)
            if not wrapper:
                return []

            client = wrapper.client
            cookies = client._cookies if hasattr(client, '_cookies') else {}

            return [{
                "id": client_id,
                "csrf_token": cookies.get("next-auth.csrf-token", ""),
                "session_token": cookies.get("__Secure-next-auth.session-token", ""),
            }]

    def import_config(self, config: Any) -> Dict[str, Any]:
        """
        Import token pool configuration, adding new tokens.

        Args:
            config: List of tokens or Dict containing tokens array

        Returns:
            Dict with status and message
        """
        # Support both array format and object format
        if isinstance(config, list):
            tokens = config
        else:
            tokens = config.get("tokens", [])

        if not tokens:
            return {"status": "error", "message": "No tokens found in config"}

        added = []
        skipped = []
        errors = []

        for token_entry in tokens:
            client_id = token_entry.get("id")
            csrf_token = token_entry.get("csrf_token")
            session_token = token_entry.get("session_token")

            if not all([client_id, csrf_token, session_token]):
                errors.append(f"Invalid token entry: missing required fields")
                continue

            result = self.add_client(client_id, csrf_token, session_token)
            if result.get("status") == "ok":
                added.append(client_id)
            else:
                if "already exists" in result.get("message", ""):
                    skipped.append(client_id)
                else:
                    errors.append(f"{client_id}: {result.get('message')}")

        # Save to config file if available
        if self._config_path and added:
            self._save_config()

        message_parts = []
        if added:
            message_parts.append(f"Added: {len(added)} token(s)")
        if skipped:
            message_parts.append(f"Skipped: {len(skipped)} (already exist)")
        if errors:
            message_parts.append(f"Errors: {len(errors)}")

        return {
            "status": "ok" if added or skipped else "error",
            "message": "; ".join(message_parts) if message_parts else "No tokens processed",
            "added": added,
            "skipped": skipped,
            "errors": errors,
        }

    def _save_config(self) -> None:
        """Save the current configuration to the config file."""
        if not self._config_path:
            return
        if not self._config_writable:
            logger.debug("Config is read-only, skipping save")
            return

        try:
            config = {
                "monitor": self._monitor_config.copy(),
                "fallback": self._fallback_config.copy(),
                "tokens": [],
            }

            # Acquire lock briefly to get a snapshot of clients, avoiding deadlock
            # (callers may already hold the lock). Read-only + GIL makes this safe.
            with self._lock:
                clients_copy = list(self.clients.items())

            for client_id, wrapper in clients_copy:
                client = wrapper.client
                # Use _cookies (original input cookies), not session jar
                # Session jar may transform cookie names after HTTP requests
                cookies = client._cookies if hasattr(client, '_cookies') else {}

                csrf = cookies.get("next-auth.csrf-token", "")
                session = cookies.get("__Secure-next-auth.session-token", "")
                logger.debug(f"[{client_id}] Saving config with cookies: csrf={csrf[:15]}... session={session[:15]}...")

                config["tokens"].append({
                    "id": client_id,
                    "csrf_token": csrf,
                    "session_token": session,
                })

            dir_name = os.path.dirname(self._config_path) or "."
            fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, self._config_path)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

            # Update mtime so reload_config() doesn't re-read our own write
            try:
                self._config_file_mtime = os.path.getmtime(self._config_path)
            except OSError:
                pass
            logger.info(f"Config saved to {self._config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    # ==================== Shared State Persistence ====================

    def _state_file_path(self) -> Optional[str]:
        """Get path to pool_state.json, derived from config file location."""
        if not self._config_path:
            return None
        return os.path.join(os.path.dirname(self._config_path), "pool_state.json")

    def save_state(self, writer: str = "unknown") -> None:
        """Save runtime state (account health) for cross-process sharing.

        Uses atomic write (tempfile + os.replace) to prevent corruption.
        Only saves state and last_check — backoff stays per-process.
        """
        state_path = self._state_file_path()
        if state_path is None:
            return

        try:
            state = {
                "version": 2,
                "updated_at": time.time(),
                "writer": writer,
                "clients": {},
            }

            with self._lock:
                for client_id, wrapper in self.clients.items():
                    state["clients"][client_id] = {
                        "session_valid": wrapper.session_valid,
                        "state": wrapper.state,  # computed, for backward compat
                        "last_check": wrapper.last_check,
                        "rate_limits": wrapper.rate_limits,
                    }

            dir_name = os.path.dirname(state_path) or "."
            fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2)
                os.replace(tmp_path, state_path)
                logger.info(f"Pool state saved to {state_path} (writer={writer})")
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

        except Exception as e:
            logger.error(f"Failed to save pool state: {e}")

    def load_state(self) -> bool:
        """Load runtime state from pool_state.json, applying state and last_check.

        Only re-reads the file if its mtime has changed (cheap os.stat check).
        Returns True if state was loaded, False if unchanged or not found.
        """
        state_path = self._state_file_path()
        if state_path is None or not os.path.exists(state_path):
            return False

        try:
            current_mtime = os.path.getmtime(state_path)
            if current_mtime == self._state_file_mtime:
                return False

            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)

            version = state.get("version", 1)
            if version not in (1, 2):
                logger.warning(f"Unknown state file version: {version}")
                return False

            clients_state = state.get("clients", {})

            with self._lock:
                for client_id, client_state in clients_state.items():
                    wrapper = self.clients.get(client_id)
                    if wrapper is None:
                        continue

                    new_check = client_state.get("last_check") or client_state.get("last_heartbeat")
                    if new_check is not None:
                        wrapper.last_check = new_check

                    # Load session_valid (new format) or derive from legacy state
                    sv = client_state.get("session_valid")
                    if sv is not None:
                        old_sv = wrapper.session_valid
                        wrapper.session_valid = sv
                        if old_sv != sv:
                            logger.info(f"[{client_id}] session_valid updated: {old_sv} -> {sv}")
                    else:
                        # Backward compat: derive from old "state" field
                        legacy_state = client_state.get("state")
                        if legacy_state == "offline":
                            wrapper.session_valid = False
                        elif legacy_state in ("normal", "downgrade"):
                            wrapper.session_valid = True

                    # v2: load rate_limits if present
                    if version >= 2:
                        rate_limits = client_state.get("rate_limits")
                        if rate_limits:
                            wrapper.rate_limits = rate_limits

            self._state_file_mtime = current_mtime
            updated_at = state.get("updated_at", 0)
            age_seconds = time.time() - updated_at
            logger.debug(
                f"Pool state loaded from {state_path} "
                f"(age={age_seconds:.0f}s, writer={state.get('writer', '?')})"
            )
            return True

        except json.JSONDecodeError as e:
            logger.warning(f"Corrupted state file, ignoring: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to load pool state: {e}")
            return False

    def reload_config(self) -> bool:
        """Re-read token_pool_config.json if it changed, adding/removing clients.

        Only re-reads if the file mtime has changed (cheap os.stat check).
        Returns True if config was reloaded, False if unchanged or not found.
        """
        if not self._config_path or not os.path.exists(self._config_path):
            return False

        try:
            current_mtime = os.path.getmtime(self._config_path)
            if current_mtime == self._config_file_mtime:
                return False

            with open(self._config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            tokens = config.get("tokens", [])
            config_ids = set()

            for token_entry in tokens:
                client_id = token_entry.get("id")
                csrf_token = token_entry.get("csrf_token")
                session_token = token_entry.get("session_token")

                if not all([client_id, csrf_token, session_token]):
                    continue

                config_ids.add(client_id)

                with self._lock:
                    if client_id not in self.clients:
                        # New token — add it
                        cookies = {
                            "next-auth.csrf-token": csrf_token,
                            "__Secure-next-auth.session-token": session_token,
                        }
                        self._add_client_internal(client_id, cookies)
                        logger.info(f"[{client_id}] Hot-reloaded new client from config")

            # Remove clients that were deleted from config
            with self._lock:
                removed = [cid for cid in self.clients if cid not in config_ids]
                for cid in removed:
                    if len(self.clients) <= 1:
                        break  # Keep at least one client
                    del self.clients[cid]
                    self._rotation_order.remove(cid)
                    if self._index >= len(self._rotation_order):
                        self._index = 0
                    logger.info(f"[{cid}] Removed client (no longer in config)")

            # Update fallback config if changed
            fallback = config.get("fallback")
            if fallback and isinstance(fallback, dict):
                self._fallback_config = {
                    "fallback_to_auto": fallback.get("fallback_to_auto", True)
                }

            self._config_file_mtime = current_mtime
            logger.info(f"Config reloaded from {self._config_path} "
                        f"(tokens: {len(config_ids)}, pool: {len(self.clients)})")
            return True

        except json.JSONDecodeError as e:
            logger.warning(f"Corrupted config file, ignoring: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to reload config: {e}")
            return False

    def is_state_stale(self, max_age_hours: Optional[float] = None) -> bool:
        """Check if shared state is stale or missing.

        Returns True if: no state file, or updated_at older than max_age_hours.
        Default max_age uses the monitor interval from config.
        """
        state_path = self._state_file_path()
        if state_path is None or not os.path.exists(state_path):
            return True

        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)

            updated_at = state.get("updated_at", 0)
            if max_age_hours is None:
                max_age_hours = self._monitor_config.get("interval", 6)

            age_seconds = time.time() - updated_at
            return age_seconds > (max_age_hours * 3600)

        except Exception:
            return True

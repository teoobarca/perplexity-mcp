# Bugfix Audit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix critical and important bugs found during the codebase audit — config persistence, mutable defaults, rotation logic, error classification, blocking I/O in locks, and crash on dropped connections.

**Architecture:** Fix bugs in priority order (critical first). Each task is independent and can be committed separately. Tests are added for each fix where applicable.

**Tech Stack:** Python (pytest), curl_cffi

---

### Task 1: Make `_save_config` atomic (prevent corruption on crash)

`_save_config` writes directly to the config file. A crash mid-write = lost config. `save_state` already uses atomic writes — apply the same pattern.

**Files:**
- Modify: `perplexity/server/client_pool.py:1137-1175`

**Step 1: Replace the direct write with atomic write**

Change lines 1170-1171 from:
```python
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
```
to:
```python
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
```

**Step 2: Run tests**

Run: `.venv/bin/python -m pytest tests/test_client_pool.py -v`
Expected: All pass

**Step 3: Commit**

```bash
git add perplexity/server/client_pool.py
git commit -m "fix: make _save_config atomic with tempfile + os.replace"
```

---

### Task 2: Stop calling `_save_config` on every successful request

`mark_client_success` calls `_save_config` on every request "to persist cookies", but `_save_config` reads `_cookies` (the original immutable input), so this is a no-op that just creates I/O and race condition risk. Only `save_state` (which persists quotas) is needed.

**Files:**
- Modify: `perplexity/server/client_pool.py:452-484`

**Step 1: Remove the unnecessary `_save_config` call from `mark_client_success`**

Remove lines 466-471:
```python
        # After a successful request, persist the latest cookies from the session
        if self._config_path:
            logger.debug(f"[{client_id}] Request successful, triggering config save to persist cookies")
            self._save_config()
        else:
            logger.debug(f"[{client_id}] Request successful, but no config path set, skipping save")
```

**Step 2: Run tests**

Run: `.venv/bin/python -m pytest tests/test_client_pool.py -v`
Expected: All pass

**Step 3: Commit**

```bash
git add perplexity/server/client_pool.py
git commit -m "fix: stop calling _save_config on every request (no-op, creates race conditions)"
```

---

### Task 3: Fix mutable default argument `cookies={}`

Classic Python bug. The shared `{}` default is passed to `requests.Session(cookies=cookies)` which may mutate it.

**Files:**
- Modify: `perplexity/client.py:46`
- Modify: `perplexity/client.py:150-156` (`search` method)

**Step 1: Fix `Client.__init__`**

Change line 46:
```python
    def __init__(self, cookies={}):
```
to:
```python
    def __init__(self, cookies=None):
```

Change line 55:
```python
        self._cookies = cookies.copy() if cookies else {}
```
to:
```python
        if cookies is None:
            cookies = {}
        self._cookies = cookies.copy()
```

Change line 60:
```python
        cookies=cookies,
```
stays the same (now refers to the local variable, not the shared default).

Change line 66:
```python
        self.own = bool(cookies)  # Indicates if the client uses its own account
```
stays the same (empty dict is falsy, so `Client(None)` and `Client({})` both produce `self.own = False`).

**Step 2: Fix `Client.search`**

Change lines 155-156:
```python
        sources=["web"],
        files={},
```
to:
```python
        sources=None,
        files=None,
```

Add at the top of the method body (after the docstring):
```python
        if sources is None:
            sources = ["web"]
        if files is None:
            files = {}
```

**Step 3: Run tests**

Run: `.venv/bin/python -m pytest tests/ -v -k "not test_mcp and not test_oai and not test_retry"`
Expected: All pass

**Step 4: Commit**

```bash
git add perplexity/client.py
git commit -m "fix: replace mutable default arguments with None"
```

---

### Task 4: Fix rotation loop that skips clients

The `for _ in range(total_clients)` loop burns iterations on duplicates via `continue`, potentially missing clients. Fix by tracking all seen IDs and looping until all distinct clients are seen.

**Files:**
- Modify: `perplexity/server/app.py:164-252`

**Step 1: Replace the rotation loop**

Change lines 168-169 from:
```python
    last_error = None
    total_clients = len(pool.clients)

    # Try up to total_clients times to ensure we attempt all available clients
    for _ in range(total_clients):
        client_id, client = pool.get_client()

        if client is None:
            # All clients are in backoff or none exist
            if not attempted_clients:
                earliest = pool.get_earliest_available_time()
                last_error = Exception(f"All clients are currently unavailable. Earliest available at: {earliest}")
            break

        if client_id in attempted_clients or client_id in [c[0] for c in skipped_downgraded_clients]:
            continue
```
to:
```python
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
```

Also change line 182 (the old skip for already-attempted/downgraded) — it's replaced by the `seen_ids` check above. The `attempted_clients` and `skipped_downgraded_clients` tracking stays for its original purpose (deciding what to do with the client after selection).

After the `seen_ids.add(client_id)` line, add back the downgrade skip logic:
```python
        # Check client state
        client_state = pool.get_client_state(client_id)
        ...
```
(rest stays the same)

**Step 2: Run tests**

Run: `.venv/bin/python -m pytest tests/test_client_pool.py tests/test_config.py tests/test_utils.py -v`
Expected: All pass

**Step 3: Commit**

```bash
git add perplexity/server/app.py
git commit -m "fix: rotation loop no longer skips clients on duplicate iterations"
```

---

### Task 5: Fix error keyword matching (too broad)

`"pro"` matches "provide", "process", etc. Use word boundary matching instead.

**Files:**
- Modify: `perplexity/server/app.py:226,248`

**Step 1: Write a helper function**

Add at module level (before `run_query`):
```python
import re

_CLIENT_LIMIT_PATTERN = re.compile(
    r'\b(pro queries|pro search|rate.?limit|quota|remaining|file upload)\b',
    re.IGNORECASE,
)
```

**Step 2: Replace the keyword matching**

Change line 226:
```python
            is_client_limit = any(kw in error_msg for kw in ["pro", "limit", "account", "upload", "quota", "remaining"])
```
to:
```python
            is_client_limit = bool(_CLIENT_LIMIT_PATTERN.search(error_msg))
```

Change line 248:
```python
            if mode == "pro" and any(kw in error_msg for kw in ["pro", "quota", "limit", "remaining"]):
```
to:
```python
            if mode == "pro" and _CLIENT_LIMIT_PATTERN.search(error_msg):
```

**Step 3: Write test**

Add to `tests/test_utils.py`:
```python
def test_client_limit_pattern_matches_correctly():
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
```

**Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_utils.py -v`
Expected: All pass

**Step 5: Commit**

```bash
git add perplexity/server/app.py tests/test_utils.py
git commit -m "fix: use regex word boundaries for error classification instead of substring matching"
```

---

### Task 6: Fix blocking HTTP call inside lock (`get_client_user_info`)

Both `get_client_user_info` and `get_all_clients_user_info` make HTTP calls while holding the pool lock. Move the HTTP call outside the lock.

**Files:**
- Modify: `perplexity/server/client_pool.py:569-609`

**Step 1: Fix `get_client_user_info`**

Change:
```python
    def get_client_user_info(self, client_id: str) -> Dict[str, Any]:
        with self._lock:
            wrapper = self.clients.get(client_id)
            if not wrapper:
                return {"status": "error", "message": f"Client '{client_id}' not found"}
            return {"status": "ok", "data": wrapper.get_user_info()}
```
to:
```python
    def get_client_user_info(self, client_id: str) -> Dict[str, Any]:
        with self._lock:
            wrapper = self.clients.get(client_id)
            if not wrapper:
                return {"status": "error", "message": f"Client '{client_id}' not found"}
        # HTTP call outside lock to avoid blocking pool operations
        return {"status": "ok", "data": wrapper.get_user_info()}
```

**Step 2: Fix `get_all_clients_user_info`**

Change:
```python
    def get_all_clients_user_info(self) -> Dict[str, Any]:
        with self._lock:
            result = {}
            for client_id, wrapper in self.clients.items():
                result[client_id] = wrapper.get_user_info()
            return {"status": "ok", "data": result}
```
to:
```python
    def get_all_clients_user_info(self) -> Dict[str, Any]:
        with self._lock:
            wrappers = list(self.clients.items())
        # HTTP calls outside lock to avoid blocking pool operations
        result = {}
        for client_id, wrapper in wrappers:
            result[client_id] = wrapper.get_user_info()
        return {"status": "ok", "data": result}
```

**Step 3: Run tests**

Run: `.venv/bin/python -m pytest tests/test_client_pool.py -v`
Expected: All pass

**Step 4: Commit**

```bash
git add perplexity/server/client_pool.py
git commit -m "fix: move blocking HTTP calls outside pool lock in get_user_info methods"
```

---

### Task 7: Handle `None` return from `Client.search()` on dropped connection

If the SSE stream ends without `end_of_stream`, `search()` implicitly returns `None`. `extract_clean_result(None)` then crashes with `AttributeError`.

**Files:**
- Modify: `perplexity/server/app.py:206-221`

**Step 1: Add None check after `client.search()`**

Change:
```python
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

            # Success
            pool.mark_client_success(client_id, mode=mode)
            clean_result = extract_clean_result(response)
```
to:
```python
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
```

Do the same for the fallback search (~line 282):
```python
            if response and "answer" in response:
```
This already handles `None` (falsy), so no change needed for the fallback path.

**Step 2: Run tests**

Run: `.venv/bin/python -m pytest tests/test_client_pool.py tests/test_config.py tests/test_utils.py -v`
Expected: All pass

**Step 3: Commit**

```bash
git add perplexity/server/app.py
git commit -m "fix: handle None response from search() on dropped connection"
```

---

### Task 8: Replace `assert` with proper exceptions in `Client.search()`

`assert` is stripped with `-O` flag and raises `AssertionError` instead of `ValidationError`.

**Files:**
- Modify: `perplexity/client.py:176-206`

**Step 1: Replace assert statements with ValidationError raises**

First, add import at the top of `client.py`:
```python
from .exceptions import ValidationError
```

Then replace lines 177-206:
```python
        assert mode in ["auto", "pro", "reasoning", "deep research"], "Invalid search mode."
        assert (model in {...}[mode] if self.own else True), "Invalid model for the selected mode."
        assert all([source in ("web", "scholar", "social") for source in sources]), "Invalid sources."
        assert (self.copilot > 0 if mode in ["pro", "reasoning", "deep research"] else True), "No remaining pro queries."
        assert self.file_upload - len(files) >= 0 if files else True, "File upload limit exceeded."
```
with:
```python
        valid_modes = ("auto", "pro", "reasoning", "deep research")
        if mode not in valid_modes:
            raise ValidationError(f"Invalid search mode '{mode}'. Choose from: {', '.join(valid_modes)}")

        valid_models = {
            "auto": [None],
            "pro": [None, "sonar", "gpt-5.2", "claude-4.5-sonnet", "grok-4.1"],
            "reasoning": [None, "gpt-5.2-thinking", "claude-4.5-sonnet-thinking", "gemini-3.0-pro", "kimi-k2-thinking", "grok-4.1-reasoning"],
            "deep research": [None],
        }
        if self.own and model not in valid_models[mode]:
            raise ValidationError(f"Invalid model '{model}' for mode '{mode}'.")

        if not all(source in ("web", "scholar", "social") for source in sources):
            raise ValidationError("Invalid sources. Choose from: web, scholar, social")

        if mode in ("pro", "reasoning", "deep research") and self.copilot <= 0:
            raise ValidationError("No remaining pro queries.")

        if files and self.file_upload - len(files) < 0:
            raise ValidationError("File upload limit exceeded.")
```

**Step 2: Run tests**

Run: `.venv/bin/python -m pytest tests/ -v -k "not test_mcp and not test_oai and not test_retry"`
Expected: All pass

**Step 3: Commit**

```bash
git add perplexity/client.py
git commit -m "fix: replace assert with ValidationError in Client.search()"
```

---

### Task 9: Final verification

**Step 1: Run full test suite**

Run: `.venv/bin/python -m pytest tests/test_client_pool.py tests/test_config.py tests/test_utils.py -v`
Expected: All pass

**Step 2: Build frontend**

Run: `cd perplexity/server/web && npm run build`
Expected: Build succeeds

**Step 3: Verify import chain works**

Run: `.venv/bin/python -c "from perplexity.server.app import run_query; from perplexity.server.admin import routes; print('OK')"`
Expected: `OK`

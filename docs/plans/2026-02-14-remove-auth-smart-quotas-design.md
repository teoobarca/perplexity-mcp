# Remove Auth + Smart Quotas Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove admin token authentication from all endpoints and add smart quota decrement after each MCP request with API verification when quotas hit zero.

**Architecture:** Two independent changes: (1) Strip all ADMIN_TOKEN auth checks from backend endpoints and all auth UI/logic from React frontend. (2) Extend `mark_client_success()` with a `mode` parameter to locally decrement the correct quota counter, trigger API verification when counter hits 0, and persist state to `pool_state.json`.

**Tech Stack:** Python/Starlette backend, React/TypeScript frontend, pytest tests

---

### Task 1: Write failing test for smart quota decrement

**Files:**
- Modify: `tests/test_client_pool.py`

**Step 1: Write the failing test**

Add to `TestClientWrapper` class:

```python
def test_decrement_quota_pro_mode(self):
    """Test that decrement_quota decreases pro counters for pro mode."""
    from perplexity.server.client_pool import ClientWrapper

    mock_client = MagicMock()
    wrapper = ClientWrapper(mock_client, "test-id")
    wrapper.rate_limits = {
        "pro_remaining": 5,
        "modes": {
            "pro_search": {"available": True, "remaining": 5, "kind": "daily"},
        },
    }

    needs_verify = wrapper.decrement_quota("pro")

    assert wrapper.rate_limits["pro_remaining"] == 4
    assert wrapper.rate_limits["modes"]["pro_search"]["remaining"] == 4
    assert needs_verify is False

def test_decrement_quota_pro_reaches_zero(self):
    """Test that decrement_quota returns True when pro counter hits 0."""
    from perplexity.server.client_pool import ClientWrapper

    mock_client = MagicMock()
    wrapper = ClientWrapper(mock_client, "test-id")
    wrapper.rate_limits = {
        "pro_remaining": 1,
        "modes": {
            "pro_search": {"available": True, "remaining": 1, "kind": "daily"},
        },
    }

    needs_verify = wrapper.decrement_quota("pro")

    assert wrapper.rate_limits["pro_remaining"] == 0
    assert wrapper.rate_limits["modes"]["pro_search"]["remaining"] == 0
    assert needs_verify is True

def test_decrement_quota_research_mode(self):
    """Test that decrement_quota decreases research counter for deep research mode."""
    from perplexity.server.client_pool import ClientWrapper

    mock_client = MagicMock()
    wrapper = ClientWrapper(mock_client, "test-id")
    wrapper.rate_limits = {
        "pro_remaining": 10,
        "modes": {
            "research": {"available": True, "remaining": 3, "kind": "daily"},
        },
    }

    needs_verify = wrapper.decrement_quota("deep research")

    assert wrapper.rate_limits["modes"]["research"]["remaining"] == 2
    assert needs_verify is False

def test_decrement_quota_research_reaches_zero(self):
    """Test that decrement_quota returns True when research counter hits 0."""
    from perplexity.server.client_pool import ClientWrapper

    mock_client = MagicMock()
    wrapper = ClientWrapper(mock_client, "test-id")
    wrapper.rate_limits = {
        "pro_remaining": 10,
        "modes": {
            "research": {"available": True, "remaining": 1, "kind": "daily"},
        },
    }

    needs_verify = wrapper.decrement_quota("deep research")

    assert wrapper.rate_limits["modes"]["research"]["remaining"] == 0
    assert needs_verify is True

def test_decrement_quota_reasoning_mode(self):
    """Test that reasoning mode decrements pro counters (same as pro)."""
    from perplexity.server.client_pool import ClientWrapper

    mock_client = MagicMock()
    wrapper = ClientWrapper(mock_client, "test-id")
    wrapper.rate_limits = {
        "pro_remaining": 3,
        "modes": {
            "pro_search": {"available": True, "remaining": 3, "kind": "daily"},
        },
    }

    needs_verify = wrapper.decrement_quota("reasoning")

    assert wrapper.rate_limits["pro_remaining"] == 2
    assert wrapper.rate_limits["modes"]["pro_search"]["remaining"] == 2
    assert needs_verify is False

def test_decrement_quota_no_rate_limits(self):
    """Test that decrement_quota handles missing rate_limits gracefully."""
    from perplexity.server.client_pool import ClientWrapper

    mock_client = MagicMock()
    wrapper = ClientWrapper(mock_client, "test-id")
    wrapper.rate_limits = {}

    needs_verify = wrapper.decrement_quota("pro")

    assert needs_verify is False

def test_decrement_quota_none_remaining(self):
    """Test that decrement_quota handles None remaining (untracked) gracefully."""
    from perplexity.server.client_pool import ClientWrapper

    mock_client = MagicMock()
    wrapper = ClientWrapper(mock_client, "test-id")
    wrapper.rate_limits = {
        "pro_remaining": None,
        "modes": {
            "pro_search": {"available": True, "remaining": None, "kind": None},
        },
    }

    needs_verify = wrapper.decrement_quota("pro")

    # None means untracked, should not decrement or trigger verify
    assert wrapper.rate_limits["pro_remaining"] is None
    assert needs_verify is False
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_client_pool.py -v -k "decrement_quota"`
Expected: FAIL with `AttributeError: 'ClientWrapper' object has no attribute 'decrement_quota'`

---

### Task 2: Implement `decrement_quota()` on ClientWrapper

**Files:**
- Modify: `perplexity/server/client_pool.py` (after `mark_pro_failure` method, ~line 68)

**Step 1: Implement the method**

Add to `ClientWrapper` class, after `mark_pro_failure()`:

```python
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
```

**Step 2: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_client_pool.py -v -k "decrement_quota"`
Expected: All 7 new tests PASS

**Step 3: Run full test suite**

Run: `.venv/bin/python -m pytest tests/test_client_pool.py tests/test_config.py tests/test_utils.py -v`
Expected: All 32+ tests PASS

**Step 4: Commit**

```bash
git add tests/test_client_pool.py perplexity/server/client_pool.py
git commit -m "feat: add decrement_quota() for smart local quota tracking"
```

---

### Task 3: Wire smart quota into mark_client_success and run_query

**Files:**
- Modify: `perplexity/server/client_pool.py:409-421` (`mark_client_success`)
- Modify: `perplexity/server/app.py:218` (call site in `run_query`)
- Modify: `perplexity/server/app.py:283` (fallback call site)

**Step 1: Update `mark_client_success` to accept `mode` and call `decrement_quota`**

In `client_pool.py`, change `mark_client_success`:

```python
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

    # After a successful request, persist the latest cookies from the session
    if self._config_path:
        logger.debug(f"[{client_id}] Request successful, triggering config save to persist cookies")
        self._save_config()
    else:
        logger.debug(f"[{client_id}] Request successful, but no config path set, skipping save")

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
```

**Step 2: Add `_verify_client_quota` helper**

Add to `ClientPool` class (after `mark_client_success`):

```python
async def _verify_client_quota(self, client_id: str) -> None:
    """Verify a client's quota by fetching rate limits from API."""
    try:
        with self._lock:
            wrapper = self.clients.get(client_id)
            if not wrapper:
                return

        logger.info(f"[{client_id}] Verifying quota via API...")
        result = await wrapper.refresh_rate_limits()

        # Update state based on refreshed limits
        with self._lock:
            pro_remaining = result.get("pro_remaining")
            modes = result.get("modes", {})
            pro_search = modes.get("pro_search", {})

            if pro_search.get("available") and (pro_remaining is None or pro_remaining > 0):
                wrapper.state = "normal"
            elif pro_remaining is not None and pro_remaining == 0:
                wrapper.state = "downgrade"

            wrapper.last_check = time.time()

        self.save_state(writer="quota_verify")
        logger.info(f"[{client_id}] Quota verification complete: pro_remaining={result.get('pro_remaining')}")

    except Exception as e:
        logger.warning(f"[{client_id}] Quota verification failed: {e}")
```

**Step 3: Update `run_query()` in `app.py` to pass `mode`**

Change line 218 from:
```python
pool.mark_client_success(client_id)
```
to:
```python
pool.mark_client_success(client_id, mode=mode)
```

Also change line 283 (fallback success) from:
```python
pool.mark_client_success(best_client_id)
```
to:
```python
pool.mark_client_success(best_client_id, mode="auto")
```

**Step 4: Run full test suite**

Run: `.venv/bin/python -m pytest tests/test_client_pool.py tests/test_config.py tests/test_utils.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add perplexity/server/client_pool.py perplexity/server/app.py
git commit -m "feat: wire smart quota decrement into request flow"
```

---

### Task 4: Remove auth from backend endpoints

**Files:**
- Modify: `perplexity/server/admin.py`

**Step 1: Remove all `ADMIN_TOKEN` auth checks from every endpoint**

For every endpoint function that has an auth check block, remove it. The pattern to remove is:

```python
from perplexity.config import ADMIN_TOKEN

if not ADMIN_TOKEN:
    return JSONResponse({...}, status_code=403)

provided_token = request.headers.get("X-Admin-Token")
if not provided_token or provided_token != ADMIN_TOKEN:
    return JSONResponse({...}, status_code=401)
```

Functions to update:
- `pool_export` — remove auth block (lines 41-54)
- `pool_export_single` — remove auth block (lines 62-75)
- `pool_import` — remove auth block (lines 84-97)
- `pool_api` — remove the `protected_actions` set and its auth check block (lines 125-149)
- `monitor_config` GET — remove auth block (lines 258-270)
- `monitor_config` POST — remove auth block (lines 279-290)
- `monitor_start` — remove auth block (lines 313-325)
- `monitor_stop` — remove auth block (lines 339-354)
- `monitor_test` — remove auth block (lines 364-380)
- `fallback_config` POST — remove auth block (lines 412-425)
- `logs_tail` — remove auth block (lines 472-488)

Also remove the `from perplexity.config import ADMIN_TOKEN` imports inside each function.

**Step 2: Run backend to verify no import errors**

Run: `.venv/bin/python -c "from perplexity.server.admin import routes; print(f'{len(routes)} routes loaded')"`
Expected: `16 routes loaded` (no errors)

**Step 3: Run full test suite**

Run: `.venv/bin/python -m pytest tests/test_client_pool.py tests/test_config.py tests/test_utils.py -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add perplexity/server/admin.py
git commit -m "feat: remove admin token auth from all endpoints"
```

---

### Task 5: Remove auth from frontend

**Files:**
- Delete: `perplexity/server/web/src/hooks/useAuth.ts`
- Delete: `perplexity/server/web/src/components/AuthBar.tsx`
- Modify: `perplexity/server/web/src/lib/api.ts`
- Modify: `perplexity/server/web/src/hooks/usePool.ts`
- Modify: `perplexity/server/web/src/hooks/useLogs.ts`
- Modify: `perplexity/server/web/src/components/App.tsx`
- Modify: `perplexity/server/web/src/components/TokenTable.tsx`
- Modify: `perplexity/server/web/src/components/MonitorPanel.tsx`
- Modify: `perplexity/server/web/src/components/logs/LogsPanel.tsx`

**Step 1: Update `api.ts` — remove auth params and headers**

Remove `verifyAdminToken` function entirely.

Remove `adminToken` parameter from:
- `fetchMonitorConfig(adminToken)` → `fetchMonitorConfig()`
- `updateFallbackConfig(config, adminToken)` → `updateFallbackConfig(config)`
- `apiCall(action, params, adminToken)` → `apiCall(action, params)`
- `updateMonitorConfig(config, adminToken)` → `updateMonitorConfig(config)`
- `fetchLogs(adminToken, lines)` → `fetchLogs(lines)`
- `downloadSingleTokenConfig(clientId, adminToken)` → `downloadSingleTokenConfig(clientId)`
- `importTokenConfig(tokens, adminToken)` → `importTokenConfig(tokens)`

Remove `X-Admin-Token` header from all fetch calls.

**Step 2: Update `usePool.ts`**

Remove `useAuth` import and usage. Simplify `refreshData` — always fetch all three (pool, monitor, fallback):

```typescript
import { useState, useEffect, useCallback } from 'react'
import { fetchPoolStatus, fetchMonitorConfig, fetchFallbackConfig, PoolStatus, MonitorConfig, FallbackConfig } from 'lib/api'

export function usePool() {
  const [data, setData] = useState<PoolStatus>({
    total: 0,
    available: 0,
    mode: '-',
    clients: [],
  })
  const [monitorConfig, setMonitorConfig] = useState<MonitorConfig | null>(null)
  const [fallbackConfig, setFallbackConfig] = useState<FallbackConfig>({ fallback_to_auto: true })
  const [isLoading, setIsLoading] = useState(false)
  const [lastSync, setLastSync] = useState<number | null>(null)

  const refreshData = useCallback(async () => {
    setIsLoading(true)
    try {
      const [poolData, monitorResp, fallbackResp] = await Promise.all([
        fetchPoolStatus(),
        fetchMonitorConfig(),
        fetchFallbackConfig(),
      ])
      setData(poolData)
      setLastSync(Date.now())

      if (monitorResp.status === 'ok' && monitorResp.config) {
        setMonitorConfig(monitorResp.config)
      }
      if (fallbackResp.status === 'ok' && fallbackResp.config) {
        setFallbackConfig(fallbackResp.config)
      }
    } catch (e) {
      console.error('Failed to fetch data:', e)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    refreshData()
    const interval = setInterval(refreshData, 30000)
    return () => clearInterval(interval)
  }, [refreshData])

  return {
    data,
    monitorConfig,
    setMonitorConfig,
    fallbackConfig,
    setFallbackConfig,
    isLoading,
    lastSync,
    refreshData,
  }
}
```

**Step 3: Update `useLogs.ts`**

Remove `adminToken` parameter. Change `useLogs(adminToken)` → `useLogs()`. Remove auth check in `refresh`. Change `fetchLogs(adminToken, 100)` → `fetchLogs(100)`. Remove `adminToken` from all dependency arrays.

**Step 4: Update `App.tsx`**

- Remove `useAuth` import and `AuthBar` import
- Remove `const { adminToken, isAuthenticated, login, logout } = useAuth()`
- Remove `handleLogout` callback
- Remove the AuthBar JSX block (lines 160-172)
- Remove `isAuthenticated` guards on tab navigation (line 175) — always show tabs
- Remove `isAuthenticated` guard on MonitorPanel (line 215) — show whenever monitorConfig exists
- Remove `adminToken` / `isAuthenticated` from all component props
- Update `handleAddToken` — remove `adminToken` from `apiCall`
- Update `handleDeleteToken` — remove `adminToken` from `apiCall`
- Update `handleImportConfig` — remove `adminToken` from `importTokenConfig`
- Update `confirmDelete` — remove `isAuthenticated` check
- Update `LogsPanel` — remove `adminToken` prop

**Step 5: Update `TokenTable.tsx`**

- Remove `adminToken` and `isAuthenticated` from props interface
- Remove all `if (!isAuthenticated)` guards
- Remove `adminToken` from `apiCall`, `updateFallbackConfig`, `downloadSingleTokenConfig` calls
- Remove disabled states based on `isAuthenticated`
- Simplify button classes (remove auth-conditional styling)

**Step 6: Update `MonitorPanel.tsx`**

- Remove `adminToken` and `isAuthenticated` from props interface
- Remove all `if (!isAuthenticated)` guards
- Remove `adminToken` from `updateMonitorConfig`, `apiCall` calls
- Remove disabled states based on `isAuthenticated`

**Step 7: Update `LogsPanel.tsx`**

- Remove `adminToken` from props interface
- Change `useLogs(adminToken)` → `useLogs()`

**Step 8: Delete auth files**

Delete `perplexity/server/web/src/hooks/useAuth.ts` and `perplexity/server/web/src/components/AuthBar.tsx`.

**Step 9: Build frontend to verify no errors**

Run: `cd perplexity/server/web && npm run build`
Expected: Build succeeds with no TypeScript errors

**Step 10: Commit**

```bash
git add -A perplexity/server/web/src/
git commit -m "feat: remove auth from admin frontend"
```

---

### Task 6: Final verification

**Step 1: Run full backend test suite**

Run: `.venv/bin/python -m pytest tests/test_client_pool.py tests/test_config.py tests/test_utils.py -v`
Expected: All tests PASS (including 7 new decrement_quota tests)

**Step 2: Build frontend**

Run: `cd perplexity/server/web && npm run build`
Expected: Build succeeds

**Step 3: Final commit (if any remaining changes)**

```bash
git add -A
git commit -m "chore: final cleanup after auth removal and smart quotas"
```

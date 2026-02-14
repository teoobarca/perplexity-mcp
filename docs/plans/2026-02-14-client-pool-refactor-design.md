# Client Pool Refactor: Remove State Redundancy

**Date**: 2026-02-14
**Status**: Approved

## Problem

The client pool has accumulated redundant state management:

1. **`state` field** ("normal", "downgrade", "offline", "unknown") is a lossy cache of `rate_limits` data, manually set in 6 places with 3 different logic paths that produce inconsistent results for edge cases
2. **`pro_fail_count`** is tracked but never affects any decision — dead metric
3. **Client selection** is split: `get_client()` filters by backoff, then `run_query()` filters again by state, then again by rate_limits for research
4. **State determination** duplicated in `_verify_client_quota()`, `test_client()`, `refresh_all_rate_limits()` with subtle inconsistencies
5. **Config save** uses two patterns: `_save_config()` for tokens, inline JSON for monitor/fallback
6. **New tokens** start as "unknown"/"Ready" and aren't tested until next monitor cycle

## Design

### Core Model Change

**Replace** `state: str` with:
- `session_valid: Optional[bool]` — `None` (unchecked), `True` (valid session), `False` (invalid)
- `rate_limits: dict` — unchanged, single source of truth for quotas

**`state`** becomes a read-only computed property for API/frontend:
```python
@property
def state(self) -> str:
    if self.session_valid is False:
        return "offline"
    if self.session_valid is None:
        return "unknown"
    if self.rate_limits.get("pro_remaining", 1) > 0:
        return "normal"
    return "exhausted"
```

Three states for display: **online** (normal), **offline**, **unknown**. Quotas shown separately from rate_limits.

### Unified Client Selection

**`get_client(mode)`** replaces `get_client()` — filters in one place:

```python
def get_client(self, mode: str = "auto") -> Tuple[Optional[str], Optional[Client]]:
    # Round-robin among: enabled + not in backoff + has_quota(mode)
```

New helper on ClientWrapper:
```python
def has_quota(self, mode: str) -> bool:
    if self.session_valid is False:
        return False
    if mode in ("pro", "reasoning"):
        pro_rem = self.rate_limits.get("pro_remaining")
        return pro_rem is None or pro_rem > 0  # None = unknown, assume yes
    if mode == "deep research":
        research = self.rate_limits.get("modes", {}).get("research", {})
        rem = research.get("remaining")
        return rem is None or rem > 0
    return True  # auto mode always ok
```

### run_query() Simplification

Current flow (6 concerns mixed together):
1. Validate query
2. Round-robin via get_client()
3. Check state to skip downgraded
4. Check rate_limits for research
5. Execute search
6. Complex fallback with skipped_downgraded_clients list

New flow:
1. Validate query
2. `get_client(mode)` — returns client with quota (one call, one filter)
3. Execute search
4. On failure → next client via loop
5. Fallback: `get_client("auto")` when all pro clients exhausted

`skipped_downgraded_clients` list and `get_client_state()` go away entirely.

### Remove Dead Code

- `pro_fail_count`, `mark_pro_failure()`, `mark_client_pro_failure()` — removed
- `get_client_state()` — removed (use `state` property via `get_status()`)
- Manual `wrapper.state = "..."` assignments in 6 locations — removed
- `_determine_state()` helper — not needed, state is a property

### Auto-Test on Add

`add_client()` in admin.py triggers `pool.test_client(client_id)` after adding, so new tokens immediately get `session_valid` + `rate_limits` instead of sitting in "unknown".

### Unified Config Save

`update_monitor_config()` and `update_fallback_config()` use `_save_config()` instead of inline JSON read/write. `_save_config()` writes the full config (tokens + monitor + fallback).

### State Determination — Single Path

`test_client()` and `refresh_all_rate_limits()` both set:
- `wrapper.session_valid = True/False`
- `wrapper.rate_limits = <API result>`
- `wrapper.last_check = time.time()`

No state derivation needed — `state` property handles it.

### pool_state.json Backward Compatibility

Write: includes `session_valid` + `rate_limits` + computed `state` (for older readers).

Read (`load_state()`): if `session_valid` is present, use it. If only `state` is present (old format), derive:
- `"offline"` → `session_valid = False`
- `"unknown"` → `session_valid = None`
- `"normal"` / `"downgrade"` → `session_valid = True`

### Frontend Changes

- Badge: online (green) / offline (red) / unknown (gray) — derived from `state` in API response
- Quota column: unchanged, reads `rate_limits` directly
- "Downgrade" filter pill → removed or renamed to "Exhausted"
- `pro_fail_count` removed from error count display
- Filter pills: All / Online / Exhausted / Offline / Unknown

## Files Changed

| File | Changes |
|------|---------|
| `perplexity/server/client_pool.py` | Core: session_valid, state property, has_quota(), get_client(mode), remove pro_fail_count, unified config save |
| `perplexity/server/app.py` | run_query() simplification, get_pool() unchanged |
| `perplexity/server/admin.py` | Auto-test on add_client |
| `src/server.py` | Remove lazy state check (pool handles it), simplify call_tool |
| `perplexity/server/web/src/components/TokenTable.tsx` | Badge/filter changes |
| `tests/test_client_pool.py` | Update tests for new API |

## Verification

1. Unit tests: `test_client_pool.py`, `test_config.py`, `test_utils.py`
2. Import chain: `from perplexity.server.app import run_query`
3. Frontend build: `cd perplexity/server/web && npm run build`

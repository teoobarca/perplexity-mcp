# Perplexity MCP Server

## Environment

- **Virtual environment**: `.venv/` — always use `.venv/bin/python` to run scripts
- Install with `uv pip install -e .` (no pip in venv, use uv)

## Setup

```bash
uv pip install -e . --python .venv/bin/python
```

## Project Structure

Monorepo — everything in one place:

```
src/                     # MCP stdio server (thin wrapper)
  server.py              # MCP server entry point, pool state sync, timeout handling
  tools.py               # MCP tool definitions (perplexity_ask, perplexity_research)

perplexity/              # Backend engine
  client.py              # Perplexity API client (curl_cffi, bypasses Cloudflare)
  config.py              # All constants, endpoints, model mappings
  exceptions.py          # Custom exception hierarchy
  logger.py              # Centralized logging
  server/
    app.py               # Starlette app, run_query() with pool rotation + fallback
    client_pool.py        # ClientPool, ClientWrapper, monitor, state persistence
    admin.py              # Admin REST API routes (plain Starlette) + static file serving
    utils.py              # Validation helpers
    main.py               # HTTP server entry point (uvicorn, port 8123)
    web/                  # React admin frontend (Vite + Tailwind)
      src/                # Frontend source
      dist/               # Built frontend (gitignored)

tests/                   # Test suite
```

## Configuration

- **Token config**: `token_pool_config.json` (gitignored) — tokens, monitor, fallback settings
- **Environment**: `.env` — `PERPLEXITY_TIMEOUT` (default 900s), `PPLX_ADMIN_TOKEN`
- The server auto-discovers `token_pool_config.json` in the working directory

### token_pool_config.json schema

```json
{
  "monitor": {
    "enable": false,
    "interval": 6,
    "tg_bot_token": null,
    "tg_chat_id": null
  },
  "fallback": { "fallback_to_auto": true },
  "tokens": [
    { "id": "main", "csrf_token": "...", "session_token": "..." }
  ]
}
```

## Architecture

- `src/server.py` — MCP stdio server, delegates to `perplexity.server.app.run_query()`
- `src/tools.py` — 2 MCP tool definitions with LLM-optimized descriptions
- Backend handles: ClientPool, round-robin rotation, exponential backoff, 3-level fallback
- Rate limits fetched via `/rest/rate-limit` API (no test queries consumed)
- Client selection: `get_client(mode)` — round-robin among clients with quota for the requested mode
- `perplexity.server.main` — HTTP server with admin UI (plain Starlette + uvicorn, port 8123)

## Two Entry Points

1. **`perplexity-mcp`** — MCP stdio server (for Claude Code, Cursor, etc.)
2. **`perplexity-server`** — HTTP server with admin panel at `http://localhost:8123/admin/` (auto-opens browser)

## Monitor System (ex-heartbeat)

Zero-cost health checks via Perplexity rate-limit API — no queries consumed.

- Periodic background task checks all clients at configurable interval
- Sets `session_valid` + fetches `rate_limits` for each client
- Telegram notifications on state changes
- State shared via `pool_state.json` for cross-process coordination
- `state` is a computed property derived from `session_valid` + `rate_limits`

## Token States

State is computed (never set manually):

| State | Meaning | Behavior |
|-------|---------|----------|
| `normal` | Session valid, pro quota available | Used for all requests |
| `exhausted` | Session valid, pro quota = 0 | Skipped for pro, used as auto fallback |
| `offline` | Session invalid/expired | Not used |
| `unknown` | Not yet checked | Used normally (assumes quota available) |

## Admin REST API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | No | Health check |
| `/pool/status` | GET | No | Pool status with rate limits |
| `/pool/{action}` | POST | Yes* | Pool management (add/remove/enable/disable/reset) |
| `/pool/export` | GET | Yes | Export all tokens |
| `/pool/import` | POST | Yes | Import tokens |
| `/monitor/config` | GET/POST | Yes | Get/update monitor config |
| `/monitor/start` | POST | Yes | Start monitor |
| `/monitor/stop` | POST | Yes | Stop monitor |
| `/monitor/test` | POST | Yes | Trigger health check |
| `/fallback/config` | GET/POST | Yes* | Get/update fallback config |
| `/logs/tail` | GET | Yes | Tail log file |

## Frontend Development

```bash
cd perplexity/server/web
npm install
npm run dev          # Dev server with proxy to :8123
npm run build        # Production build to dist/
```

Vite proxy paths: /pool, /monitor, /health, /logs, /fallback

## Tests

```bash
# Unit tests (no server required)
.venv/bin/python -m pytest tests/test_config.py tests/test_utils.py tests/test_client_pool.py tests/test_research_downgrade.py -v
```

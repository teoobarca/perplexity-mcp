# AGENTS.md — Codex CLI Configuration

> Mirrors CLAUDE.md for OpenAI Codex CLI compatibility.
> Codex reads `AGENTS.md` where Claude Code reads `CLAUDE.md`.

## Parity Rules

- This file is **additive only** — never delete content from CLAUDE.md when mirroring
- Skill invocation patterns are compatible across both runtimes
- Runtime mapping: `CLAUDE.md` ↔ `AGENTS.md`, `.claude/` ↔ `.agents/`

## Project Context

| Aspect | Value |
|--------|-------|
| **Repo** | `geremyturcotte/perplexity-mcp` |
| **Type** | MCP server (stdio + HTTP) |
| **Stack** | Python 3.10+, Starlette, curl_cffi, MCP SDK |
| **Version** | 0.7.0 |
| **Owner** | Geremy Turcotte |

## Active MCPs

| MCP | Available | Notes |
|-----|-----------|-------|
| Linear | No | Not configured locally |
| Perplexity | No | This IS the Perplexity server |
| Redis | No | Not applicable |
| Stripe | No | Not applicable |

## Key Commands

```bash
# Setup
uv pip install -e . --python .venv/bin/python

# Tests
.venv/bin/python -m pytest tests/ -v

# Run MCP server (stdio)
.venv/bin/python -m src.server

# Run HTTP server (admin UI)
.venv/bin/python -m perplexity.server.main

# Frontend dev
cd perplexity/server/web && npm run dev
```

## Project Structure

```
src/server.py          # MCP stdio entry point
src/tools.py           # Tool definitions (ask, research, council)
perplexity/client.py   # API client (curl_cffi, Cloudflare bypass)
perplexity/config.py   # Constants, model mappings, endpoints
perplexity/server/     # HTTP server (Starlette + uvicorn)
  app.py               # run_query() with pool rotation + fallback
  client_pool.py       # ClientPool, ClientWrapper, quota management
  admin.py             # Admin REST API routes
  utils.py             # Validation helpers
tests/                 # pytest suite
```

## Guardrails

- **NEVER** commit `.env`, `accounts.json`, `token_pool_config.json`, `pool_state.json`
- **NEVER** expose session tokens or CSRF tokens in code or logs
- **ALWAYS** use `.venv/bin/python` — system Python may lack dependencies
- **ALWAYS** run tests before committing: `.venv/bin/python -m pytest tests/ -v`
- **ALWAYS** validate JSON files after editing: `python3 -m json.tool <file>`

## ProKai Integration

- **Plugin**: `prokai-core` enabled (`.claude/settings.json`)
- **Config**: `.prokai.config.json` (stack: python, ticket: PRO-)
- **Methodology**: auto (TDD default)
- Changes here affect all repos with `prokai-core` enabled (perplexity MCP server)

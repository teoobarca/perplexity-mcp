<p align="center">
  <img src="https://img.shields.io/badge/Perplexity-MCP_Server-1a1a2e?style=for-the-badge&labelColor=09090b" alt="Perplexity MCP Server" />
</p>

<p align="center">
  <strong>Free Perplexity AI for your coding assistant. No API keys needed.</strong>
</p>

<p align="center">
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-14b8a6?style=flat-square" alt="MIT License" /></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.10+-3b82f6?style=flat-square" alt="Python 3.10+" /></a>
  <a href="https://modelcontextprotocol.io/"><img src="https://img.shields.io/badge/MCP-Compatible-22c55e?style=flat-square" alt="MCP Compatible" /></a>
</p>

---

## What is this?

An MCP server that gives your AI coding assistant access to [Perplexity](https://perplexity.ai) — an AI research engine that synthesizes answers from multiple sources with citations.

**What you get vs. built-in web search:**

| | Built-in search | Perplexity MCP |
|:---|:---|:---|
| **Quick questions** | 10 blue links | Synthesized answer with sources |
| **Technical docs** | Outdated snippets | Current, contextual explanations |
| **Deep research** | Manual reading | 10-30+ citation reports |
| **Reasoning** | N/A | Multi-model reasoning (GPT, Claude, Grok) |

Includes a **token pool admin panel** for managing multiple sessions, monitoring quotas, and auto-fallback — useful if you run this for a team or want zero-downtime rotation.

---

## Tools

| Tool | Mode | Best for |
|:-----|:-----|:---------|
| `perplexity_ask` | Pro search | Technical questions, docs, how-to guides |
| `perplexity_ask` | Reasoning* | Comparisons, trade-offs, decisions |
| `perplexity_research` | Deep research | Architecture analysis, thorough investigations (10-30+ citations) |

\* *Reasoning mode is auto-detected when using a model with "thinking" or "reasoning" in the name.*

---

## Quick Start

```bash
git clone https://github.com/teoobarca/perplexity-mcp.git
cd perplexity-mcp
uv sync
```

Then add to your AI tool:

<details>
<summary><b>Claude Code</b></summary>

```bash
claude mcp add perplexity -s user -- uv --directory /path/to/perplexity-mcp run perplexity-mcp
```
</details>

<details>
<summary><b>Cursor</b></summary>

Settings → MCP → Add new server:
```json
{
  "command": "uv",
  "args": ["--directory", "/path/to/perplexity-mcp", "run", "perplexity-mcp"]
}
```
</details>

<details>
<summary><b>Windsurf / VS Code / Other MCP clients</b></summary>

```json
{
  "mcpServers": {
    "perplexity": {
      "command": "uv",
      "args": ["--directory", "/path/to/perplexity-mcp", "run", "perplexity-mcp"]
    }
  }
}
```
</details>

**Done.** Works out of the box with anonymous sessions (rate limited). Add your tokens for unlimited access — see [Authentication](#authentication) below.

---

## Admin Panel

A built-in web dashboard for managing token pools, monitoring quotas, and viewing logs.

```bash
perplexity-server
```

Opens automatically at `http://localhost:8123/admin/`.

**Features:**
- Real-time token pool status with usage quotas (Pro, Research, Agentic)
- Health monitoring with zero-cost rate-limit API checks
- Token management — add, remove, enable/disable, import/export
- Auto-fallback from Pro → free model when quota exhausted
- Telegram notifications on state changes
- Log viewer with level filtering and search

<!-- Screenshot placeholder — replace with actual screenshot -->
<!-- ![Admin Panel](docs/admin-panel.png) -->

---

## Authentication

By default, the server uses anonymous Perplexity sessions. For unlimited queries, add your Perplexity Pro session tokens.

### Single token (MCP server)

```bash
cp token_pool_config.example.json token_pool_config.json
# Edit and add your tokens
```

### How to get tokens

1. Sign in at [perplexity.ai](https://perplexity.ai)
2. Open DevTools (F12) → Application tab → Cookies
3. Copy `next-auth.session-token` and `next-auth.csrf-token`
4. Add them to `token_pool_config.json`:

```json
{
  "tokens": [
    {
      "id": "main",
      "csrf_token": "your-csrf-token",
      "session_token": "your-session-token"
    }
  ]
}
```

### Multiple tokens (pool)

Add multiple tokens for round-robin rotation with automatic failover:

```json
{
  "monitor": {
    "enable": true,
    "interval": 6
  },
  "fallback": { "fallback_to_auto": true },
  "tokens": [
    { "id": "account-1", "csrf_token": "...", "session_token": "..." },
    { "id": "account-2", "csrf_token": "...", "session_token": "..." }
  ]
}
```

---

## Configuration

| Variable | Default | Description |
|:---------|:--------|:------------|
| `PERPLEXITY_TIMEOUT` | `900` | Request timeout in seconds (15 min for deep research) |
| `PERPLEXITY_MAX_RETRIES` | `2` | Retry attempts on transient failures |
| `PPLX_ADMIN_TOKEN` | — | Admin token for the web dashboard |

---

## How It Works

```
Your AI Assistant ──MCP──▸ perplexity-mcp ──▸ Perplexity ──▸ Answer + Citations
                                │
                          Client Pool (round-robin, backoff, fallback)
                                │
                          perplexity-server ──▸ Admin Panel :8123/admin/
```

- **MCP server** (`perplexity-mcp`) — stdio transport, connects to Claude Code / Cursor / etc.
- **Client pool** — round-robin rotation, exponential backoff on failures, automatic Pro → free fallback
- **Monitor** — periodic health checks via rate-limit API (zero queries consumed), detects token states
- **Admin server** (`perplexity-server`) — Starlette + React dashboard on port 8123

---

## Limitations

- **Unofficial** — uses Perplexity's web interface, may break if they change it
- **Rate limits** — anonymous sessions have query limits
- **Cookie expiry** — session tokens last ~30 days

---

## License

MIT

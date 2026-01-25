# Perplexity MCP Server

**Free Perplexity AI for your coding assistant. No API keys, no account needed.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)

---

## Why Perplexity?

Most AI coding assistants have some form of web search, but it's basic — you get links and snippets, not answers.

[Perplexity](https://perplexity.ai) is an AI research assistant that actually synthesizes information:

- Combines multiple sources into coherent answers
- Cites everything so you can verify
- Has specialized modes for reasoning and deep research (10-30+ citations)

This MCP server connects your assistant to Perplexity's web interface — no API keys, no subscription, no cost.

---

## What You Get

Four specialized tools, each optimized for different tasks:

| Tool | Use case | Example |
|:-----|:---------|:--------|
| `perplexity_search` | Quick facts | "Latest stable version of Node.js?" |
| `perplexity_ask` | Technical questions | "How to set up OAuth in Next.js 15 App Router?" |
| `perplexity_reason` | Decisions & trade-offs | "Prisma vs Drizzle for serverless Postgres?" |
| `perplexity_research` | Deep analysis (10-30+ citations) | "Best practices for LLM API key rotation in production" |

**vs. built-in search:** Your assistant asks "What's new in React 19?" — built-in search returns 10 blue links. Perplexity returns a synthesized answer with specific breaking changes, migration steps, and citations.

---

## Installation

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
<summary><b>Windsurf</b></summary>

Add to your MCP config:
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

<details>
<summary><b>VS Code + Copilot</b></summary>

Add to `.vscode/mcp.json`:
```json
{
  "servers": {
    "perplexity": {
      "command": "uv",
      "args": ["--directory", "/path/to/perplexity-mcp", "run", "perplexity-mcp"]
    }
  }
}
```
</details>

<details>
<summary><b>Other MCP clients</b></summary>

```json
{
  "mcpServers": {
    "perplexity": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "/path/to/perplexity-mcp", "run", "perplexity-mcp"]
    }
  }
}
```
</details>

**Done.** Free Perplexity access, no API keys, no account required.

---

## How It Works

This server uses [helallao/perplexity-ai](https://github.com/helallao/perplexity-ai) to connect to Perplexity's web interface — the same way you'd use perplexity.ai in your browser, but automated.

```
Your AI Assistant → MCP Server → Perplexity → Synthesized answer with citations
```

---

## Optional: Authenticate for Unlimited Access

By default, the server uses anonymous sessions (rate limited). If you have Perplexity Pro, authenticate for unlimited queries:

```bash
cp .env.example .env
# Add your session cookies
```

<details>
<summary><b>How to get cookies</b></summary>

1. Sign in at [perplexity.ai](https://perplexity.ai)
2. Open DevTools (F12) → Network tab
3. Refresh the page
4. Right-click the first request → Copy as cURL
5. Paste at [curlconverter.com/python](https://curlconverter.com/python)
6. Copy `next-auth.session-token` and `next-auth.csrf-token` to `.env`

</details>

---

## Configuration

| Variable | Default | Description |
|:---------|:--------|:------------|
| `PERPLEXITY_TIMEOUT` | 900 | Request timeout in seconds (15 min default for deep research) |
| `PERPLEXITY_MAX_RETRIES` | 2 | Retry attempts on transient failures |

---

## Limitations

- **Unofficial** — Uses Perplexity's web interface, may break if they change it
- **Rate limits** — Anonymous sessions have query limits
- **Cookie expiry** — Authenticated sessions last ~30 days

---

## License

MIT

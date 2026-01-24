# 🔍 Perplexity MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)

> Unofficial MCP server for Perplexity AI. Works out of the box — no API keys, no configuration required.

---

## 🚀 Installation

```bash
git clone https://github.com/teoobarca/perplexity-mcp.git
cd perplexity-mcp
uv sync
```

### Claude Code

```bash
claude mcp add perplexity -s user -- uv --directory /path/to/perplexity-mcp run perplexity-mcp
```

### Cursor

Settings → MCP → Add new server:
```json
{
  "command": "uv",
  "args": ["--directory", "/path/to/perplexity-mcp", "run", "perplexity-mcp"]
}
```

### VS Code

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

### Other clients

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

**That's it!** No cookies, no API keys needed. It just works.

---

## 🛠️ Available Tools

Perplexity is an AI model, not a search engine — provide context and specific requirements for better results.

| Tool | Best For |
|:-----|:---------|
| `perplexity_search` | Quick facts, simple questions |
| `perplexity_ask` | Tech questions, documentation, how-to guides |
| `perplexity_reason` | Comparisons, trade-offs, decisions |
| `perplexity_research` | Deep analysis, architecture decisions (10-30+ citations) |

**Parameters:**
- `query` *(required)* — Natural language question with context
- `language` *(optional)* — ISO 639 code, default: `en-US`
- `sources` *(optional)* — Array: `web`, `scholar`, `social`

---

## 💬 Usage Examples

```
perplexity_search: "What is the latest stable version of React?"
```

```
perplexity_ask: "How to implement JWT auth in Next.js 14 App Router
with httpOnly cookies for a SaaS app?"
```

```
perplexity_reason: "Should I use Prisma or Drizzle for a new Next.js project?
Need type-safety, good DX, and must work with Planetscale MySQL."
```

```
perplexity_research: "Best practices for LLM API key rotation in production
Node.js apps - need patterns for zero-downtime rotation, secret storage
options, and monitoring."
```

---

## 🔧 How It Works

This server wraps [helallao/perplexity-ai](https://github.com/helallao/perplexity-ai), which reverse-engineers Perplexity's web interface.

```
Query → MCP Server → perplexity-api → Perplexity SSE API
                          ↓
               Chrome impersonation via curl_cffi
               Anonymous session creation
               SSE response streaming
```

---

## 🔐 Optional: Use Your Own Account

For unlimited queries with Perplexity Pro, provide your session cookies:

```bash
cp .env.example .env
# Edit .env with your cookies
```

| Mode | Setup | Access |
|:-----|:------|:-------|
| **Anonymous** *(default)* | Nothing needed | Basic queries, Pro limited |
| **Authenticated** | Session cookies | Full subscription access |

<details>
<summary><b>How to get cookies</b></summary>

1. Open [perplexity.ai](https://perplexity.ai) and sign in
2. Open DevTools (`F12`) → Network tab
3. Refresh the page
4. Right-click first request → Copy → Copy as cURL
5. Go to [curlconverter.com/python](https://curlconverter.com/python)
6. Extract `next-auth.session-token` and `next-auth.csrf-token`

</details>

---

## ⚠️ Limitations

- **Unofficial** — May break if Perplexity changes their API
- **Rate limits** — Standard Perplexity limits apply
- **Cookie expiry** — ~30 days if using own account

---

## 📄 License

MIT

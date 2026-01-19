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

| Tool | Mode | Description |
|:-----|:-----|:------------|
| `perplexity_search` | auto | Quick basic search for simple queries |
| `perplexity_ask` | pro | Pro mode with citations and detailed answers |
| `perplexity_reason` | reasoning | Step-by-step analytical reasoning |
| `perplexity_research` | deep research | Exhaustive research with 50+ citations |

**Parameters:**
- `query` *(required)* — Your search query
- `language` *(optional)* — ISO 639 code, default: `en-US`
- `sources` *(optional)* — Array: `web`, `scholar`, `social`

---

## 💬 Usage Examples

> Use `perplexity_search` to find the current price of Bitcoin.

> Use `perplexity_ask` to explain how mRNA vaccines work.

> Use `perplexity_reason` to analyze pros and cons of remote work.

> Use `perplexity_research` to find latest research on intermittent fasting.

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

# Perplexity MCP Server

Unofficial MCP server for Perplexity AI. Works out of the box - no API keys, no configuration required.

## Quick Start

```bash
git clone https://github.com/teoobarca/perplexity-mcp.git
cd perplexity-mcp
uv sync

# Add to Claude Code
claude mcp add perplexity -s user -- uv --directory /path/to/perplexity-mcp run perplexity-mcp
```

**That's it!** No cookies, no API keys needed. It just works.

## How It Works

This MCP server wraps the unofficial [helallao/perplexity-ai](https://github.com/helallao/perplexity-ai) library, which reverse-engineers Perplexity's web interface.

### No Configuration Required

The library automatically creates anonymous sessions with Perplexity. When you make a query:

1. Library impersonates a Chrome browser using `curl_cffi`
2. Creates a session with Perplexity's servers
3. Sends your query to the internal SSE endpoint (`/rest/sse/perplexity_ask`)
4. Streams back the response with citations

### Optional: Use Your Own Account

If you want unlimited queries with your Perplexity Pro subscription, you can optionally provide your session cookies:

```bash
cp .env.example .env
# Edit .env with your cookies
```

| Cookie | Purpose |
|--------|---------|
| `next-auth.session-token` | Your authenticated session (JWT token) |
| `next-auth.csrf-token` | CSRF protection (optional) |

**How to get cookies:**
1. Open [perplexity.ai](https://perplexity.ai) and sign in
2. Open DevTools (`F12`) → Network tab
3. Refresh the page
4. Right-click first request → Copy → Copy as cURL (bash)
5. Go to [curlconverter.com/python](https://curlconverter.com/python)
6. Paste cURL and extract cookie values

### Anonymous vs Authenticated

| Mode | Setup | Limits |
|------|-------|--------|
| **Anonymous** (default) | None! Just install and use | Basic queries work, Pro features limited |
| **With cookies** | Provide session cookies | Full access based on your subscription |

## Available Tools

| Tool | Mode | Description |
|------|------|-------------|
| `perplexity_search` | auto | Quick basic search for simple queries |
| `perplexity_ask` | pro | Pro mode with citations and detailed answers |
| `perplexity_reason` | reasoning | Step-by-step analytical reasoning |
| `perplexity_research` | deep research | Exhaustive research with 50+ citations |

### Tool Parameters

All tools accept:
- `query` (required) - Your search query
- `language` (optional) - ISO 639 language code, default: `en-US`
- `sources` (optional) - Array of `web`, `scholar`, `social`, default: `["web"]`

## Usage Examples

```
Use perplexity_search to find the current price of Bitcoin.
```

```
Use perplexity_ask to explain how mRNA vaccines work.
```

```
Use perplexity_reason to analyze pros and cons of remote work.
```

```
Use perplexity_research to find latest research on intermittent fasting.
```

## Manual Configuration

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "perplexity": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/perplexity-mcp",
        "run",
        "perplexity-mcp"
      ]
    }
  }
}
```

## Verification

```bash
# List installed MCP servers
claude mcp list

# Or inside Claude Code
/mcp
```

## Technical Details

### Under the Hood

The underlying `perplexity-api` library:
- Uses `curl_cffi` to impersonate Chrome browser with realistic headers
- Sends requests to Perplexity's internal REST/SSE endpoints
- Parses Server-Sent Events response stream
- Extracts answers, citations, and metadata

### Limitations

- **Unofficial** - May break if Perplexity changes their internal API
- **Rate limits** - Perplexity's standard rate limits apply
- **Cookie expiry** - If using own account, cookies expire after ~30 days

## Dependencies

- `perplexity-api` - Unofficial Perplexity wrapper ([helallao/perplexity-ai](https://github.com/helallao/perplexity-ai))
- `mcp` - Anthropic MCP SDK
- `python-dotenv` - Environment variable loading

## License

MIT

## Disclaimer

This is an unofficial wrapper using reverse-engineered endpoints. Use responsibly and respect Perplexity's Terms of Service.

# Perplexity MCP Server

Unofficial MCP server for Perplexity AI using cookie-based authentication. Access Perplexity Pro features without API costs.

## Quick Install (Claude Code)

```bash
# Clone and setup
git clone https://github.com/teoobarca/perplexity-mcp.git
cd perplexity-mcp
uv sync
cp .env.example .env
# Edit .env with your cookies (see "Getting Cookies" below)

# Add to Claude Code globally
claude mcp add perplexity -s user -- uv --directory /path/to/perplexity-mcp run perplexity-mcp
```

Or add manually to `~/.claude.json`:

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

## Getting Cookies

This server uses cookie-based auth to access Perplexity Pro features.

1. Open [perplexity.ai](https://perplexity.ai) and sign in
2. Open DevTools (`F12`) → Network tab
3. Refresh the page
4. Right-click first request → Copy → Copy as cURL (bash)
5. Go to [curlconverter.com/python](https://curlconverter.com/python)
6. Paste cURL and extract cookie values

### Configure cookies

Edit `.env` file:

```env
PERPLEXITY_CSRF_TOKEN=your_csrf_token_here
PERPLEXITY_SESSION_TOKEN=your_session_token_here
```

## Usage Examples

In Claude Code:

```
Use perplexity_research to find latest research on intermittent fasting benefits.
```

```
Use perplexity_ask to quickly check magnesium glycinate dosage for sleep.
```

```
Use perplexity_reason to analyze whether creatine or beta-alanine is better for climbing performance.
```

## Verification

After setup, verify the server is working:

```bash
# List installed MCP servers
claude mcp list

# Or inside Claude Code
/mcp
```

Test the tools:
```bash
echo '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}' | uv run perplexity-mcp
```

## Troubleshooting

### "Missing cookies" error
Cookies not configured. Check your `.env` file has both tokens set.

### "Expired cookies" error
Cookies have expired. Repeat the cookie extraction steps above.

### Server won't start
```bash
# Debug mode
uv run python -c "from src.perplexity_client import PerplexityClient; c = PerplexityClient(); print('OK')"
```

### Remove and re-add
```bash
claude mcp remove perplexity
claude mcp add perplexity -s user -- uv --directory /path/to/perplexity-mcp run perplexity-mcp
```

## Dependencies

- `perplexity-api` - Unofficial Perplexity wrapper ([helallao/perplexity-ai](https://github.com/helallao/perplexity-ai))
- `mcp` - Anthropic MCP SDK
- `python-dotenv` - Environment variable loading

## License

MIT

## Disclaimer

This is an unofficial wrapper using cookie-based authentication. Use responsibly and respect Perplexity's Terms of Service. Cookies may expire and require periodic refresh.

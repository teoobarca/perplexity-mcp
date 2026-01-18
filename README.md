# Perplexity MCP Server

Unofficial MCP server pre Perplexity AI používajúci cookie-based authentication.
Poskytuje Perplexity Pro features bez API poplatkov.

## Features

- **perplexity_ask** - Pro mode search s citáciami
- **perplexity_research** - Deep research mode pre exhaustívnu analýzu
- **perplexity_reason** - Reasoning mode pre step-by-step analýzu
- **perplexity_search** - Basic auto mode pre quick queries

## Setup

### 1. Inštalácia dependencies

```bash
cd tools/perplexity-mcp
uv sync
```

### 2. Získanie cookies

1. Otvor [perplexity.ai](https://perplexity.ai) a prihlás sa
2. Otvor DevTools (F12) → Network tab
3. Refresh stránku
4. Pravý klik na prvý request → Copy → Copy as cURL (bash)
5. Choď na [curlconverter.com/python](https://curlconverter.com/python)
6. Vlož cURL a skopíruj cookies

### 3. Konfigurácia cookies

Vytvor `.env` súbor (skopíruj z `.env.example`):

```bash
cp .env.example .env
```

Vyplň cookies:

```env
PERPLEXITY_CSRF_TOKEN=abc123...
PERPLEXITY_SESSION_TOKEN=xyz789...
```

### 4. Pridanie do Claude Code

Edituj `~/.claude.json`:

```json
{
  "mcpServers": {
    "perplexity": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/hamper/Documents/Programming/Biohacking/tools/perplexity-mcp",
        "run",
        "perplexity-mcp"
      ]
    }
  }
}
```

### 5. Reštart Claude Code

```bash
# Zavri a znova otvor Claude Code
claude
```

## Usage

V Claude Code:

```
Použi perplexity_research a zisti najnovšie informácie o LPR liečbe.
```

## Available Tools

| Tool | Mode | Popis |
|------|------|-------|
| `perplexity_ask` | pro | Pro search s citáciami |
| `perplexity_research` | deep research | Exhaustívny research |
| `perplexity_reason` | reasoning | Step-by-step reasoning |
| `perplexity_search` | auto | Quick basic search |

## Troubleshooting

### "Missing cookies" error

Cookies nie sú nastavené. Skontroluj `.env` súbor.

### "Expired cookies" error

Cookies expirovali. Opakuj kroky na získanie nových cookies.

### Server sa nespustí

```bash
# Debug mode
cd tools/perplexity-mcp
uv run python -c "from src.perplexity_client import PerplexityClient; c = PerplexityClient(); print('OK')"
```

### Test MCP protocol

```bash
echo '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}' | uv run perplexity-mcp
```

## Dependencies

- `perplexity-api` - Unofficial Perplexity wrapper (helallao/perplexity-ai)
- `mcp` - Anthropic MCP SDK
- `python-dotenv` - Environment variable loading

## Disclaimer

Toto je unofficial wrapper. Použi zodpovedne a rešpektuj Perplexity ToS.

"""
MCP Server for Perplexity AI.

Provides unofficial Perplexity access through MCP tools using cookie-based
authentication. Requires valid Perplexity session cookies.
"""

import asyncio
import json
import logging
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent

from .perplexity_client import PerplexityClient, CookieError, PerplexityClientError
from .tools import TOOLS, TOOL_METHOD_MAP

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("perplexity-mcp")

# Create server instance
server = Server("perplexity-mcp")

# Global client instance (initialized on first use)
_client: PerplexityClient | None = None


def get_client() -> PerplexityClient:
    """Get or create the Perplexity client."""
    global _client
    if _client is None:
        _client = PerplexityClient()
    return _client


@server.list_tools()
async def list_tools():
    """List available Perplexity tools."""
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """
    Handle tool calls.

    Args:
        name: Tool name (perplexity_ask, perplexity_research, etc.)
        arguments: Tool arguments (query, sources, language)

    Returns:
        List with single TextContent containing the response
    """
    logger.info(f"Tool call: {name} with args: {arguments}")

    if name not in TOOL_METHOD_MAP:
        return [TextContent(
            type="text",
            text=f"Unknown tool: {name}. Available: {list(TOOL_METHOD_MAP.keys())}"
        )]

    try:
        client = get_client()
        method_name = TOOL_METHOD_MAP[name]
        method = getattr(client, method_name)

        # Extract arguments
        query = arguments.get("query", "")
        sources = arguments.get("sources")
        language = arguments.get("language", "en-US")

        # Run synchronous client in thread pool to not block async
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: method(query=query, sources=sources, language=language)
        )

        # Format response
        result = format_response(response)
        logger.info(f"Tool {name} completed successfully")
        return [TextContent(type="text", text=result)]

    except CookieError as e:
        error_msg = f"Cookie error: {e}\n\nTo fix:\n1. Login to perplexity.ai\n2. Open DevTools (F12) → Network tab\n3. Refresh page\n4. Right-click first request → Copy as cURL\n5. Paste at curlconverter.com/python\n6. Copy cookies to .env file"
        logger.error(error_msg)
        return [TextContent(type="text", text=error_msg)]

    except PerplexityClientError as e:
        error_msg = f"Perplexity client error: {e}"
        logger.error(error_msg)
        return [TextContent(type="text", text=error_msg)]

    except Exception as e:
        error_msg = f"Unexpected error: {type(e).__name__}: {e}"
        logger.exception(error_msg)
        return [TextContent(type="text", text=error_msg)]


def format_response(response: dict) -> str:
    """Format Perplexity response for MCP output."""
    parts = []

    # Main answer
    if answer := response.get("answer"):
        parts.append(answer)

    # Citations
    if citations := response.get("citations"):
        if citations:
            parts.append("\n\n## Sources")
            for i, citation in enumerate(citations[:10], 1):  # Limit to 10
                if isinstance(citation, dict):
                    url = citation.get("url", "")
                    title = citation.get("title", url)
                    parts.append(f"{i}. [{title}]({url})")
                else:
                    parts.append(f"{i}. {citation}")

    return "\n".join(parts) if parts else "No response received."


async def run_server():
    """Run the MCP server."""
    logger.info("Starting Perplexity MCP server...")

    # Validate cookies on startup
    try:
        get_client()
        logger.info("Cookies validated successfully")
    except CookieError as e:
        logger.warning(f"Cookie validation failed: {e}")
        logger.warning("Server will start but tools will fail until cookies are provided")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


def main():
    """Entry point for the MCP server."""
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.exception(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
MCP Server for Perplexity AI.

Thin MCP wrapper over the perplexity backend with LLM-optimized tool definitions.
Uses ClientPool with weighted rotation, exponential backoff, and multi-level fallback.
Shares pool state via pool_state.json for cross-process monitor coordination.
"""

import asyncio
import logging
import os
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent

from perplexity.server.app import run_query, get_pool
from .tools import TOOLS, get_mode_for_tool, TOOL_DEFAULT_SOURCES

# Configuration from environment
TIMEOUT_SECONDS = int(os.getenv("PERPLEXITY_TIMEOUT", "900"))  # 15 min default for research

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("perplexity-mcp")

# Valid tool names for dispatch
_VALID_TOOLS = {t.name for t in TOOLS}

# Create server instance
server = Server("perplexity-mcp")


@server.list_tools()
async def list_tools():
    """List available Perplexity tools."""
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """
    Handle tool calls by delegating to run_query().

    Before each query:
    1. Loads shared pool state from pool_state.json (noop if unchanged)
    2. If state is stale, refreshes rate limits via API (no queries consumed)
    3. For research: checks if any account has research quota
    4. Delegates to run_query() which handles rotation and fallback
    """
    logger.info(f"Tool call: {name} with args: {arguments}")

    if name not in _VALID_TOOLS:
        return [TextContent(
            type="text",
            text=f"Unknown tool: {name}. Available: {list(_VALID_TOOLS)}"
        )]

    # Extract arguments
    query = arguments.get("query", "")
    model = arguments.get("model")
    mode = get_mode_for_tool(name, model)
    sources = arguments.get("sources") or TOOL_DEFAULT_SOURCES.get(name, ["web"])
    language = arguments.get("language", "en-US")

    # Sync shared pool state before query (MCP is read-only, HTTP server owns config)
    pool = get_pool(config_writable=False)
    pool.reload_config()  # Pick up tokens added/removed via web UI
    pool.load_state()

    # Lazy rate-limit refresh — if state is stale (>1h), refresh via API (zero quota cost)
    if pool.is_state_stale(max_age_hours=1):
        logger.info("Rate limits stale, refreshing via API...")
        try:
            await pool.refresh_all_rate_limits()
        except Exception as e:
            logger.warning(f"Rate limit refresh failed: {e}")

    try:
        # Run synchronous run_query() in thread pool with timeout
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: run_query(
                    query=query,
                    mode=mode,
                    model=model,
                    sources=sources,
                    language=language,
                    fallback_to_auto=True,
                )
            ),
            timeout=TIMEOUT_SECONDS
        )

        # Format response
        text = format_result(result)
        logger.info(f"Tool {name} completed (status={result.get('status')}, mode={mode})")
        return [TextContent(type="text", text=text)]

    except asyncio.TimeoutError:
        error_msg = (
            f"Request timed out after {TIMEOUT_SECONDS}s. "
            f"For research queries, try setting PERPLEXITY_TIMEOUT higher in your environment."
        )
        logger.error(error_msg)
        return [TextContent(type="text", text=error_msg)]

    except Exception as e:
        error_msg = f"Unexpected error: {type(e).__name__}: {e}"
        logger.exception(error_msg)
        return [TextContent(type="text", text=error_msg)]


def format_result(result: dict) -> str:
    """Format run_query() result for MCP output.

    run_query() returns:
        {"status": "ok", "data": {"answer": ..., "sources": [...]}}
        {"status": "error", "error_type": ..., "message": ...}
    """
    if result.get("status") == "error":
        error_type = result.get("error_type", "Unknown")
        message = result.get("message", "Request failed.")
        return f"Error ({error_type}): {message}"

    data = result.get("data", {})
    parts = []

    # Fallback notice
    if data.get("fallback"):
        fallback_mode = data.get("fallback_mode", "auto")
        original_mode = data.get("original_mode", "unknown")
        parts.append(
            f"*Note: Fell back from '{original_mode}' to '{fallback_mode}' mode "
            f"(Pro quota exhausted).*\n"
        )

    # Main answer
    if answer := data.get("answer"):
        parts.append(answer)

    # Sources
    if sources := data.get("sources"):
        total = len(sources)
        shown_limit = 30

        parts.append(f"\n\n## Sources referenced ({total} total)")
        for i, source in enumerate(sources[:shown_limit], 1):
            url = source.get("url", "")
            title = source.get("title", url)
            parts.append(f"{i}. [{title}]({url})")

        if total > shown_limit:
            parts.append(f"\n*+ {total - shown_limit} more sources*")

    return "\n".join(parts) if parts else "No response received."


async def run_server():
    """Run the MCP server."""
    logger.info("Starting Perplexity MCP server...")

    # Initialize pool on startup to validate config
    try:
        pool = get_pool(config_writable=False)
        client_count = len(pool.clients)
        logger.info(f"Initialized pool with {client_count} client(s)")

        # Load shared state from monitor (if available)
        if pool.load_state():
            logger.info("Loaded shared pool state from monitor")
    except Exception as e:
        logger.warning(f"Pool initialization failed: {e}")
        logger.warning("Server will start but tools may fail until config is fixed")

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

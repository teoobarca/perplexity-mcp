"""
MCP Tool definitions for Perplexity.
"""

from mcp.types import Tool

# Tool definitions for MCP server
TOOLS = [
    Tool(
        name="perplexity_ask",
        description=(
            "Pro mode search with Perplexity AI. Returns comprehensive answers "
            "with citations. Best for general questions requiring detailed responses."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["web", "scholar", "social"]},
                    "description": "Information sources to search. Default: ['web']"
                },
                "language": {
                    "type": "string",
                    "description": "ISO 639 language code. Default: 'en-US'"
                }
            },
            "required": ["query"]
        }
    ),
    Tool(
        name="perplexity_research",
        description=(
            "Deep research mode for exhaustive analysis. Returns comprehensive "
            "research with extensive citations. Best for complex topics requiring "
            "thorough investigation. May take longer than other modes."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The research query"
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["web", "scholar", "social"]},
                    "description": "Information sources. Default: ['web', 'scholar']"
                },
                "language": {
                    "type": "string",
                    "description": "ISO 639 language code. Default: 'en-US'"
                }
            },
            "required": ["query"]
        }
    ),
    Tool(
        name="perplexity_reason",
        description=(
            "Reasoning mode for step-by-step analysis. Returns structured "
            "reasoning with logical steps. Best for questions requiring "
            "analytical thinking and problem-solving."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The query requiring reasoning"
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["web", "scholar", "social"]},
                    "description": "Information sources. Default: ['web']"
                },
                "language": {
                    "type": "string",
                    "description": "ISO 639 language code. Default: 'en-US'"
                }
            },
            "required": ["query"]
        }
    ),
    Tool(
        name="perplexity_search",
        description=(
            "Basic auto mode search. Returns quick answers with citations. "
            "Best for simple factual queries that don't require deep analysis."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["web", "scholar", "social"]},
                    "description": "Information sources. Default: ['web']"
                },
                "language": {
                    "type": "string",
                    "description": "ISO 639 language code. Default: 'en-US'"
                }
            },
            "required": ["query"]
        }
    )
]

# Map tool names to client methods
TOOL_METHOD_MAP = {
    "perplexity_ask": "ask",
    "perplexity_research": "research",
    "perplexity_reason": "reason",
    "perplexity_search": "search"
}

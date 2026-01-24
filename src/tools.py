"""
MCP Tool definitions for Perplexity.

Tool descriptions are optimized for LLM agents - they explain:
1. What the tool does and when to use it
2. That Perplexity is an AI model (not a search engine) that benefits from context
3. Examples of good queries in parameter descriptions
"""

from mcp.types import Tool

# Tool definitions for MCP server
TOOLS = [
    Tool(
        name="perplexity_ask",
        description=(
            "AI-powered answer engine for tech questions, documentation lookups, and how-to guides. "
            "Perplexity is an AI model (not a search engine) - provide context and specific requirements "
            "in your query for better results. Returns synthesized answers with citations."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Natural language question with context. Include specific requirements, "
                        "constraints, or use case. Example: 'How to implement JWT auth in Next.js 14 "
                        "App Router with httpOnly cookies for a SaaS app?'"
                    )
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
            "Deep research agent for comprehensive analysis of complex topics. "
            "Provide detailed context about what you need and why - this AI model spends more time "
            "gathering and synthesizing information. Returns extensive reports with 10-30+ citations. "
            "Use for architecture decisions, technology comparisons, or thorough investigations."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Detailed research question with full context. Explain the problem, "
                        "constraints, and what insights you need. Example: 'Best practices for "
                        "LLM API key rotation in production Node.js apps - need patterns for "
                        "zero-downtime rotation, secret storage options, and monitoring.'"
                    )
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
            "Reasoning-focused AI for analytical questions requiring step-by-step thinking. "
            "Best for comparisons, trade-off analysis, and decisions. Provide your specific "
            "situation and requirements - the model reasons through options systematically."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Analytical question with your specific context. Include constraints, "
                        "priorities, and what you're optimizing for. Example: 'Should I use "
                        "Prisma or Drizzle for a new Next.js project? Need type-safety, "
                        "good DX, and must work with Planetscale MySQL.'"
                    )
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
            "Quick fact lookup for simple questions. Use perplexity_ask for tech questions "
            "or perplexity_reason for comparisons. Returns brief answers with citations."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Simple factual question. Example: 'What is the latest stable version of React?'"
                    )
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

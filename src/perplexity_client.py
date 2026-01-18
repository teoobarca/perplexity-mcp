"""
Perplexity client wrapper for MCP server.
Uses helallao/perplexity-ai library with cookie-based authentication.
"""

import os
import logging
from typing import Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class PerplexityClientError(Exception):
    """Base exception for Perplexity client errors."""
    pass


class CookieError(PerplexityClientError):
    """Raised when cookies are missing or invalid."""
    pass


class PerplexityClient:
    """
    Wrapper over perplexity-api library for MCP integration.

    Provides simplified methods for different query modes:
    - ask: Pro mode search
    - research: Deep research mode
    - reason: Reasoning mode
    - search: Basic auto mode
    """

    def __init__(self, cookies: Optional[dict] = None):
        """
        Initialize client with Perplexity cookies.

        Args:
            cookies: Dict with 'next-auth.csrf-token' and 'next-auth.session-token'.
                    If None, will attempt to load from environment variables.
        """
        if cookies is None:
            cookies = self._load_cookies_from_env()

        self._validate_cookies(cookies)
        self.cookies = cookies
        self._client = None

    def _load_cookies_from_env(self) -> dict:
        """Load cookies from environment variables."""
        # Load .env file if exists
        env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
        load_dotenv(env_path)

        csrf_token = os.getenv('PERPLEXITY_CSRF_TOKEN')
        session_token = os.getenv('PERPLEXITY_SESSION_TOKEN')

        cookies = {}
        if csrf_token:
            cookies['next-auth.csrf-token'] = csrf_token
        if session_token:
            cookies['next-auth.session-token'] = session_token

        return cookies

    def _validate_cookies(self, cookies: dict) -> None:
        """Validate that required cookies are present."""
        if not cookies:
            raise CookieError(
                "No cookies provided. Set PERPLEXITY_CSRF_TOKEN and "
                "PERPLEXITY_SESSION_TOKEN environment variables or pass cookies dict."
            )

        # Session token is required, CSRF is optional for some operations
        if 'next-auth.session-token' not in cookies:
            raise CookieError(
                "Missing 'next-auth.session-token' cookie. "
                "Get it from perplexity.ai using browser dev tools."
            )

    def _get_client(self):
        """Get or create the perplexity client (lazy initialization)."""
        if self._client is None:
            import perplexity
            self._client = perplexity.Client(self.cookies)
        return self._client

    def ask(
        self,
        query: str,
        sources: Optional[list[str]] = None,
        language: str = "en-US"
    ) -> dict:
        """
        Pro mode search with citations.

        Args:
            query: Search query
            sources: List of sources ['web', 'scholar', 'social']
            language: ISO 639 language code

        Returns:
            Dict with 'answer' and 'citations' keys
        """
        sources = sources or ["web"]
        client = self._get_client()

        response = client.search(
            query,
            mode="pro",
            sources=sources,
            language=language,
            stream=False
        )

        return self._format_response(response)

    def research(
        self,
        query: str,
        sources: Optional[list[str]] = None,
        language: str = "en-US"
    ) -> dict:
        """
        Deep research mode for exhaustive analysis.

        Args:
            query: Research query
            sources: List of sources ['web', 'scholar', 'social']
            language: ISO 639 language code

        Returns:
            Dict with 'answer', 'citations', and 'chunks' keys
        """
        sources = sources or ["web", "scholar"]
        client = self._get_client()

        response = client.search(
            query,
            mode="deep research",
            sources=sources,
            language=language,
            stream=False
        )

        return self._format_response(response)

    def reason(
        self,
        query: str,
        sources: Optional[list[str]] = None,
        language: str = "en-US"
    ) -> dict:
        """
        Reasoning mode for step-by-step analysis.

        Args:
            query: Query requiring reasoning
            sources: List of sources ['web', 'scholar', 'social']
            language: ISO 639 language code

        Returns:
            Dict with 'answer' and reasoning details
        """
        sources = sources or ["web"]
        client = self._get_client()

        response = client.search(
            query,
            mode="reasoning",
            sources=sources,
            language=language,
            stream=False
        )

        return self._format_response(response)

    def search(
        self,
        query: str,
        sources: Optional[list[str]] = None,
        language: str = "en-US"
    ) -> dict:
        """
        Basic auto mode search.

        Args:
            query: Search query
            sources: List of sources ['web', 'scholar', 'social']
            language: ISO 639 language code

        Returns:
            Dict with 'answer' and 'citations' keys
        """
        sources = sources or ["web"]
        client = self._get_client()

        response = client.search(
            query,
            mode="auto",
            sources=sources,
            language=language,
            stream=False
        )

        return self._format_response(response)

    def _format_response(self, response: dict) -> dict:
        """Format response to consistent structure."""
        if response is None:
            return {
                "answer": "No response received from Perplexity.",
                "citations": [],
                "chunks": []
            }

        return {
            "answer": response.get("answer", ""),
            "citations": response.get("web_results", []),
            "chunks": response.get("chunks", []),
            "raw": response  # Include raw response for debugging
        }

"""
Colorist API Client

Routes Claude API calls through the Colorist gateway.
Based on paintress implementation pattern.
"""

import os
from anthropic import AsyncAnthropic, Anthropic
from typing import Optional
import httpx


class ColoristClient:
    """
    Claude client routed through Colorist gateway.

    The Colorist gateway provides a unified interface for LLM calls
    with usage tracking and rate limiting.
    """

    DEFAULT_API_KEY = ""  # Set via COLORIST_API_KEY env var
    DEFAULT_GATEWAY_URL = "https://colorist-gateway-staging.arco.ai"
    # Colorist model format: claude-4-5-sonnet-by-all (from paintress config)
    DEFAULT_MODEL = "claude-4-5-sonnet-by-all"

    def __init__(
        self,
        api_key: Optional[str] = None,
        gateway_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("COLORIST_API_KEY", self.DEFAULT_API_KEY)
        self.gateway_url = gateway_url or os.environ.get("COLORIST_GATEWAY_URL", self.DEFAULT_GATEWAY_URL)
        self.model = model or os.environ.get("COLORIST_MODEL", self.DEFAULT_MODEL)

        # Create http client (matches paintress pattern)
        self.http_client = httpx.AsyncClient()

        # Following paintress pattern: use auth_token, no /v1 suffix
        # The gateway handles routing based on the endpoint path
        self.client = AsyncAnthropic(
            auth_token=self.api_key,
            base_url=self.gateway_url,
            http_client=self.http_client,
        )

    async def create_message(self, **kwargs):
        """
        Create a message using the Claude API.

        Proxies to Anthropic's messages.create with Colorist gateway.
        """
        # Use default model if not specified
        if "model" not in kwargs:
            kwargs["model"] = self.model

        return await self.client.messages.create(**kwargs)

    async def create_message_stream(self, **kwargs):
        """
        Create a streaming message using the Claude API.

        Returns an async context manager for streaming responses.
        """
        if "model" not in kwargs:
            kwargs["model"] = self.model

        return self.client.messages.stream(**kwargs)

    def get_sync_client(self) -> Anthropic:
        """Get a synchronous Anthropic client for non-async contexts."""
        return Anthropic(
            auth_token=self.api_key,
            base_url=self.gateway_url,
        )

    async def close(self):
        """Close the HTTP client."""
        await self.http_client.aclose()


# Global client instance
_client: Optional[ColoristClient] = None


def get_colorist_client() -> ColoristClient:
    """Get or create the global Colorist client."""
    global _client
    if _client is None:
        _client = ColoristClient()
    return _client

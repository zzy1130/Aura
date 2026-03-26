"""
Colorist Provider for PydanticAI

Custom provider that routes Claude API calls through the Colorist gateway.
Based on paintress/models/colorist.py pattern.
"""

import os
from functools import cache
from typing import Any

from dotenv import load_dotenv
load_dotenv()  # Ensure .env is loaded

import httpx
from anthropic import AsyncAnthropic
from pydantic_ai.models import Model
from pydantic_ai.models import infer_model as legacy_infer_model
from pydantic_ai.providers import Provider
from pydantic_ai.providers.anthropic import AnthropicProvider


# Default configuration - API key must be set via COLORIST_API_KEY environment variable
DEFAULT_API_KEY = ""  # Set via COLORIST_API_KEY env var
DEFAULT_GATEWAY_URL = "https://colorist-gateway-staging.arco.ai"
DEFAULT_MODEL = "claude-4-5-sonnet-by-all"

# Gemini model for vibe research (cheaper, higher rate limits)
GEMINI_FLASH_MODEL = "gemini-3-flash-preview"


@cache
def _cached_http_client(
    timeout: int = 300,
    connect: int = 5,
    read: int = 300,
) -> httpx.AsyncClient:
    """Create a cached HTTP client for connection pooling."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout=timeout, connect=connect, read=read),
    )


def get_http_client() -> httpx.AsyncClient:
    """Get or create the shared HTTP client."""
    client = _cached_http_client()
    if client.is_closed:
        _cached_http_client.cache_clear()
        client = _cached_http_client()
    return client


def gateway_provider(provider_name: str) -> Provider[Any]:
    """
    Create a PydanticAI provider for the Colorist gateway.

    This function is passed to pydantic_ai's infer_model to handle
    model instantiation with custom gateway configuration.

    Args:
        provider_name: The provider name extracted from model string
                      (e.g., "anthropic" from "anthropic:claude-4-5-sonnet-by-all")

    Returns:
        Configured provider instance

    Raises:
        KeyError: If provider is not supported
    """
    api_key = os.getenv("COLORIST_API_KEY", DEFAULT_API_KEY)
    base_url = os.getenv("COLORIST_GATEWAY_URL", DEFAULT_GATEWAY_URL)

    http_client = get_http_client()

    if provider_name == "anthropic":
        return AnthropicProvider(
            anthropic_client=AsyncAnthropic(
                auth_token=api_key,
                base_url=base_url,
                http_client=http_client,
            )
        )
    else:
        raise KeyError(
            f"Unsupported provider: {provider_name}. "
            f"Aura uses 'anthropic' provider for all models via Colorist gateway."
        )


def infer_model(model: str | None = None) -> Model:
    """
    Infer a PydanticAI model from a model string, configured for Colorist gateway.

    Args:
        model: Model string in format "provider:model_name"
               (e.g., "anthropic:claude-4-5-sonnet-by-all")
               If None, uses the default model.

    Returns:
        Configured Model instance for use with PydanticAI Agent

    Example:
        from pydantic_ai import Agent
        from backend.agent.providers import infer_model

        agent = Agent(
            model=infer_model("anthropic:claude-4-5-sonnet-by-all"),
            ...
        )
    """
    if model is None:
        model = f"anthropic:{DEFAULT_MODEL}"

    return legacy_infer_model(model, gateway_provider)


def get_default_model() -> Model:
    """Get the default model (Claude Sonnet 4.5 via Colorist)."""
    return infer_model()


# For convenience - pre-configured models
def get_sonnet_model() -> Model:
    """Get Claude Sonnet 4.5 model."""
    return infer_model("anthropic:claude-4-5-sonnet-by-all")


def get_haiku_model() -> Model:
    """Get Claude Haiku 4.5 model (faster, cheaper)."""
    return infer_model("anthropic:claude-4-5-haiku-by-all")


def get_opus_model() -> Model:
    """Get Claude Opus 4.5 model (most capable)."""
    return infer_model("anthropic:claude-4-5-opus-by-all")


def get_gemini_flash_model() -> Model:
    """Get Gemini 3 Flash model via Colorist (cheaper, higher rate limits, good for vibe research)."""
    # Colorist routes all models through the same Anthropic-style API
    return infer_model(f"anthropic:{GEMINI_FLASH_MODEL}")


def get_model(
    provider: str = "colorist",
    model_id: str | None = None,
    api_key: str | None = None,
) -> Model:
    """
    Get a model based on provider selection.

    This is the unified entry point for getting models from any supported provider.

    Args:
        provider: Provider name ("colorist" or "dashscope")
        model_id: Model ID to use (required for dashscope, ignored for colorist)
        api_key: API key (required for dashscope, ignored for colorist)

    Returns:
        Configured Model instance for use with PydanticAI Agent

    Raises:
        ValueError: If provider is unknown or required params are missing
    """
    if provider == "colorist":
        return get_default_model()

    elif provider == "dashscope":
        if not api_key:
            raise ValueError("DashScope provider requires an API key")

        from agent.providers.dashscope import get_dashscope_model
        return get_dashscope_model(api_key=api_key, model_id=model_id)

    else:
        raise ValueError(
            f"Unknown provider: {provider}. "
            f"Available providers: colorist, dashscope"
        )

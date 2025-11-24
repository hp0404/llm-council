"""Model management for OpenRouter integration."""

import asyncio
from datetime import datetime, timedelta
from typing import Any

import aiohttp

# Cache for models list
_models_cache: dict[str, Any] | None = None
_cache_timestamp: datetime | None = None
_cache_duration = timedelta(hours=24)  # Cache for 24 hours
_fetch_lock = asyncio.Lock()

# Default preselected models
DEFAULT_COUNCIL_MODELS = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "qwen/qwen3-30b-a3b-thinking-2507",
    "qwen/qwen3-235b-a22b-thinking-2507",
]

DEFAULT_CHAIRMAN_MODEL = "openai/gpt-5-mini"


async def fetch_models_from_openrouter() -> dict[str, Any]:
    """
    Fetch the list of available models from OpenRouter API.

    Returns:
        Dict with 'data' key containing list of model objects
    """
    url = "https://openrouter.ai/api/v1/models"

    async with aiohttp.ClientSession() as session:
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise Exception(f"Failed to fetch models: HTTP {response.status}")


async def get_available_models(force_refresh: bool = False) -> dict[str, Any]:
    """
    Get available models from cache or fetch if needed.

    Args:
        force_refresh: If True, bypass cache and fetch fresh data

    Returns:
        Dict with 'data' key containing list of model objects
    """
    global _models_cache, _cache_timestamp

    async with _fetch_lock:
        now = datetime.now()

        # Check if cache is valid
        if (
            not force_refresh
            and _models_cache is not None
            and _cache_timestamp is not None
            and (now - _cache_timestamp) < _cache_duration
        ):
            return _models_cache

        # Fetch fresh data
        try:
            models_data = await fetch_models_from_openrouter()
            _models_cache = models_data
            _cache_timestamp = now
            return models_data
        except Exception as e:
            # If fetch fails but we have cached data, return it
            if _models_cache is not None:
                return _models_cache
            raise e


def format_models_for_ui(models_data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Format models data for UI consumption.

    Args:
        models_data: Raw data from OpenRouter API

    Returns:
        List of formatted model objects
    """
    models = models_data.get("data", [])

    formatted = []
    for model in models:
        formatted.append(
            {
                "id": model.get("id", ""),
                "name": model.get("name", ""),
                "description": model.get("description", ""),
                "context_length": model.get("context_length", 0),
                "pricing": model.get("pricing", {}),
                "architecture": model.get("architecture", {}),
            }
        )

    return formatted


def get_default_config() -> dict[str, Any]:
    """
    Get the default model configuration.

    Returns:
        Dict with council_models and chairman_model
    """
    return {
        "council_models": DEFAULT_COUNCIL_MODELS.copy(),
        "chairman_model": DEFAULT_CHAIRMAN_MODEL,
    }

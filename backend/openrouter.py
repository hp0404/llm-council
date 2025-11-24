"""OpenRouter API client for making LLM requests."""

import json
import logging
import os
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import create_engine, text

from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL

logger = logging.getLogger("llm_logger")

DEFAULT_DATABASE_URL = os.getenv("LLMLOGER_DATABASE_URL")


def llm_call(
    *,
    system_prompt: str | None = None,
    user_message: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    temperature: float = 1.0,
    completion: Any | None = None,
    task: str | None = None,
    completion_type: str | None = None,
    set_daily_max_tokens: (
        int | None
    ) = None,  # kept for backwards compatibility, ignored
    is_batched: bool = False,
    database_url: str | None = None,
) -> None:
    """
    Minimal standalone logger for LLM calls.
    Inserts new rows into the existing `llm_interactions` table (no daily limit checks).
    """

    if completion is None:
        raise ValueError("completion must not be None")

    completion_id = getattr(completion, "id", None) or completion.get("id")
    if completion_id is None:
        raise ValueError("completion object must have an 'id' attribute")

    created_ts = getattr(completion, "created", None) or completion.get("created")
    if created_ts:
        created_at = datetime.fromtimestamp(created_ts)
    else:
        created_at = datetime.now()

    # Extract token usage
    token_fields = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "prompt_tokens_cached": 0,
        "prompt_tokens_audio": 0,
        "completion_tokens_reasoning": 0,
        "completion_tokens_audio": 0,
        "completion_tokens_accepted": 0,
        "completion_tokens_rejected": 0,
    }

    usage = getattr(completion, "usage", None) or completion.get("usage")
    if usage is not None:
        if isinstance(usage, dict):
            token_fields["prompt_tokens"] = usage.get("prompt_tokens", 0) or 0
            token_fields["completion_tokens"] = usage.get("completion_tokens", 0) or 0
            token_fields["total_tokens"] = usage.get("total_tokens", 0) or 0

            prompt_details = usage.get("prompt_tokens_details")
            if prompt_details is not None and isinstance(prompt_details, dict):
                token_fields["prompt_tokens_cached"] = (
                    prompt_details.get("cached_tokens", 0) or 0
                )
                token_fields["prompt_tokens_audio"] = (
                    prompt_details.get("audio_tokens", 0) or 0
                )

            completion_details = usage.get("completion_tokens_details")
            if completion_details is not None and isinstance(completion_details, dict):
                token_fields["completion_tokens_reasoning"] = (
                    completion_details.get("reasoning_tokens", 0) or 0
                )
                token_fields["completion_tokens_audio"] = (
                    completion_details.get("audio_tokens", 0) or 0
                )
                token_fields["completion_tokens_accepted"] = (
                    completion_details.get("accepted_prediction_tokens", 0) or 0
                )
                token_fields["completion_tokens_rejected"] = (
                    completion_details.get("rejected_prediction_tokens", 0) or 0
                )
        else:
            token_fields["prompt_tokens"] = getattr(usage, "prompt_tokens", 0) or 0
            token_fields["completion_tokens"] = (
                getattr(usage, "completion_tokens", 0) or 0
            )
            token_fields["total_tokens"] = getattr(usage, "total_tokens", 0) or 0

            prompt_details = getattr(usage, "prompt_tokens_details", None)
            if prompt_details is not None:
                token_fields["prompt_tokens_cached"] = (
                    getattr(prompt_details, "cached_tokens", 0) or 0
                )
                token_fields["prompt_tokens_audio"] = (
                    getattr(prompt_details, "audio_tokens", 0) or 0
                )

            completion_details = getattr(usage, "completion_tokens_details", None)
            if completion_details is not None:
                token_fields["completion_tokens_reasoning"] = (
                    getattr(completion_details, "reasoning_tokens", 0) or 0
                )
                token_fields["completion_tokens_audio"] = (
                    getattr(completion_details, "audio_tokens", 0) or 0
                )
                token_fields["completion_tokens_accepted"] = (
                    getattr(completion_details, "accepted_prediction_tokens", 0) or 0
                )
                token_fields["completion_tokens_rejected"] = (
                    getattr(completion_details, "rejected_prediction_tokens", 0) or 0
                )

    # Provider / model / task / completion_type defaults
    if provider is None:
        provider = "openrouter"

    if completion_type is None:
        completion_type = getattr(completion, "object", None) or completion.get(
            "object", "chat"
        )

    if model is None:
        model_val = getattr(completion, "model", None) or completion.get("model")
        if model_val is None:
            raise ValueError("Either 'model' argument or completion.model must be set")
        model = str(model_val)

    if task is None:
        task = "chat_completion"

    user_message_db = user_message or ""

    # Convert completion object to JSON-serialisable dict for JSONB
    if hasattr(completion, "model_dump"):
        completion_dict = completion.model_dump()
    elif hasattr(completion, "dict"):
        completion_dict = completion.dict()
    elif isinstance(completion, dict):
        completion_dict = completion
    else:
        completion_dict = {
            k: getattr(completion, k)
            for k in dir(completion)
            if not k.startswith("_") and not callable(getattr(completion, k))
        }

    completion_json = json.dumps(completion_dict)

    db_url = database_url or os.getenv("LLMLOGER_DATABASE_URL", DEFAULT_DATABASE_URL)
    engine = create_engine(db_url)

    try:
        with engine.begin() as conn:
            # Duplicate check
            exists = conn.execute(
                text(
                    "SELECT 1 FROM llm_interactions "
                    "WHERE completion_id = :cid LIMIT 1"
                ),
                {"cid": completion_id},
            ).scalar()

            if exists:
                logger.debug(
                    "Skipping duplicate LLM interaction with ID %s", completion_id
                )
                return

            params = {
                "completion_id": completion_id,
                "completion_type": completion_type,
                "task": task,
                "model": model,
                "provider": provider,
                "temperature": float(temperature),
                "system_message": system_prompt,
                "user_message": user_message_db,
                "created_at": created_at,
                "completion": completion_json,
                "is_batched": bool(is_batched),
                "error": None,
                **token_fields,
            }

            conn.execute(
                text(
                    """
                    INSERT INTO llm_interactions (
                        completion_id,
                        completion_type,
                        task,
                        model,
                        provider,
                        temperature,
                        system_message,
                        user_message,
                        created_at,
                        completion,
                        prompt_tokens,
                        completion_tokens,
                        total_tokens,
                        prompt_tokens_cached,
                        prompt_tokens_audio,
                        completion_tokens_reasoning,
                        completion_tokens_audio,
                        completion_tokens_accepted,
                        completion_tokens_rejected,
                        error,
                        is_batched
                    )
                    VALUES (
                        :completion_id,
                        :completion_type,
                        :task,
                        :model,
                        :provider,
                        :temperature,
                        :system_message,
                        :user_message,
                        :created_at,
                        CAST(:completion AS jsonb),
                        :prompt_tokens,
                        :completion_tokens,
                        :total_tokens,
                        :prompt_tokens_cached,
                        :prompt_tokens_audio,
                        :completion_tokens_reasoning,
                        :completion_tokens_audio,
                        :completion_tokens_accepted,
                        :completion_tokens_rejected,
                        :error,
                        :is_batched
                    )
                    """
                ),
                params,
            )

            logger.debug("Logged LLM interaction with ID %s", completion_id)

    except Exception:
        logger.error("Failed to log LLM interaction", exc_info=True)
        raise


async def query_model(
    model: str, messages: list[dict[str, str]], timeout: float = 120.0
) -> dict[str, Any] | None:
    """
    Query a single model via OpenRouter API.

    Args:
        model: OpenRouter model identifier (e.g., "openai/gpt-4o")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content' and optional 'reasoning_details', or None if failed
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                OPENROUTER_API_URL, headers=headers, json=payload
            )
            response.raise_for_status()

            data = response.json()
            message = data["choices"][0]["message"]

            # Extract system prompt and user message for logging
            system_prompt = None
            user_message = None
            for msg in messages:
                if msg.get("role") == "system":
                    system_prompt = msg.get("content")
                elif msg.get("role") == "user":
                    user_message = msg.get("content")

            # Extract provider from response (e.g., "Novita", "OpenAI", etc.)
            provider = data.get("provider", "openrouter")

            # Log the LLM call
            try:
                llm_call(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    model=model,
                    provider=provider,
                    completion=data,
                    task="llm_council_query",
                    completion_type="chat.completion",
                )
            except Exception as log_error:
                logger.error(f"Failed to log LLM call for model {model}: {log_error}")

            return {
                "content": message.get("content"),
                "reasoning_details": message.get("reasoning_details"),
            }

    except Exception as e:
        print(f"Error querying model {model}: {e}")
        return None


async def query_models_parallel(
    models: list[str], messages: list[dict[str, str]]
) -> dict[str, dict[str, Any] | None]:
    """
    Query multiple models in parallel.

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    import asyncio

    # Create tasks for all models
    tasks = [query_model(model, messages) for model in models]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return {model: response for model, response in zip(models, responses)}

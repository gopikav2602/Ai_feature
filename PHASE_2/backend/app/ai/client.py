"""
AI client layer — provider-agnostic.

Public API
----------
build_client(settings)  → BoschClient | ClaudeClient

    Factory used at startup.  NarrativeService holds the result and
    calls client.generate(user_message) — it never knows which provider
    is active.

BoschClient
    Calls the Bosch LLM Farm OpenAI-compatible Chat Completions endpoint
    via plain httpx (no Azure/OpenAI SDK dependency).

    Authentication:  genaiplatform-farm-subscription-key header
                     (NOT Authorization: Bearer)
    Endpoint:        https://aoai-farm.bosch-temp.com/api/openai/deployments/
                     {deployment}/chat/completions?api-version={version}
    Response format: standard OpenAI chat completion JSON
    Structured output: JSON mode — model is instructed to return strict JSON;
                        no tool-calling required.

ClaudeClient (unchanged from previous version)
    Calls the Anthropic Messages API using the anthropic SDK.
    Structured output: tool-use / submit_advisor_explanation.

Both clients
    - enforce ai_settings.ai_timeout
    - retry transient failures (429, 500, 529) up to MAX_RETRIES times
      with exponential back-off
    - raise typed exceptions from app.ai.exceptions
    - return Dict[str, Any] that NarrativeService passes to
      AdvisorOutput.model_validate()

Swapping providers
    Set AI_PROVIDER=bosch or AI_PROVIDER=anthropic in .env.
    build_client() returns the right implementation.
    NarrativeService, cache, renderer — zero changes.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict

import httpx

from app.ai.config import AISettings
from app.ai.exceptions import (
    AIClientError,
    AIResponseError,
    AIRetryExhaustedError,
    AITimeoutError,
)
from app.ai.prompts import (
    ADVISOR_SYSTEM_PROMPT,
    ADVISOR_OUTPUT_TOOL,
    BOSCH_SYSTEM_PROMPT,
    BOSCH_JSON_SCHEMA_INSTRUCTION,
)

logger = logging.getLogger(__name__)

MAX_RETRIES: int = 3
RETRY_BASE_DELAY: float = 0.5        # seconds; doubles each attempt
RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 529})


# ---------------------------------------------------------------------------
# Bosch LLM Farm client
# ---------------------------------------------------------------------------


class BoschClient:
    """
    Async HTTP client for the Bosch LLM Farm (OpenAI-compatible endpoint).

    The Bosch Farm does not support Anthropic-style tool-calling.
    Structured output is achieved by:
      1. Including the AdvisorOutput JSON schema in the system prompt
         (see app/ai/prompts.py: BOSCH_JSON_SCHEMA_INSTRUCTION)
      2. Instructing the model to return ONLY valid JSON, no markdown fences
      3. Parsing the response with json.loads() and validating with Pydantic

    This is identical to what NarrativeService already does with the
    Anthropic client — the only difference is how the model is told to
    structure its output.
    """

    def __init__(self, settings: AISettings) -> None:
        if not settings.bosch_api_key:
            raise AIClientError(
                "BOSCH_API_KEY is not set.  Add it to your .env file."
            )
        self._settings = settings
        # One shared connection pool for the application lifetime.
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.ai_timeout),
            headers={
                "Content-Type": "application/json",
                "genaiplatform-farm-subscription-key": settings.bosch_api_key,
            },
        )

    async def generate(self, user_message: str) -> Dict[str, Any]:
        """
        Send a chat completion request to the Bosch LLM Farm and return
        the parsed AdvisorOutput dict.

        Raises
        ------
        AITimeoutError          Request exceeded ai_settings.ai_timeout
        AIClientError           Non-retryable HTTP or network error
        AIRetryExhaustedError   All retry attempts failed
        AIResponseError         Response was not valid JSON / empty content
        """
        last_exc: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return await self._create_message(user_message)

            except httpx.TimeoutException as exc:
                logger.warning(
                    "Bosch LLM Farm timed out (attempt %d/%d): %s",
                    attempt, MAX_RETRIES, exc,
                )
                last_exc = AITimeoutError(
                    f"Bosch LLM Farm call timed out after {self._settings.ai_timeout}s"
                )
                last_exc.__cause__ = exc

            except AIResponseError:
                # Structural problem — retrying won't fix it.
                raise

            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status not in RETRYABLE_STATUS_CODES:
                    err = AIClientError(
                        f"Bosch LLM Farm HTTP {status}: {exc.response.text[:200]}"
                    )
                    err.__cause__ = exc
                    raise err
                logger.warning(
                    "Retryable HTTP %d from Bosch Farm (attempt %d/%d)",
                    status, attempt, MAX_RETRIES,
                )
                last_exc = exc

            except httpx.RequestError as exc:
                logger.warning(
                    "Network error calling Bosch Farm (attempt %d/%d): %s",
                    attempt, MAX_RETRIES, exc,
                )
                last_exc = AIClientError(f"Network error: {exc}")

            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.debug("Retrying in %.1fs …", delay)
                await asyncio.sleep(delay)

        raise AIRetryExhaustedError(
            f"Bosch LLM Farm call failed after {MAX_RETRIES} attempts"
        ) from last_exc

    async def _create_message(self, user_message: str) -> Dict[str, Any]:
        """Single attempt — no retry logic here."""
        payload = {
            "messages": [
                {"role": "system", "content": BOSCH_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "temperature": self._settings.ai_temperature,
            "max_tokens": self._settings.ai_max_tokens,
        }

        response = await self._http.post(
            self._settings.bosch_chat_url,
            json=payload,
        )
        response.raise_for_status()

        data = response.json()
        raw_text = self._extract_text(data)
        return self._parse_json(raw_text)

    @staticmethod
    def _extract_text(data: Dict[str, Any]) -> str:
        """
        Pull the assistant message content out of the OpenAI chat completion
        response envelope.

        Expected shape:
            {"choices": [{"message": {"content": "..."}}]}
        """
        try:
            choices = data["choices"]
            if not choices:
                raise AIResponseError("Bosch LLM Farm returned empty choices[]")
            content = choices[0]["message"]["content"]
            if not content or not content.strip():
                raise AIResponseError("Bosch LLM Farm returned empty message content")
            return content.strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise AIResponseError(
                f"Unexpected Bosch LLM Farm response shape: {exc}"
            ) from exc

    @staticmethod
    def _parse_json(raw_text: str) -> Dict[str, Any]:
        """
        Parse the model's text response as JSON.

        The system prompt instructs the model to return raw JSON with no
        markdown fences.  As a belt-and-suspenders measure, strip fences
        if the model adds them anyway (some model versions do despite the
        instruction).
        """
        # Strip optional ```json ... ``` wrapper
        text = raw_text
        if text.startswith("```"):
            # Remove opening fence (```json or ```)
            text = text[text.index("\n") + 1:] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[: text.rfind("```")]
        text = text.strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AIResponseError(
                f"Bosch LLM Farm response is not valid JSON: {exc}\n"
                f"Raw response (first 500 chars): {raw_text[:500]}"
            ) from exc

        if not isinstance(parsed, dict):
            raise AIResponseError(
                f"Expected a JSON object, got {type(parsed).__name__}"
            )
        return parsed

    async def aclose(self) -> None:
        """Close the underlying httpx connection pool.  Call at app shutdown."""
        await self._http.aclose()


# ---------------------------------------------------------------------------
# Anthropic / Claude client (unchanged from original)
# ---------------------------------------------------------------------------


class ClaudeClient:
    """
    Thin Anthropic SDK wrapper.  Kept intact so AI_PROVIDER=anthropic
    still works — useful for local dev / comparison testing.

    Structured output via Anthropic tool-calling (submit_advisor_explanation).
    """

    def __init__(self, settings: AISettings) -> None:
        try:
            import anthropic as _anthropic  # optional dep when using bosch provider
        except ImportError as exc:
            raise AIClientError(
                "anthropic package is not installed.  "
                "Run: pip install anthropic  "
                "or switch to AI_PROVIDER=bosch."
            ) from exc

        if not settings.anthropic_api_key:
            raise AIClientError(
                "ANTHROPIC_API_KEY is not set.  Add it to your .env file."
            )
        self._settings = settings
        self._client = _anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=httpx.Timeout(settings.ai_timeout),
        )
        self._anthropic = _anthropic

    async def generate(self, user_message: str) -> Dict[str, Any]:
        last_exc: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return await self._create_message(user_message)

            except httpx.TimeoutException as exc:
                logger.warning(
                    "Claude timed out (attempt %d/%d): %s", attempt, MAX_RETRIES, exc
                )
                last_exc = AITimeoutError(
                    f"Claude call timed out after {self._settings.ai_timeout}s"
                )
                last_exc.__cause__ = exc

            except AIResponseError:
                raise

            except self._anthropic.RateLimitError as exc:
                logger.warning("Rate limited (attempt %d/%d)", attempt, MAX_RETRIES)
                last_exc = exc

            except self._anthropic.InternalServerError as exc:
                logger.warning("Anthropic 5xx (attempt %d/%d)", attempt, MAX_RETRIES)
                last_exc = exc

            except self._anthropic.APIStatusError as exc:
                if exc.status_code not in RETRYABLE_STATUS_CODES:
                    err = AIClientError(
                        f"Anthropic API error {exc.status_code}: {exc.message}"
                    )
                    err.__cause__ = exc
                    raise err
                last_exc = exc

            except self._anthropic.APIError as exc:
                err = AIClientError(f"Anthropic API error: {exc}")
                err.__cause__ = exc
                raise err

            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

        err = AIRetryExhaustedError(
            f"Claude call failed after {MAX_RETRIES} attempts"
        )
        if last_exc is not None:
            err.__cause__ = last_exc
        raise err

    async def _create_message(self, user_message: str) -> Dict[str, Any]:
        response = await self._client.messages.create(
            model=self._settings.ai_model,
            max_tokens=self._settings.ai_max_tokens,
            system=ADVISOR_SYSTEM_PROMPT,
            tools=[ADVISOR_OUTPUT_TOOL],
            tool_choice={"type": "tool", "name": "submit_advisor_explanation"},
            messages=[{"role": "user", "content": user_message}],
        )
        for block in response.content:
            if getattr(block, "type", None) == "tool_use":
                return block.input  # type: ignore[return-value]
        raise AIResponseError(
            "Claude did not return a tool_use block.  "
            "Check tool_choice is respected by the model version."
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_client(settings: AISettings) -> BoschClient | ClaudeClient:
    """
    Return the correct client implementation based on settings.ai_provider.

    Call once at application startup; pass the result to NarrativeService.

        from app.ai.config import ai_settings
        from app.ai.client import build_client

        client = build_client(ai_settings)
        narrative_service = NarrativeService(client=client, settings=ai_settings)
    """
    if settings.ai_provider == "bosch":
        return BoschClient(settings)
    if settings.ai_provider == "anthropic":
        return ClaudeClient(settings)
    raise AIClientError(
        f"Unknown AI_PROVIDER '{settings.ai_provider}'. "
        "Valid values: 'bosch', 'anthropic'."
    )

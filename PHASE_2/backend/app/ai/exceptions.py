"""
AI-layer exceptions.

All exceptions raised inside app.ai bubble up as one of these types so
callers (NarrativeService) can catch a single base class and fall back to
deterministic templates without accidentally swallowing unrelated errors.
"""

from __future__ import annotations


class AIError(Exception):
    """Base class for all AI-layer errors."""


class AIClientError(AIError):
    """
    Raised when the Anthropic API call itself fails — network error,
    HTTP 4xx/5xx, auth failure, or an empty response from the provider.
    """


class AITimeoutError(AIClientError):
    """Raised when the API call exceeds ai_settings.ai_timeout seconds."""


class AIResponseError(AIError):
    """
    Raised when the API call succeeded but the response is unusable:
      - model returned plain text instead of the required tool_use block
      - tool input failed Pydantic validation against AdvisorOutput
      - a claim resolver raised an unexpected error at render time
    """


class AIRetryExhaustedError(AIClientError):
    """
    Raised after all retry attempts have failed.  Wraps the last
    underlying exception as __cause__.
    """

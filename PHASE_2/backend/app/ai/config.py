"""
AI layer configuration — provider-agnostic.

Supports two providers, selected by AI_PROVIDER:

  "anthropic"  (original)   — uses ANTHROPIC_API_KEY + Anthropic SDK
  "bosch"      (default)    — uses Bosch LLM Farm OpenAI-compatible endpoint

.env keys
---------
AI_PROVIDER             "bosch" | "anthropic"      default: bosch

# Bosch LLM Farm (used when AI_PROVIDER=bosch)
BOSCH_API_KEY           required for bosch
BOSCH_ENDPOINT          default: https://aoai-farm.bosch-temp.com
BOSCH_DEPLOYMENT        default: askbosch-prod-farm-openai-gpt-4o-mini-2024-07-18
BOSCH_API_VERSION       default: 2024-08-01-preview

# Anthropic (used when AI_PROVIDER=anthropic)
ANTHROPIC_API_KEY       required for anthropic

# Shared inference settings (apply to both providers)
AI_MODEL                default: gpt-4o-mini
AI_TEMPERATURE          default: 0.2
AI_TIMEOUT              default: 8.0   (seconds)
AI_MAX_TOKENS           default: 1024

# Feature flags
AI_ADVISOR_ENABLED      default: true
AI_CACHE_ENABLED        default: true

Usage
-----
    from app.ai.config import ai_settings
    from app.ai.client import build_client

    client = build_client(ai_settings)   # returns BoschClient or ClaudeClient
"""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings


class AISettings(BaseSettings):
    """
    Provider-agnostic AI infrastructure settings.

    Kept separate from app.core.config.Settings so the AI layer can be
    swapped or disabled without touching business-logic configuration.
    """

    # ─── Provider selector ───────────────────────────────────────────────────
    ai_provider: Literal["bosch", "anthropic"] = "bosch"

    # ─── Bosch LLM Farm ──────────────────────────────────────────────────────
    bosch_api_key: str = ""
    bosch_endpoint: str = "https://aoai-farm.bosch-temp.com"
    bosch_deployment: str = (
        "askbosch-prod-farm-openai-gpt-4o-mini-2024-07-18"
    )
    bosch_api_version: str = "2024-08-01-preview"

    # ─── Anthropic (kept for fallback / local dev) ───────────────────────────
    anthropic_api_key: str = ""

    # ─── Shared inference ────────────────────────────────────────────────────
    ai_model: str = "gpt-4o-mini"
    ai_temperature: float = 0.2
    ai_timeout: float = 8.0       # seconds; applied as httpx read timeout
    ai_max_tokens: int = 1024

    # ─── Feature flags ───────────────────────────────────────────────────────
    ai_advisor_enabled: bool = True
    ai_cache_enabled: bool = True

    @property
    def bosch_chat_url(self) -> str:
        """
        Full Chat Completions URL for the configured Bosch deployment.

        Example:
            https://aoai-farm.bosch-temp.com/api/openai/deployments/
            askbosch-prod-farm-openai-gpt-4o-mini-2024-07-18/
            chat/completions?api-version=2024-08-01-preview
        """
        return (
            f"{self.bosch_endpoint}/api/openai/deployments"
            f"/{self.bosch_deployment}/chat/completions"
            f"?api-version={self.bosch_api_version}"
        )

    class Config:
        env_file = ".env"
        case_sensitive = False


# Module-level singleton — import this everywhere instead of constructing
# a new instance per request.
ai_settings = AISettings()

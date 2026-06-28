"""
NarrativeService — the only place an LLM is called in Sprint Whisperer.

This module is now a pure orchestrator.  All infrastructure concerns live
in app.ai:

    app.ai.config    → AISettings (API key, model, timeout, tokens, flags)
    app.ai.client    → ClaudeClient (auth, retry, timeout, tool-call)
    app.ai.prompts   → ADVISOR_SYSTEM_PROMPT, ADVISOR_OUTPUT_TOOL
    app.ai.cache     → NarrativeCache / InMemoryNarrativeCache / cache_key()
    app.ai.renderer  → render_recommendation_explanation, render_scenario_explanation,
                        render_executive_summary

Hard invariants (unchanged from original design — enforced by construction):

  1. The model receives ONLY an AdvisorInput snapshot — no ProjectState,
     no engines, no callables.  Nothing it could use to derive a new number.

  2. The model MUST respond via the submit_advisor_explanation tool.
     ClaudeClient raises AIResponseError if it returns plain text instead.

  3. Every numeric claim is a ClaimRef → resolved by the renderer from
     the real AdvisorInput value at render time.  The model never writes
     a number directly.

  4. Any failure (timeout, bad JSON, unresolvable claim, disabled flag)
     degrades to the existing deterministic template text.  This layer
     can never block or corrupt the deterministic pipeline.

  5. Results are cached per (model, AdvisorInput) so re-calling with
     the same facts never hits the API twice.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.ai.cache import InMemoryNarrativeCache, NarrativeCache, cache_key
from app.ai.client import ClaudeClient
from app.ai.config import AISettings, ai_settings
from app.ai.exceptions import AIError
from app.ai.renderer import (
    render_executive_summary,
    render_recommendation_explanation,
    render_scenario_explanation,
)
from app.engines.advisor_contract import (
    AdvisorInput,
    AdvisorOutput,
    AdvisorResponseStatus,
)

logger = logging.getLogger(__name__)


def _build_user_message(advisor_input: AdvisorInput) -> str:
    return (
        "Here is the deterministic snapshot to explain:\n\n"
        f"{advisor_input.model_dump_json(indent=2)}"
    )


class NarrativeService:
    """
    Orchestrates:
        AdvisorInput
              │
              ▼
        NarrativeCache (check)
              │ miss
              ▼
        ClaudeClient.generate()
              │
              ▼
        AdvisorOutput  (Pydantic validation)
              │
              ▼
        Renderer  (ClaimRef → resolved values)
              │
              ▼
        NarrativeCache (store)
              │
              ▼
        Dict[str, Any]  (API response shape)

    On any failure → _fallback_response() using deterministic template text.
    """

    def __init__(
        self,
        client: ClaudeClient,
        settings: Optional[AISettings] = None,
        cache: Optional[NarrativeCache] = None,
    ) -> None:
        self.client = client
        self.settings = settings or ai_settings
        self.cache = cache or InMemoryNarrativeCache()

    async def explain(
        self,
        advisor_input: AdvisorInput,
        fallback_text_by_recommendation: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Generate (or retrieve from cache) an AI narrative for the given
        AdvisorInput snapshot.

        Parameters
        ----------
        advisor_input
            Closed, read-only snapshot of already-computed engine facts.
        fallback_text_by_recommendation
            Maps recommendation_id → the deterministic description string
            produced by the recommendation engine.  Used when the model call
            fails entirely or the model skips a recommendation.

        Returns
        -------
        {
            "status": "ok" | "partial" | "fallback",
            "executive_summary": {...} | None,
            "recommendation_explanations": [{...}, ...],
            "scenario_explanation": {...} | None,
        }
        """
        if not self.settings.ai_advisor_enabled:
            return self._fallback_response(advisor_input, fallback_text_by_recommendation)

        key = cache_key(advisor_input, self.settings.ai_model)
        if self.settings.ai_cache_enabled:
            cached = await self.cache.get(key)
            if cached is not None:
                return cached

        try:
            raw = await self.client.generate(_build_user_message(advisor_input))
            advisor_output = AdvisorOutput.model_validate(raw)
        except AIError as exc:
            logger.warning("Advisor call failed (%s); using template fallback", exc)
            return self._fallback_response(advisor_input, fallback_text_by_recommendation)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error in NarrativeService.explain: %s", exc)
            return self._fallback_response(advisor_input, fallback_text_by_recommendation)

        result = self._render(advisor_output, advisor_input, fallback_text_by_recommendation)

        if self.settings.ai_cache_enabled:
            await self.cache.set(key, result)

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _render(
        self,
        advisor_output: AdvisorOutput,
        advisor_input: AdvisorInput,
        fallback_text_by_recommendation: Dict[str, str],
    ) -> Dict[str, Any]:
        any_degraded = False

        # Executive summary
        rendered_exec_summary = None
        if advisor_output.executive_summary is not None:
            rendered_exec_summary = render_executive_summary(
                advisor_output.executive_summary, advisor_input
            )
            if not rendered_exec_summary["fully_resolved"]:
                any_degraded = True

        # Recommendation explanations
        rendered_recs = []
        seen_ids: set[str] = set()

        for explanation in advisor_output.recommendation_explanations:
            seen_ids.add(explanation.recommendation_id)
            rendered = render_recommendation_explanation(explanation, advisor_input)
            if not rendered["fully_resolved"]:
                any_degraded = True
            rendered_recs.append(rendered)

        # Any recommendation the model skipped falls back to its deterministic text.
        for rec_id, fallback_text in fallback_text_by_recommendation.items():
            if rec_id not in seen_ids:
                rendered_recs.append(
                    {
                        "recommendation_id": rec_id,
                        "sections": [
                            {"kind": "summary", "heading": "Summary", "body": fallback_text}
                        ],
                        "fully_resolved": True,
                        "source": "template_fallback",
                    }
                )

        # Scenario explanation
        rendered_scenario = None
        if advisor_output.scenario_explanation is not None:
            rendered_scenario = render_scenario_explanation(
                advisor_output.scenario_explanation, advisor_input
            )
            if not rendered_scenario["fully_resolved"]:
                any_degraded = True

        status = (
            AdvisorResponseStatus.PARTIAL if any_degraded else AdvisorResponseStatus.OK
        )
        return {
            "status": status.value,
            "executive_summary": rendered_exec_summary,
            "recommendation_explanations": rendered_recs,
            "scenario_explanation": rendered_scenario,
        }

    def _fallback_response(
        self,
        advisor_input: AdvisorInput,
        fallback_text_by_recommendation: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Deterministic-only fallback — no LLM involved, always succeeds.
        Numbers are read directly from the already-real AdvisorInput values.
        """
        fallback_exec_summary = None
        ctx = advisor_input.project_context
        if ctx is not None:
            delay_phrase = (
                f"{ctx.expected_delay_days:.0f} days late"
                if ctx.expected_delay_days > 0
                else f"{abs(ctx.expected_delay_days):.0f} days early"
            )
            fallback_exec_summary = {
                "headline": (
                    f"{ctx.current_sprint_name}: project is forecast to finish "
                    f"{delay_phrase}, with a {ctx.on_time_probability * 100:.0f}% "
                    f"chance of hitting the target date."
                ),
                "fully_resolved": True,
            }

        return {
            "status": AdvisorResponseStatus.FALLBACK.value,
            "executive_summary": fallback_exec_summary,
            "recommendation_explanations": [
                {
                    "recommendation_id": rec_id,
                    "sections": [
                        {"kind": "summary", "heading": "Summary", "body": text}
                    ],
                    "fully_resolved": True,
                    "source": "template_fallback",
                }
                for rec_id, text in fallback_text_by_recommendation.items()
            ],
            "scenario_explanation": None,
        }

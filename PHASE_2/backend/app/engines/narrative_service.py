"""
NarrativeService -- the only place an LLM is called in Sprint Whisperer.

Hard rules enforced by construction (see advisor_contract.py for the why):

  1. The model receives ONLY an AdvisorInput snapshot (facts already
     computed by the deterministic engines). No ProjectState, no
     engines, nothing it could use to compute a new number.

  2. The model is forced to respond via tool-calling against the
     AdvisorOutput JSON schema -- there is no free-text channel.
     Every numeric claim must be a ClaimRef (a path into the snapshot),
     never a literal number, and that's enforced both by the schema
     description AND by NarrativeSection's pydantic validator, which
     rejects raw digits outside {claim_N} placeholders.

  3. If the call fails, times out, returns malformed JSON, or any
     claim fails to resolve against real data, this service falls
     back to the existing deterministic template string
     (Recommendation.description / the rule-engine's own text).
     The narrative layer can only degrade gracefully -- it can never
     block or corrupt the deterministic pipeline.

  4. Results are cached per recommendation/scenario, keyed by a hash
     of the exact facts shown to the model. Same facts -> same cache
     entry. If the underlying numbers change (re-simulation), the
     hash changes and the cache naturally misses.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, Optional, Protocol

from pydantic_settings import BaseSettings

from app.engines.advisor_contract import (
    AdvisorInput,
    AdvisorOutput,
    AdvisorRecommendationExplanation,
    AdvisorResponseStatus,
    AdvisorScenarioExplanation,
    ProjectExecutiveSummary,
    render_executive_summary,
    render_recommendation_explanation,
    render_scenario_explanation,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Settings -- same style/section convention as app/core/config.py
# ---------------------------------------------------------------------------


class NarrativeSettings(BaseSettings):
    """Advisor / narrative-layer configuration."""

    # ─── AI Advisor Settings ─────────────────────────────────────────────────
    advisor_enabled: bool = True
    advisor_model: str = "claude-sonnet-4-6"
    advisor_max_tokens: int = 1024
    advisor_timeout_seconds: float = 8.0
    advisor_cache_enabled: bool = True


# ---------------------------------------------------------------------------
# Minimal client protocol -- so this module doesn't hard-depend on a
# specific SDK version. Swap in the real Anthropic client; it already
# matches the shape of client.messages.create(...).
# ---------------------------------------------------------------------------


class MessagesClient(Protocol):
    async def create(self, **kwargs: Any) -> Any: ...


# ---------------------------------------------------------------------------
# Tool schema -- this IS the contract. The model can only respond by
# filling in this shape, which mirrors AdvisorOutput exactly. There is
# no free-text response path for this call.
# ---------------------------------------------------------------------------

ADVISOR_OUTPUT_TOOL = {
    "name": "submit_advisor_explanation",
    "description": (
        "Submit your explanation of the deterministic recommendation/scenario "
        "data you were given. You must use this tool to respond -- do not "
        "respond with plain text."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "executive_summary": {
                "type": ["object", "null"],
                "description": (
                    "One short headline section summarizing overall project "
                    "state, shown before any recommendation explanations. "
                    "Only include if project_context was provided in the input."
                ),
                "properties": {
                    "headline": {"$ref": "#/$defs/section"},
                },
                "required": ["headline"],
            },
            "recommendation_explanations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "recommendation_id": {"type": "string"},
                        "why": {"$ref": "#/$defs/section"},
                        "evidence": {"$ref": "#/$defs/section"},
                        "benefits": {"$ref": "#/$defs/section"},
                        "trade_offs": {
                            "anyOf": [{"$ref": "#/$defs/section"}, {"type": "null"}],
                            "description": (
                                "Omit (null) if this recommendation genuinely has "
                                "no meaningful downside -- do not invent one."
                            ),
                        },
                        "next_step": {"$ref": "#/$defs/section"},
                    },
                    "required": ["recommendation_id", "why", "evidence", "benefits", "next_step"],
                },
            },
            "scenario_explanation": {
                "type": ["object", "null"],
                "properties": {
                    "scenario_id": {"type": "string"},
                    "why": {"$ref": "#/$defs/section"},
                    "evidence": {"$ref": "#/$defs/section"},
                    "benefits": {"$ref": "#/$defs/section"},
                    "trade_offs": {
                        "anyOf": [{"$ref": "#/$defs/section"}, {"type": "null"}],
                    },
                    "next_step": {"$ref": "#/$defs/section"},
                },
            },
        },
        "$defs": {
            "section": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "body_template": {
                        "type": "string",
                        "description": (
                            "Prose with {claim_0}, {claim_1}, ... placeholders. "
                            "NEVER write a literal number here -- every number "
                            "must be a placeholder referencing an entry in "
                            "`claims`. Entity IDs like 'B-03' or 'WI-041' are "
                            "fine to write directly since they are names, not "
                            "metrics."
                        ),
                    },
                    "claims": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "value_path": {
                                    "type": "string",
                                    "description": (
                                        "Dotted path into the AdvisorInput "
                                        "snapshot you were given, e.g. "
                                        "'scenario.days_saved' or "
                                        "'recommendations[0]."
                                        "estimated_hours_recovered' or "
                                        "'project_context.on_time_probability'. "
                                        "Must point at a real field you were "
                                        "shown -- do not invent a path."
                                    ),
                                },
                                "label": {
                                    "type": "string",
                                    "description": "Short label, e.g. 'days saved'",
                                },
                                "as_percentage": {
                                    "type": "boolean",
                                    "description": (
                                        "Set true if this field is a 0.0-1.0 "
                                        "fraction that should display as a "
                                        "percentage (e.g. on_time_probability). "
                                        "Defaults to false."
                                    ),
                                },
                            },
                            "required": ["value_path", "label"],
                        },
                    },
                },
                "required": ["heading", "body_template", "claims"],
            },
        },
        "required": ["recommendation_explanations"],
    },
}


SYSTEM_PROMPT = """You are the explanation layer for Sprint Whisperer, a project \
delivery forecasting tool. You will be given a JSON snapshot of facts that have \
ALREADY been computed by deterministic engines (Monte Carlo simulation, risk \
scoring, dependency analysis, recommendation ranking).

Your job is ONLY to explain these facts in clear, PM-friendly language. You must \
follow these rules exactly:

1. You may NEVER state a metric or quantity directly in prose. Every number that \
   represents a measurement (hours, days, percentages, scores) must be expressed \
   as a {claim_N} placeholder, with a corresponding entry in that section's \
   `claims` list whose `value_path` points at the exact field in the snapshot \
   you were given. Entity IDs (e.g. 'B-03', 'WI-041', 'SPR-1') are names, not \
   metrics -- write them directly in prose, do not turn them into claims.
2. You may NEVER invent a value_path that wasn't in the snapshot. If you want to \
   reference something that isn't there, omit that claim rather than guess.
3. If a field is a 0.0-1.0 fraction representing a probability or percentage \
   (check the field description in the snapshot), set as_percentage: true on \
   that claim so it renders correctly (e.g. 0.63 -> "63%", not "0.6%").
4. You may NEVER generate a new recommendation, forecast, or risk score. You are \
   explaining what the engines already produced, not producing new analysis.
5. If project_context is present in the snapshot, write an executive_summary with \
   a single short headline section that states where the project stands right \
   now (current sprint, forecast finish, on-time probability) before any \
   recommendation explanations. If project_context is absent, omit executive_summary.
6. Every recommendation explanation and the scenario explanation (if present) use \
   exactly five standardized sections: why, evidence, benefits, trade_offs, \
   next_step. trade_offs is the only optional one -- omit it (null) if the \
   recommendation has no genuine downside; do not invent one just to fill the slot.
7. You MUST respond using the submit_advisor_explanation tool. Do not respond \
   with plain text.

Write in the voice of a calm, direct project advisor talking to a PM who is \
busy and wants the bottom line first, evidence second."""


def _build_user_message(advisor_input: AdvisorInput) -> str:
    return (
        "Here is the deterministic snapshot to explain:\n\n"
        f"{advisor_input.model_dump_json(indent=2)}"
    )


def _cache_key(advisor_input: AdvisorInput, model: str) -> str:
    """
    Hash of (exact facts shown to the model) + (model version used).

    Including the model version means upgrading advisor_model naturally
    invalidates old cache entries -- you never serve a Sonnet-4.6-era
    narrative once you've moved to a newer model, and A/B testing two
    model versions against the same facts doesn't collide on one key.
    """
    payload = advisor_input.model_dump_json()
    combined = f"{model}::{payload}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


class NarrativeCache(Protocol):
    async def get(self, key: str) -> Optional[Dict[str, Any]]: ...
    async def set(self, key: str, value: Dict[str, Any]) -> None: ...


class InMemoryNarrativeCache:
    """Drop-in default; swap for Redis/session_store-backed cache in prod."""

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        return self._store.get(key)

    async def set(self, key: str, value: Dict[str, Any]) -> None:
        self._store[key] = value


class NarrativeService:
    """
    Calls the LLM to explain an AdvisorInput snapshot, renders the
    result through advisor_contract's resolver, and always returns
    something usable -- degraded or templated on any failure, never
    an exception that could break the response pipeline.
    """

    def __init__(
        self,
        client: MessagesClient,
        settings: Optional[NarrativeSettings] = None,
        cache: Optional[NarrativeCache] = None,
    ) -> None:
        self.client = client
        self.settings = settings or NarrativeSettings()
        self.cache = cache or InMemoryNarrativeCache()

    async def explain(
        self,
        advisor_input: AdvisorInput,
        fallback_text_by_recommendation: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Returns a dict shaped like:
            {
              "status": "ok" | "partial" | "fallback",
              "recommendation_explanations": [ {recommendation_id, sections, fully_resolved}, ... ],
            }

        `fallback_text_by_recommendation` maps recommendation_id -> the
        existing deterministic template description, used if the model
        call fails entirely for that recommendation.
        """
        if not self.settings.advisor_enabled:
            return self._fallback_response(advisor_input, fallback_text_by_recommendation)

        cache_key = _cache_key(advisor_input, self.settings.advisor_model)
        if self.settings.advisor_cache_enabled:
            cached = await self.cache.get(cache_key)
            if cached is not None:
                return cached

        try:
            raw_output = await self._call_model(advisor_input)
            advisor_output = AdvisorOutput.model_validate(raw_output)
        except Exception:
            logger.exception("Advisor model call failed; falling back to templates")
            result = self._fallback_response(advisor_input, fallback_text_by_recommendation)
            return result

        result = self._render(advisor_output, advisor_input, fallback_text_by_recommendation)

        if self.settings.advisor_cache_enabled:
            await self.cache.set(cache_key, result)

        return result

    async def _call_model(self, advisor_input: AdvisorInput) -> Dict[str, Any]:
        response = await self.client.create(
            model=self.settings.advisor_model,
            max_tokens=self.settings.advisor_max_tokens,
            system=SYSTEM_PROMPT,
            tools=[ADVISOR_OUTPUT_TOOL],
            tool_choice={"type": "tool", "name": "submit_advisor_explanation"},
            messages=[{"role": "user", "content": _build_user_message(advisor_input)}],
        )

        for block in response.content:
            if getattr(block, "type", None) == "tool_use":
                return block.input  # already-parsed dict per Anthropic SDK

        raise ValueError("Model did not return a tool_use block")

    def _render(
        self,
        advisor_output: AdvisorOutput,
        advisor_input: AdvisorInput,
        fallback_text_by_recommendation: Dict[str, str],
    ) -> Dict[str, Any]:
        any_degraded = False

        rendered_exec_summary = None
        if advisor_output.executive_summary is not None:
            rendered_exec_summary = render_executive_summary(
                advisor_output.executive_summary, advisor_input
            )
            if not rendered_exec_summary["fully_resolved"]:
                any_degraded = True

        rendered_recs = []
        seen_ids = set()
        for explanation in advisor_output.recommendation_explanations:
            seen_ids.add(explanation.recommendation_id)
            rendered = render_recommendation_explanation(explanation, advisor_input)
            if not rendered["fully_resolved"]:
                any_degraded = True
            rendered_recs.append(rendered)

        # Any recommendation the model skipped or that failed entirely
        # falls back to its existing deterministic description.
        for rec_id, fallback_text in fallback_text_by_recommendation.items():
            if rec_id not in seen_ids:
                rendered_recs.append(
                    {
                        "recommendation_id": rec_id,
                        "sections": [{"kind": "summary", "heading": "Summary", "body": fallback_text}],
                        "fully_resolved": True,
                        "source": "template_fallback",
                    }
                )

        rendered_scenario = None
        if advisor_output.scenario_explanation is not None:
            rendered_scenario = render_scenario_explanation(
                advisor_output.scenario_explanation, advisor_input
            )
            if not rendered_scenario["fully_resolved"]:
                any_degraded = True

        status = AdvisorResponseStatus.PARTIAL if any_degraded else AdvisorResponseStatus.OK
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
        fallback_exec_summary = None
        ctx = advisor_input.project_context
        if ctx is not None:
            # Plain deterministic sentence, no LLM involved -- safe to
            # build directly from already-real numbers.
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
                    "sections": [{"kind": "summary", "heading": "Summary", "body": text}],
                    "fully_resolved": True,
                    "source": "template_fallback",
                }
                for rec_id, text in fallback_text_by_recommendation.items()
            ],
            "scenario_explanation": None,
        }

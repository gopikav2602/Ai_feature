"""
AI Advisor contract.

Design goal (per Sprint Intelligence Workflow doc):
    "The AI NEVER computes metrics. The AI NEVER forecasts.
     The AI NEVER generates recommendations independently.
     It ONLY explains deterministic outputs."

This file makes that boundary structural rather than advisory:

1. AdvisorInput is a closed, read-only snapshot. It contains no engines,
   no ProjectState, nothing callable -- only values and evidence that
   upstream engines already computed. The AI literally cannot reach
   anything it could use to compute a new number.

2. AdvisorOutput cannot contain a bare number written by the model.
   Every numeric claim is a `ClaimRef` -- a pointer into AdvisorInput's
   field paths. The renderer resolves the pointer to the *real* value
   at render time. If the model points at a path that doesn't exist,
   resolution fails and that claim is dropped (or the whole response
   falls back to the deterministic template) -- the model can never
   inject a number that didn't already exist in the deterministic layer.

This means: AI gets creative with phrasing and structure (which evidence
to lead with, how to group trade-offs, tone), but it cannot be the
source of any fact in the final text.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# 1. INPUT CONTRACT -- read-only snapshot of already-computed facts
# ---------------------------------------------------------------------------
# Mirrors the real shapes in app/engines/recommendation_engine/models.py
# and app/engines/simulation_engine.py. We don't pass those objects
# directly (they carry methods / engine references) -- we project them
# into a flat, inert snapshot built specifically for the advisor.


class EvidenceItem(BaseModel):
    """Mirrors SignalEvidence. One fact, already computed upstream."""

    source_engine: str
    metric_name: str
    metric_value: float
    threshold: float
    explanation: str

    model_config = {"frozen": True}


class RecommendationFacts(BaseModel):
    """Projection of Recommendation -- facts only, no behavior."""

    recommendation_id: str
    title: str
    action_type: str
    confidence: str
    priority_score: float
    estimated_hours_recovered: float
    estimated_delay_reduction_days: float
    estimated_risk_reduction: float
    affected_item_ids: List[str] = Field(default_factory=list)
    affected_resource_ids: List[str] = Field(default_factory=list)
    affected_sprint_ids: List[str] = Field(default_factory=list)
    affected_blocker_ids: List[str] = Field(default_factory=list)
    impact_evidence: List[EvidenceItem] = Field(default_factory=list)

    model_config = {"frozen": True}


class ForecastDriverFact(BaseModel):
    """
    Projection of ForecastDriver -- a single ranked, deterministic
    contributor to forecast delay (e.g. "Critical dependency", impact
    in days, plain-English reason). Sourced directly from
    ForecastResult.forecast_drivers, which is already ranked by the
    forecast engine -- this is not re-derived or re-sorted here.
    """

    name: str
    impact_days: float
    reason: str

    model_config = {"frozen": True}


class MetricsFacts(BaseModel):
    """
    Projection of a subset of ProjectMetrics -- deterministic project
    health figures the advisor can reference when explaining *why*
    a forecast or recommendation looks the way it does (e.g. "velocity
    has been unstable" backed by velocity_std_dev, not a vibe).

    Deliberately a curated subset, not a 1:1 dump of ProjectMetrics:
    only fields with a clear, advisor-relevant narrative meaning are
    included. Extend this model (and the builder) if a new field is
    needed -- never let the AI reach ProjectMetrics directly.
    """

    completion_pct: float
    active_blocker_count: int
    blocker_count_by_severity: Dict[str, int]
    actual_avg_velocity: float
    velocity_std_dev: float
    avg_allocation_pct: float
    underutilized_resource_count: int
    dependency_count: int
    critical_path_length: int
    historical_carryover_items: int

    model_config = {"frozen": True}


class ProjectContextFacts(BaseModel):
    """
    Snapshot of overall project state, sourced from ForecastResult /
    MonteCarloResult / the current in-progress Sprint. Lets the advisor
    open with "where things stand" before explaining individual
    recommendations or a scenario -- mirrors the workflow doc's example,
    which leads with "Project is expected to finish 9 days late."

    Field provenance (real upstream models, not invented):
      - current_sprint_name / current_sprint_number  <- Sprint (domain/models.py)
      - completion_percentage                          <- ForecastResult.completion_percentage
      - expected_finish_date / expected_delay_days     <- ForecastResult
      - on_track                                       <- ForecastResult.on_track
      - on_time_probability                            <- MonteCarloResult.on_time_probability
      - on_time_risk_level                             <- MonteCarloResult.on_time_risk_level
      - top_drivers                                    <- ForecastResult.forecast_drivers (already ranked)
    """

    current_sprint_name: str
    current_sprint_number: int
    completion_percentage: float
    target_end_date: str
    expected_finish_date: str
    expected_delay_days: float
    on_track: bool
    on_time_probability: float
    on_time_risk_level: str
    top_drivers: List[ForecastDriverFact] = Field(default_factory=list)

    model_config = {"frozen": True}


class ScenarioFacts(BaseModel):
    """Projection of ScenarioResult -- baseline vs simulated, already run."""

    scenario_id: str
    selected_recommendation_ids: List[str]

    baseline_finish_date: str
    simulated_finish_date: str
    days_saved: float

    baseline_on_time_probability: float
    simulated_on_time_probability: float
    confidence_delta: float

    baseline_risk_score: float
    simulated_risk_score: float
    risk_reduction: float

    # Optional, not defaulted to 0.0: these deltas are only available
    # when the upstream simulation result actually computed them.
    # RecommendationSimulationResult, for example, only carries
    # delta_projected_velocity -- utilization/carryover/blocker deltas
    # are not produced by that path. Rendering them as 0.0 would let
    # the AI claim "no blocker improvement" when the truth is "blocker
    # delta was never computed." None forces the renderer/AI to treat
    # the field as unavailable rather than as a real zero.
    velocity_delta: Optional[float] = None
    utilization_delta: Optional[float] = None
    carryover_delta: Optional[float] = None
    blocker_delta: Optional[float] = None

    overall_improvement_score: float
    simulation_success: bool
    warnings: List[str] = Field(default_factory=list)

    model_config = {"frozen": True}


class AdvisorInput(BaseModel):
    """
    The complete, closed universe of facts the advisor may reference.

    No ProjectState. No engine objects. No callables. Just values.
    Anything not present here is a fact the AI cannot use, by construction.
    """

    project_id: str
    project_context: Optional[ProjectContextFacts] = None
    metrics: Optional[MetricsFacts] = None
    recommendations: List[RecommendationFacts] = Field(default_factory=list)
    scenario: Optional[ScenarioFacts] = None

    model_config = {"frozen": True}

    def get_path(self, path: str) -> Any:
        """
        Resolve a dotted field path against this snapshot, e.g.:
            "scenario.days_saved"
            "recommendations[0].estimated_delay_reduction_days"
            "recommendations[0].impact_evidence[1].metric_value"

        Used by the renderer to verify/resolve a ClaimRef. Raises
        KeyError/IndexError/AttributeError on any invalid path --
        callers MUST catch and treat as "claim invalid, drop it."
        """
        obj: Any = self
        for part in _tokenize_path(path):
            if isinstance(part, int):
                obj = obj[part]
            else:
                obj = getattr(obj, part)
        return obj


def _tokenize_path(path: str) -> List[Any]:
    """'recommendations[0].title' -> ['recommendations', 0, 'title']"""
    tokens: List[Any] = []
    for segment in path.split("."):
        if "[" in segment:
            name, idx = segment[:-1].split("[")
            tokens.append(name)
            tokens.append(int(idx))
        else:
            tokens.append(segment)
    return tokens


# ---------------------------------------------------------------------------
# 2. OUTPUT CONTRACT -- the model can narrate, never invent a number
# ---------------------------------------------------------------------------


class ClaimRef(BaseModel):
    """
    A single factual claim the model wants to make.

    `value_path` MUST point at a real field in the AdvisorInput that was
    given to this call. The model writes the path; your renderer resolves
    it and substitutes the *actual* value. The model never writes the
    number itself, so it cannot hallucinate one.
    """

    value_path: str = Field(
        ..., description="Dotted path into AdvisorInput, e.g. 'scenario.days_saved'"
    )
    label: str = Field(
        ..., description="Short human label for what this value represents, "
        "e.g. 'days saved' -- used if the path fails to resolve and the "
        "claim must be dropped or flagged"
    )
    as_percentage: bool = Field(
        default=False,
        description=(
            "Set true if value_path resolves to a 0.0-1.0 fraction that "
            "should render as a percentage, e.g. on_time_probability=0.63 "
            "-> '63%'. Without this, fractions render as '0.6', which is "
            "wrong for probability/percentage fields. Does not affect "
            "fields already stored as percentages (e.g. scope_growth_percent)."
        ),
    )


class NarrativeSection(BaseModel):
    """
    One section of the advisor's explanation, e.g. 'Evidence',
    'Trade-offs', 'Recommended Next Step' from the workflow doc's
    example output.
    """

    heading: str
    body_template: str = Field(
        ...,
        description=(
            "Prose with placeholders like {claim_0}, {claim_1} referencing "
            "indices into `claims`. No raw numbers should appear in this "
            "string outside of placeholders -- enforced by validator."
        ),
    )
    claims: List[ClaimRef] = Field(default_factory=list)

    @field_validator("body_template")
    @classmethod
    def must_use_placeholders_for_any_digits(cls, v: str) -> str:
        """
        Guardrail: reject standalone numeric quantities written directly
        into prose instead of going through a ClaimRef placeholder.

        Deliberately does NOT flag alphanumeric ID tokens like 'B-03',
        'WI-041', 'SPR-1', 'S4' -- these are entity identifiers the model
        is expected to reference by name (they come from affected_item_ids
        / affected_blocker_ids / affected_sprint_ids, not from a metric).
        A digit only counts as a violation if it forms a standalone
        number with no adjacent letter, e.g. '7 days' or '14%'.
        """
        import re

        without_placeholders = re.sub(r"\{claim_\d+\}", "", v)

        # Standalone number: digits not immediately preceded or followed
        # by a letter (so "B-03" and "WI-041" are skipped, but "7 days"
        # and "14%" are caught). Hyphens between letters and digits
        # (ID-style) are excluded via the negative lookbehind/lookahead.
        bare_number_pattern = re.compile(
            r"(?<![A-Za-z0-9-])\d+(\.\d+)?(?![A-Za-z0-9-])"
        )
        if bare_number_pattern.search(without_placeholders):
            raise ValueError(
                "body_template contains a standalone number outside of a "
                "{claim_N} placeholder. All numeric claims must go through "
                "`claims` -- entity IDs like 'B-03' are fine, bare "
                "quantities like '7 days' are not."
            )
        return v


class SectionKind(str, Enum):
    """
    Standardized explanation sections. Every recommendation explanation
    and the scenario explanation use this same five-part structure, so
    the frontend can render a consistent layout regardless of which
    recommendation or scenario is being explained.
    """

    WHY = "why"
    EVIDENCE = "evidence"
    BENEFITS = "benefits"
    TRADE_OFFS = "trade_offs"
    NEXT_STEP = "next_step"


SECTION_LABELS: Dict[SectionKind, str] = {
    SectionKind.WHY: "Why",
    SectionKind.EVIDENCE: "Evidence",
    SectionKind.BENEFITS: "Benefits",
    SectionKind.TRADE_OFFS: "Trade-offs",
    SectionKind.NEXT_STEP: "Next Step",
}


class AdvisorRecommendationExplanation(BaseModel):
    """
    Why a specific recommendation was generated (workflow doc item 1),
    using the standardized five-section structure. `trade_offs` is
    optional -- some recommendations (e.g. "resolve blocker") have no
    meaningful downside, and the model should not be forced to invent one.
    """

    recommendation_id: str
    why: NarrativeSection
    evidence: NarrativeSection
    benefits: NarrativeSection
    trade_offs: Optional[NarrativeSection] = None
    next_step: NarrativeSection

    def ordered_sections(self) -> List[tuple[SectionKind, Optional[NarrativeSection]]]:
        return [
            (SectionKind.WHY, self.why),
            (SectionKind.EVIDENCE, self.evidence),
            (SectionKind.BENEFITS, self.benefits),
            (SectionKind.TRADE_OFFS, self.trade_offs),
            (SectionKind.NEXT_STEP, self.next_step),
        ]


class AdvisorScenarioExplanation(BaseModel):
    """
    Baseline vs simulated comparison narrative (workflow doc item 6-9),
    using the same standardized five-section structure as recommendation
    explanations for layout consistency.
    """

    scenario_id: str
    why: NarrativeSection
    evidence: NarrativeSection
    benefits: NarrativeSection
    trade_offs: Optional[NarrativeSection] = None
    next_step: NarrativeSection

    def ordered_sections(self) -> List[tuple[SectionKind, Optional[NarrativeSection]]]:
        return [
            (SectionKind.WHY, self.why),
            (SectionKind.EVIDENCE, self.evidence),
            (SectionKind.BENEFITS, self.benefits),
            (SectionKind.TRADE_OFFS, self.trade_offs),
            (SectionKind.NEXT_STEP, self.next_step),
        ]


class ProjectExecutiveSummary(BaseModel):
    """
    Project-level summary shown before any recommendation explanations --
    "where things stand right now," sourced from AdvisorInput.project_context.
    Mirrors the workflow doc's example opening: "Project is expected to
    finish 9 days late."

    Single section, not the full five-part structure -- this is a short
    framing statement, not a recommendation explanation.
    """

    headline: NarrativeSection


class AdvisorResponseStatus(str, Enum):
    OK = "ok"
    PARTIAL = "partial"  # one or more claims failed to resolve and were dropped
    FALLBACK = "fallback"  # resolution failed badly enough to use template text


class AdvisorOutput(BaseModel):
    """
    Top-level response from the advisor call, pre-rendering.

    `status` tells the caller whether every claim resolved cleanly.
    Render-time resolution happens in `render()` below, not here --
    this object is still in "model wrote this, not yet verified" state
    until rendered.
    """

    executive_summary: Optional[ProjectExecutiveSummary] = None
    recommendation_explanations: List[AdvisorRecommendationExplanation] = Field(
        default_factory=list
    )
    scenario_explanation: Optional[AdvisorScenarioExplanation] = None
    status: AdvisorResponseStatus = AdvisorResponseStatus.OK


# ---------------------------------------------------------------------------
# 3. RENDERER -- the only place a number from AdvisorInput reaches the user
# ---------------------------------------------------------------------------


def render_section(section: NarrativeSection, source: AdvisorInput) -> tuple[str, bool]:
    """
    Resolve all ClaimRefs in a section against `source` and substitute
    into body_template. Returns (rendered_text, all_claims_resolved).

    If a claim's path doesn't resolve, OR resolves to None (field exists
    but the upstream engine never computed it -- e.g. ScenarioFacts'
    optional deltas), it's replaced with "Not available" rather than a
    guessed number, and the second return value is False so the caller
    can mark status=PARTIAL. A None value is treated identically to a
    broken path: both mean "the AI cannot make this claim," never "the
    value is zero."
    """
    resolved_ok = True
    values: Dict[str, str] = {}

    for i, claim in enumerate(section.claims):
        try:
            value = source.get_path(claim.value_path)
            if value is None:
                values[f"claim_{i}"] = "Not available"
                resolved_ok = False
            else:
                values[f"claim_{i}"] = _format_value(value, as_percentage=claim.as_percentage)
        except (KeyError, IndexError, AttributeError, ValueError):
            values[f"claim_{i}"] = "Not available"
            resolved_ok = False

    try:
        text = section.body_template.format(**values)
    except (KeyError, IndexError):
        # Template referenced a claim index that doesn't exist in claims[]
        return section.body_template, False

    return text, resolved_ok


def _format_value(value: Any, as_percentage: bool = False) -> str:
    if as_percentage and isinstance(value, (float, int)):
        return f"{value * 100:.0f}"
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


def render_recommendation_explanation(
    explanation: AdvisorRecommendationExplanation,
    source: AdvisorInput,
) -> Dict[str, Any]:
    """
    Renders the standardized Why / Evidence / Benefits / Trade-offs / Next
    Step structure. trade_offs is optional and omitted from output if the
    model didn't provide one.
    """
    rendered_sections = []
    all_ok = True

    for kind, section in explanation.ordered_sections():
        if section is None:
            continue
        text, ok = render_section(section, source)
        all_ok = all_ok and ok
        rendered_sections.append(
            {"kind": kind.value, "heading": SECTION_LABELS[kind], "body": text}
        )

    return {
        "recommendation_id": explanation.recommendation_id,
        "sections": rendered_sections,
        "fully_resolved": all_ok,
    }


def render_scenario_explanation(
    explanation: AdvisorScenarioExplanation,
    source: AdvisorInput,
) -> Dict[str, Any]:
    """Same standardized structure as recommendation explanations, for a scenario."""
    rendered_sections = []
    all_ok = True

    for kind, section in explanation.ordered_sections():
        if section is None:
            continue
        text, ok = render_section(section, source)
        all_ok = all_ok and ok
        rendered_sections.append(
            {"kind": kind.value, "heading": SECTION_LABELS[kind], "body": text}
        )

    return {
        "scenario_id": explanation.scenario_id,
        "sections": rendered_sections,
        "fully_resolved": all_ok,
    }


def render_executive_summary(
    summary: ProjectExecutiveSummary,
    source: AdvisorInput,
) -> Dict[str, Any]:
    """Renders the single project-level headline shown before recommendations."""
    text, ok = render_section(summary.headline, source)
    return {"headline": text, "fully_resolved": ok}

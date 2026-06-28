"""
AdvisorInputBuilder.

Its only responsibility:

    Recommendation
    + RecommendationSimulationResult
    + ForecastResult
    + MonteCarloResult
    + ProjectMetrics
    + RiskResult
    ---------------------------------
    -> AdvisorInput

NOTHING ELSE.

This module performs no computation, no scoring, no forecasting. It is a
pure projection layer: it reads fields that the deterministic engines have
already produced and copies them into the flat, closed AdvisorInput shape
defined in advisor_contract.py. If a value isn't already sitting on one of
the six input objects, this builder cannot produce it -- that's the point.

Why this exists as its own file, rather than building AdvisorInput inline
wherever it's needed: every route or service that wants to call the
NarrativeService needs the *same* projection, built the *same* way, every
time. Centralizing it here means there is exactly one place that defines
"what facts the AI is allowed to see," which is the property the whole
AI Advisor design depends on.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from app.api.models_phase3 import (
    ForecastResult,
    MonteCarloResult,
    RecommendationSimulationResult,
    RiskResult,
)
from app.domain.models import ProjectState, SprintStatus
from app.engines.metrics_engine import ProjectMetrics
from app.engines.recommendation_engine.models import Recommendation

from app.engines.advisor_contract import (
    AdvisorInput,
    EvidenceItem,
    ForecastDriverFact,
    MetricsFacts,
    ProjectContextFacts,
    RecommendationFacts,
    ScenarioFacts,
)


def _current_sprint_name_and_number(project_state: ProjectState) -> tuple[str, int]:
    """
    Mirrors the lookup ForecastEngine already performs internally
    (the in-progress sprint). Re-derives it here rather than computing
    anything new -- this is reading the same fact the forecast engine
    used, not producing a new one.
    """
    for sprint in project_state.sprints:
        status = sprint.status
        is_in_progress = (
            status == SprintStatus.IN_PROGRESS
            or (isinstance(status, str) and status == SprintStatus.IN_PROGRESS.value)
        )
        if is_in_progress:
            return sprint.sprint_name, sprint.sprint_number

    # No sprint currently in progress (e.g. between sprints, or project
    # not yet started) -- fall back to the first not-yet-completed sprint
    # so the advisor still has something concrete to reference.
    for sprint in sorted(project_state.sprints, key=lambda s: s.sprint_number):
        if sprint.status != SprintStatus.COMPLETED:
            return sprint.sprint_name, sprint.sprint_number

    # All sprints completed -- reference the last one.
    last = max(project_state.sprints, key=lambda s: s.sprint_number)
    return last.sprint_name, last.sprint_number


def build_project_context(
    project_state: ProjectState,
    forecast: ForecastResult,
    monte_carlo: MonteCarloResult,
) -> ProjectContextFacts:
    """
    Project ForecastResult + MonteCarloResult + current sprint
    -> ProjectContextFacts.

    top_drivers is a direct copy of forecast.forecast_drivers, already
    ranked by the forecast engine -- this function does not re-sort,
    re-score, or filter them, it only changes the shape from
    ForecastDriver to ForecastDriverFact.
    """
    sprint_name, sprint_number = _current_sprint_name_and_number(project_state)

    return ProjectContextFacts(
        current_sprint_name=sprint_name,
        current_sprint_number=sprint_number,
        completion_percentage=forecast.completion_percentage,
        target_end_date=forecast.target_end_date.isoformat(),
        expected_finish_date=forecast.expected_finish_date.isoformat(),
        expected_delay_days=forecast.expected_delay_days,
        on_track=forecast.on_track,
        on_time_probability=monte_carlo.on_time_probability,
        on_time_risk_level=monte_carlo.on_time_risk_level.value
        if hasattr(monte_carlo.on_time_risk_level, "value")
        else str(monte_carlo.on_time_risk_level),
        top_drivers=[
            ForecastDriverFact(name=d.name, impact_days=d.impact, reason=d.reason)
            for d in forecast.forecast_drivers
        ],
    )


def build_metrics_facts(metrics: ProjectMetrics) -> MetricsFacts:
    """
    Project a curated subset of ProjectMetrics -> MetricsFacts.

    historical_carryover_items intentionally reads
    expected_spillover_items, NOT historical_total_carryover_items --
    both hold the identical value (see the naming clarification in
    ProjectMetrics' own docstring; the latter is the accurately-named
    alias of the former). Either field works; this picks the
    accurately-named one so a future reader of this builder isn't
    misled the way the original field name could mislead.
    """
    return MetricsFacts(
        completion_pct=metrics.completion_pct,
        active_blocker_count=metrics.active_blocker_count,
        blocker_count_by_severity=dict(metrics.blocker_count_by_severity),
        actual_avg_velocity=metrics.actual_avg_velocity,
        velocity_std_dev=metrics.velocity_std_dev,
        avg_allocation_pct=metrics.avg_allocation_pct,
        underutilized_resource_count=metrics.underutilized_resource_count,
        dependency_count=metrics.dependency_count,
        critical_path_length=metrics.critical_path_length,
        historical_carryover_items=metrics.historical_total_carryover_items,
    )


def build_recommendation_facts(recommendation: Recommendation) -> RecommendationFacts:
    """Project a single Recommendation -> RecommendationFacts. 1:1 field copy, no derivation."""
    return RecommendationFacts(
        recommendation_id=recommendation.recommendation_id,
        title=recommendation.title,
        action_type=recommendation.action_type.value,
        confidence=recommendation.confidence.value,
        priority_score=recommendation.priority_score,
        estimated_hours_recovered=recommendation.estimated_hours_recovered,
        estimated_delay_reduction_days=recommendation.estimated_delay_reduction_days,
        estimated_risk_reduction=recommendation.estimated_risk_reduction,
        affected_item_ids=list(recommendation.affected_item_ids),
        affected_resource_ids=list(recommendation.affected_resource_ids),
        affected_sprint_ids=list(recommendation.affected_sprint_ids),
        affected_blocker_ids=list(recommendation.affected_blocker_ids),
        impact_evidence=[
            EvidenceItem(
                source_engine=ev.source_engine,
                metric_name=ev.metric_name,
                metric_value=ev.metric_value,
                threshold=ev.threshold,
                explanation=ev.explanation,
            )
            for ev in recommendation.impact_evidence
        ],
    )


def build_scenario_facts(
    simulation_result: RecommendationSimulationResult,
    forecast: Optional[ForecastResult] = None,
    monte_carlo: Optional[MonteCarloResult] = None,
    risk_result: Optional[RiskResult] = None,
) -> ScenarioFacts:
    """
    Project RecommendationSimulationResult (+ optionally forecast/monte-carlo/risk data)
    into ScenarioFacts.

    RecommendationSimulationResult already carries baseline/after pairs for
    probability, delay, and overall risk; the builder enriches the scenario
    snapshot with finish dates when a forecast result is available, while keeping
    other fields absent rather than inventing them.
    """
    scenario_ids = simulation_result.scenario_recommendation_ids or (
        [simulation_result.recommendation_id] if simulation_result.recommendation_id else []
    )

    baseline_finish_date = ""
    simulated_finish_date = ""
    if forecast is not None:
        baseline_finish_date = forecast.target_end_date.isoformat()
        simulated_finish_date = forecast.expected_finish_date.isoformat()

    warnings: List[str] = []
    if forecast is None:
        warnings.append("Forecast result unavailable for finish-date projection")
    if monte_carlo is None:
        warnings.append("Monte Carlo result unavailable for risk comparison")

    return ScenarioFacts(
        scenario_id=simulation_result.session_id,
        selected_recommendation_ids=scenario_ids,
        baseline_finish_date=baseline_finish_date,
        simulated_finish_date=simulated_finish_date,
        days_saved=simulation_result.delay_reduction_days,
        baseline_on_time_probability=simulation_result.baseline_probability,
        simulated_on_time_probability=simulation_result.after_probability,
        confidence_delta=simulation_result.probability_gain,
        baseline_risk_score=simulation_result.baseline_risk_score,
        simulated_risk_score=simulation_result.after_risk_score,
        risk_reduction=simulation_result.risk_reduction,
        # Pass through as-is: delta_projected_velocity is genuinely
        # Optional on RecommendationSimulationResult. Using `or 0.0` here
        # would collapse "not computed" (None) and "computed as exactly
        # 0.0" into the same value -- exactly the zero-vs-unavailable
        # conflation this field's Optional type exists to prevent.
        velocity_delta=simulation_result.delta_projected_velocity,
        # Not produced by RecommendationSimulationResult at all -- left
        # as None (unavailable), never defaulted to 0.0.
        utilization_delta=None,
        carryover_delta=None,
        blocker_delta=None,
        overall_improvement_score=simulation_result.probability_gain * 100.0,
        simulation_success=simulation_result.is_positive_impact,
        warnings=warnings,
    )


class AdvisorInputBuilder:
    """
    Builds AdvisorInput from already-computed engine outputs.

    Stateless -- holds no engine references, no ProjectState mutation,
    no caching.

    Public API is split into two intent-specific methods rather than one
    do-everything `build()`:

      - build_recommendation_input(): project context + ranked
        recommendations, for explaining "here's what's wrong and what
        we suggest" (GET /recommendations style requests).
      - build_simulation_input(): a single recommendation + its
        simulation result, for explaining "here's what changed after
        applying this" (POST /recommendations/simulate style requests).

    Both delegate to the same private _build(), so there is exactly one
    place that actually assembles an AdvisorInput -- the split is about
    giving callers a narrower, intent-matched signature, not about
    duplicating assembly logic.
    """

    def build_recommendation_input(
        self,
        project_id: str,
        project_state: ProjectState,
        forecast: ForecastResult,
        monte_carlo: MonteCarloResult,
        recommendations: List[Recommendation],
        metrics: Optional[ProjectMetrics] = None,
    ) -> AdvisorInput:
        """Project context + ranked recommendations -- no scenario/simulation data."""
        return self._build(
            project_id=project_id,
            project_state=project_state,
            forecast=forecast,
            monte_carlo=monte_carlo,
            metrics=metrics,
            recommendations=recommendations,
        )

    def build_simulation_input(
        self,
        project_id: str,
        recommendation: Recommendation,
        simulation_result: RecommendationSimulationResult,
        risk: Optional[RiskResult] = None,
        project_state: Optional[ProjectState] = None,
        forecast: Optional[ForecastResult] = None,
        monte_carlo: Optional[MonteCarloResult] = None,
        metrics: Optional[ProjectMetrics] = None,
    ) -> AdvisorInput:
        """
        A single recommendation + its simulation result -- for explaining
        the before/after of applying one recommendation. project_state/
        forecast/monte_carlo are optional here since a simulate-only call
        may not have re-run the full forecast; pass them if available to
        also get an updated project_context/executive summary alongside
        the scenario explanation.
        """
        return self._build(
            project_id=project_id,
            project_state=project_state,
            forecast=forecast,
            monte_carlo=monte_carlo,
            metrics=metrics,
            risk=risk,
            recommendations=[recommendation],
            simulation_result=simulation_result,
        )

    def _build(
        self,
        project_id: str,
        project_state: Optional[ProjectState] = None,
        forecast: Optional[ForecastResult] = None,
        monte_carlo: Optional[MonteCarloResult] = None,
        metrics: Optional[ProjectMetrics] = None,
        risk: Optional[RiskResult] = None,
        recommendations: Optional[List[Recommendation]] = None,
        simulation_result: Optional[RecommendationSimulationResult] = None,
    ) -> AdvisorInput:
        """
        Shared assembly logic. Not part of the public API -- callers use
        build_recommendation_input() or build_simulation_input() above.
        Anything omitted here is simply absent from the resulting
        AdvisorInput (and therefore unavailable to the AI), not
        backfilled or guessed.
        """
        project_context = None
        if project_state is not None and forecast is not None and monte_carlo is not None:
            project_context = build_project_context(project_state, forecast, monte_carlo)

        metrics_facts = build_metrics_facts(metrics) if metrics is not None else None

        recommendation_facts = [
            build_recommendation_facts(rec) for rec in (recommendations or [])
        ]

        scenario_facts = None
        if simulation_result is not None:
            scenario_facts = build_scenario_facts(
                simulation_result,
                forecast=forecast,
                monte_carlo=monte_carlo,
                risk_result=risk,
            )

        return AdvisorInput(
            project_id=project_id,
            project_context=project_context,
            metrics=metrics_facts,
            recommendations=recommendation_facts,
            scenario=scenario_facts,
        )

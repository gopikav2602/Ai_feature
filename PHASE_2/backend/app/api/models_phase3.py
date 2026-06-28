"""API models for Phase 3 (Forecasting)
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class ForecastDelayBreakdown(BaseModel):
    """
    Additive decomposition of `expected_delay_days`.

    All components use the same `projected_velocity` basis as the forecast,
    so these fields sum exactly to `expected_delay_days`.

    expected_delay_days = days_elapsed + remaining_days_total - planned_window_days
    where remaining_days_total = adjusted_remaining / projected_velocity * sprint_days
    """

    planned_window_days: float = Field(
        ...,
        description="Planned project duration in days (target_end_date - project_start)",
    )
    days_elapsed: float = Field(
        ..., description="Schedule days already consumed by completed and in-progress sprints"
    )
    remaining_days_total: float = Field(
        ..., description="Forecasted remaining days = adjusted_remaining / projected_velocity * sprint_days"
    )
    # Additive breakdown of remaining_days_total
    remaining_days_base_work: float = Field(
        ..., description="Portion of delay driven by raw remaining effort at base velocity"
    )
    remaining_days_spillover: float = Field(
        ..., description="Portion of delay driven by spillover schedule impact at projected velocity"
    )
    remaining_days_blocker_loss: float = Field(
        ...,
        description=(
            "Extra days caused by blocker-reduced velocity: equivalent days compared against base velocity"
        ),
    )
    expected_delay_days: float = Field(
        ...,
        description=(
            "Days late vs target (mirrors ForecastResult.expected_delay_days). "
            "= days_elapsed + remaining_days_total - planned_window_days"
        ),
    )


class ForecastScheduleDiagnostics(BaseModel):
    """
    Diagnostic schedule components computed using `base_velocity` (not `projected_velocity`).
    These are driver magnitudes for human explanation and are NOT additive to
    `expected_delay_days`.
    """

    is_additive: bool = Field(
        False,
        description="Always False — these are diagnostic values, not an additive decomposition",
    )
    base_schedule_days: float = Field(
        ..., description="Days to complete raw remaining effort at base (unpenalised) velocity"
    )
    spillover_days: float = Field(..., description="Extra days from spillover penalty at base velocity")
    blocker_days: float = Field(..., description="Extra days from blocker velocity loss (projected vs base)")
    critical_path_days: float = Field(..., description="Extra days from critical path serialisation beyond remaining effort")
    diagnostic_total_days: float = Field(..., description="Sum of above components (does not equal expected_delay_days)")
    velocity_floor_saturated_by_blockers: Optional[bool] = Field(
        False,
        description="True when blockers reduce velocity to the floor value used by the forecast",
    )
    spillover_message: Optional[str] = Field(
        "",
        description="Narrative explanation of spillover impact on the forecast",
    )


class ForecastEffortBreakdown(BaseModel):
    """Explainable breakdown of forecast effort components."""

    raw_remaining_effort_hours: float = Field(..., description="Remaining effort without spillover or critical path uplift")
    critical_path_remaining_hours: float = Field(..., description="Remaining critical path effort used by the forecast")
    spillover_penalty_hours: float = Field(..., description="Equivalent penalty hours from predicted spillover items used for schedule delay calculation")
    blocker_penalty_hours: float = Field(..., description="Effective velocity penalty converted to equivalent effort hours")
    forecast_adjusted_effort_hours: float = Field(..., description="Adjusted effort used by the forecast calculation (critical path uplift only)")


class ForecastConfidence(BaseModel):
    """Deterministic forecast confidence derived from measurable historical indicators."""

    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Deterministic confidence score from historical predictability signals")
    confidence_level: str = Field(..., description="HIGH, MEDIUM, or LOW")
    confidence_reason: str = Field(..., description="Short human-readable reason for the confidence level")
    confidence_inputs: Dict[str, float] = Field(default_factory=dict, description="Historical metrics used to calculate confidence")


class ForecastDriver(BaseModel):
    """A ranked deterministic contributor to forecast delay."""

    name: str = Field(..., description="Contributor name")
    impact: float = Field(..., description="Impact in forecast days")
    reason: str = Field(..., description="Deterministic reason for the impact")
    supporting_metrics: Dict[str, float] = Field(default_factory=dict, description="Metrics that support this driver")


class ForecastEvidence(BaseModel):
    """Structured evidence used to produce the deterministic forecast."""

    name: str = Field(..., description="Evidence name")
    value: Any = Field(..., description="Evidence value")
    unit: str = Field(..., description="Unit of the evidence value")
    source: str = Field(..., description="Source engine or metric set")


class ForecastAssumptions(BaseModel):
    """Machine-readable assumptions that govern the deterministic forecast."""

    velocity_calculation_method: str = Field(..., description="Formula used to derive projected velocity")
    blocker_adjustment_method: str = Field(..., description="Method used to model blocker impact on velocity")
    spillover_adjustment_method: str = Field(..., description="Method used to model spillover impact on throughput")
    critical_path_handling: str = Field(..., description="Method used to incorporate dependency sequencing")
    timeline_anchoring: str = Field(..., description="Method used to anchor the forecast to schedule dates")
    capacity_assumptions: Dict[str, float] = Field(default_factory=dict, description="Capacity-related assumption values")


class ForecastExplanation(BaseModel):
    """Structured explanation payload for downstream UI or AI layers."""

    summary: str = Field(..., description="Short summary of the forecast outcome")
    primary_driver: str = Field(..., description="Name of the largest forecast driver")
    driver_names: List[str] = Field(default_factory=list, description="Ordered driver names")
    confidence_note: str = Field(..., description="Confidence explanation derived from deterministic metrics")
    delay_signal: str = Field(..., description="Whether the project is projected to be early, on track, or late")


class ForecastResult(BaseModel):
    """Deterministic single-point forecast result."""

    target_end_date: datetime = Field(..., description="Project target completion date")
    expected_finish_date: datetime = Field(..., description="Forecasted project completion date")
    expected_delay_days: float = Field(..., description="Days between expected finish and target end date (negative = early, positive = late)")
    remaining_effort_hours: float = Field(..., description="Remaining work to complete (hours)")
    completion_percentage: float = Field(..., ge=0.0, le=1.0, description="Project completion percentage (0.0-1.0)")
    projected_velocity: float = Field(..., description="Projected velocity in hours per sprint")
    on_track: bool = Field(..., description="True if expected_finish_date <= target_end_date, false otherwise")
    raw_remaining_effort_hours: float = Field(..., description="Remaining effort before forecast adjustments")
    critical_path_remaining_hours: float = Field(..., description="Remaining critical-path effort used by the forecast")
    predicted_spillover_items: float = Field(..., description="Expected number of spillover items predicted across remaining sprints")
    spillover_delay_days: float = Field(..., description="Schedule impact of predicted spillover items in days")
    spillover_penalty_hours: float = Field(..., description="Equivalent hours from predicted spillover items used for schedule delay calculation")
    blocker_penalty_hours: float = Field(..., description="Velocity penalty hours due to blockers")
    forecast_adjusted_effort_hours: float = Field(..., description="Adjusted effort used for the forecast calculation")
    scope_growth_hours: float = Field(..., description="Total additional effort hours added since baseline scope")
    scope_growth_percent: float = Field(..., description="Scope growth as a percentage of original project estimate hours")
    scope_impact_days: float = Field(..., description="Estimated days added by scope growth using projected velocity per day")
    scope_growth_message: str = Field(..., description="Narrative explaining the scope growth impact on the forecast")
    delay_breakdown: ForecastDelayBreakdown = Field(
        ...,
        description=(
            "Additive decomposition of expected_delay_days. "
            "days_elapsed + remaining_days_total - planned_window_days == expected_delay_days"
        ),
    )
    schedule_diagnostics: ForecastScheduleDiagnostics = Field(
        ...,
        description=(
            "Diagnostic driver magnitudes computed at base velocity. "
            "Not additive — use delay_breakdown for the exact decomposition."
        ),
    )
    effort_breakdown: ForecastEffortBreakdown = Field(..., description="Structured breakdown of forecast effort components")
    confidence: ForecastConfidence = Field(..., description="Deterministic confidence score and supporting inputs")
    forecast_drivers: List[ForecastDriver] = Field(default_factory=list, description="Ranked deterministic forecast contributors")
    forecast_evidence: List[ForecastEvidence] = Field(default_factory=list, description="Structured evidence used to create the forecast")
    forecast_assumptions: ForecastAssumptions = Field(..., description="Machine-readable assumptions used by the forecast")
    forecast_explanation: ForecastExplanation = Field(..., description="Structured forecast explanation for downstream UI or AI consumers")
    forecast_vs_montecarlo_note: str = Field(
        ...,
        description=(
            "Explains why the deterministic delay and Monte Carlo "
            "on-time probability can appear contradictory"
        ),
    )


class ForecastResponse(BaseModel):
    session_id: str
    project_name: str
    forecast: ForecastResult


class OnTimeRisk(str, Enum):
    """Risk level based on on-time delivery probability."""
    LOW = "LOW"              # >80% probability of on-time delivery
    MEDIUM = "MEDIUM"        # 60-79% probability
    HIGH = "HIGH"            # 40-59% probability
    CRITICAL = "CRITICAL"    # <40% probability


class MonteCarloStatistics(BaseModel):
    """Statistical distribution of simulation results."""

    mean_finish_date: datetime = Field(..., description="Mean expected finish date across all simulations")
    median_finish_date: datetime = Field(..., description="Median expected finish date")
    percentile_10: datetime = Field(..., description="10th percentile (optimistic scenario)")
    percentile_25: datetime = Field(..., description="25th percentile")
    percentile_50: datetime = Field(..., description="50th percentile (median)")
    percentile_75: datetime = Field(..., description="75th percentile")
    percentile_80: datetime = Field(..., description="80th percentile (for analysis)")
    percentile_90: datetime = Field(..., description="90th percentile (pessimistic scenario)")
    percentile_95: datetime = Field(..., description="95th percentile (extreme pessimistic)")
    
    mean_delay_days: float = Field(..., description="Mean delay vs. target end date (days)")
    median_delay_days: float = Field(..., description="Median delay vs. target end date (days)")


class MonteCarloResult(BaseModel):
    """Monte Carlo simulation result with probability distribution."""

    target_end_date: datetime = Field(..., description="Project target completion date (constant across all simulations)")
    simulation_count: int = Field(..., description="Number of simulations performed", ge=1)
    
    # Statistics
    statistics: MonteCarloStatistics
    
    # On-time delivery probability
    on_time_probability: float = Field(..., description="Probability of finishing on or before target_end_date (0.0-1.0)", ge=0.0, le=1.0)
    on_time_risk_level: OnTimeRisk = Field(..., description="Risk rating: LOW (>80%), MEDIUM (60-79%), HIGH (40-59%), CRITICAL (<40%)")
    
    # Counts
    simulations_on_time: int = Field(..., description="Number of simulations finishing on or before target_end_date")
    simulations_late: int = Field(..., description="Number of simulations finishing after target_end_date")
    
    # Additional context
    most_likely_finish_date: datetime = Field(..., description="Median finish date (most likely outcome)")
    best_case_finish_date: datetime = Field(..., description="10th percentile (best case)")
    p80_finish_date: datetime = Field(..., description="80th percentile (80% of outcomes complete by this date)")
    p90_finish_date: datetime = Field(..., description="90th percentile (90% of outcomes complete by this date)")
    p95_finish_date: datetime = Field(..., description="95th percentile (95% of outcomes complete by this date)")


class MonteCarloResponse(BaseModel):
    """API response for Monte Carlo analysis."""
    session_id: str
    project_name: str
    monte_carlo: MonteCarloResult


# ──────────────────────────────────────────────────────────────────────────────
# PHASE 3.3 RISK ENGINE MODELS
# ──────────────────────────────────────────────────────────────────────────────


class RiskLevel(str, Enum):
    """Risk level classification (0-100 scale)."""
    LOW = "LOW"              # 0-20
    MODERATE = "MODERATE"    # 21-40
    HIGH = "HIGH"            # 41-60
    VERY_HIGH = "VERY_HIGH"  # 61-80
    CRITICAL = "CRITICAL"    # 81-100


class RiskDriver(BaseModel):
    """Single risk driver with explanation."""
    
    category: str = Field(
        ...,
        description="Risk category: SCHEDULE, DEPENDENCY, RESOURCE, SCOPE, or BLOCKER"
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Risk contribution score (0-100)"
    )
    title: str = Field(..., description="Short title for risk driver")
    description: str = Field(..., description="Detailed explanation of the risk")
    recommendation_hint: str = Field(
        ...,
        description="Actionable recommendation to mitigate this risk"
    )


class SprintRisk(BaseModel):
    """Risk analysis at sprint level."""
    
    sprint_id: int = Field(..., description="Sprint number")
    risk_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Sprint-level risk score (0-100)"
    )
    risk_level: RiskLevel = Field(..., description="Risk level classification")
    blocked_items: int = Field(..., ge=0, description="Number of blocked items in sprint")
    spillover_items: int = Field(..., ge=0, description="Predicted spillover items from sprint")
    overload_pct: float = Field(
        ...,
        ge=0.0,
        le=300.0,
        description="Sprint overload percentage (planned effort / capacity)"
    )
    dependency_count: int = Field(..., ge=0, description="Number of dependencies in sprint")


class RiskExplanation(BaseModel):
    """Explainable breakdown of a risk score."""
    
    score: float = Field(..., ge=0.0, le=100.0, description="Risk score")
    reasons: List[str] = Field(default_factory=list, description="Human-readable reasons for the score")
    drivers: List[RiskDriver] = Field(
        default_factory=list,
        description="Contributing risk drivers"
    )


class RiskResult(BaseModel):
    """Comprehensive risk analysis result."""
    
    # Overall project risk
    overall_risk_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Overall project risk score (0-100)"
    )
    overall_risk_level: RiskLevel = Field(..., description="Overall risk classification")
    
    # Sub-score explanations
    schedule_risk: RiskExplanation = Field(
        ...,
        description="Schedule risk breakdown with reasons"
    )
    dependency_risk: RiskExplanation = Field(
        ...,
        description="Dependency risk breakdown with reasons"
    )
    resource_risk: RiskExplanation = Field(
        ...,
        description="Resource risk breakdown with reasons"
    )
    scope_risk: RiskExplanation = Field(
        ...,
        description="Scope risk breakdown with reasons"
    )
    
    # Top risk drivers
    top_risk_drivers: List[RiskDriver] = Field(
        max_items=10,
        description="Top 10 risk drivers, sorted by risk contribution (descending)"
    )
    
    # Sprint-level analysis
    sprint_risks: List[SprintRisk] = Field(
        default_factory=list,
        description="Per-sprint risk analysis"
    )
    
    # Scoring formula documentation
    weighting_formula: str = Field(
        default="overall = 0.40 * schedule + 0.25 * dependency + 0.20 * resource + 0.15 * scope",
        description="Weighted aggregation formula used to calculate overall_risk_score"
    )
    risk_vs_montecarlo_note: str = Field(
        default="",
        description=(
            "Explains why overall risk level and Monte Carlo "
            "on-time probability can appear contradictory"
        ),
    )
    blocker_risk_concentration: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "Fraction of overall_risk_score attributable to active blocker root cause "
            "(range 0.0-1.0). Values above 0.60 indicate the score is dominated by a single "
            "factor. Informational only -- does not change the score."
        ),
    )


class RiskResponse(BaseModel):
    """API response for risk analysis."""
    
    session_id: str = Field(..., description="Session ID")
    project_name: str = Field(..., description="Project name")
    risk_analysis: RiskResult = Field(..., description="Risk analysis result")


class RecommendationType(str, Enum):
    RESOLVE_BLOCKER = "Resolve Blocker"
    ADD_RESOURCE = "Add Resource"
    REASSIGN_WORK = "Reassign Work"
    REDUCE_ITEM_SCOPE = "Reduce Item Scope"
    PARALLELIZE_TASKS = "Parallelize Tasks"
    MOVE_BLOCKER_ITEMS = "Move Blocked Items Forward"
    SPLIT_TASK = "Split Task"
    CRITICAL_PATH_OPTIMIZATION = "Critical Path Optimization"


class RecommendationSummary(BaseModel):
    recommendation_id: str = Field(..., description="Unique recommendation identifier")
    type: RecommendationType = Field(..., description="Recommendation type")
    action: str = Field(..., description="Action text for the recommendation")
    target_ids: List[str] = Field(default_factory=list, description="Target entity IDs")
    details: Dict[str, Any] = Field(default_factory=dict, description="Structured recommendation details")
    reason: str = Field(..., description="Why this recommendation was generated")
    implementation_effort: str = Field(..., description="Estimated implementation effort")
    confidence: str = Field(..., description="Confidence level")
    priority_score: float = Field(..., ge=0.0, le=100.0, description="Recommendation effectiveness score")
    baseline_probability: float = Field(..., ge=0.0, le=1.0, description="Baseline on-time probability")
    after_probability: float = Field(..., ge=0.0, le=1.0, description="On-time probability after applying recommendation")
    expected_probability_gain: float = Field(..., description="Probability gain from recommendation")
    baseline_delay_days: float = Field(..., description="Baseline expected delay in days")
    after_delay_days: float = Field(..., description="Expected delay after recommendation")
    expected_delay_gain_days: float = Field(..., description="Delay reduction in days")
    baseline_risk_score: float = Field(..., description="Baseline overall risk score")
    after_risk_score: float = Field(..., description="Overall risk score after recommendation")
    expected_risk_reduction: float = Field(..., description="Risk score reduction")
    impact_level: str = Field(..., description="High/Medium/Low impact level for the recommendation")
    impact_confidence: str = Field(..., description="High/Medium/Low impact confidence relative to Monte Carlo noise")
    impact_classification: str = Field(..., description="Impact classification such as Positive Impact, Negative Impact, or Negligible Impact")
    business_impact: str = Field(..., description="Business impact summary for the recommendation")
    impact_summary: str = Field(..., description="Summary of the recommendation's expected impact")
    category: Optional[str] = Field(None, description="Category of the blocker if applicable")
    recommended_actions: List[str] = Field(default_factory=list, description="Category-aware recommended actions")


class RecommendationSimulationRequest(BaseModel):
    recommendation_id: str = Field(..., description="Recommendation ID to simulate")


class RecommendationScenarioRequest(BaseModel):
    recommendation_ids: List[str] = Field(..., description="List of recommendation IDs to simulate as a scenario")


class ScopeChangeRequest(BaseModel):
    item_ids: List[str] = Field(..., min_items=1, description="Work item IDs to descoped")
    reason: Optional[str] = Field(None, description="Reason for the scope change")


class RecommendationSimulationResult(BaseModel):
    session_id: str = Field(..., description="Session ID")
    project_name: str = Field(..., description="Project name")
    recommendation_id: Optional[str] = Field(None, description="Recommendation ID if single recommendation simulated")
    baseline_probability: float = Field(..., ge=0.0, le=1.0)
    after_probability: float = Field(..., ge=0.0, le=1.0)
    probability_gain: float = Field(..., description="Gain in on-time probability")
    baseline_delay_days: float = Field(..., description="Baseline delay days")
    after_delay_days: float = Field(..., description="Delay days after simulation")
    delay_reduction_days: float = Field(..., description="Delay reduction in days")
    baseline_risk_score: float = Field(..., description="Baseline overall risk score")
    after_risk_score: float = Field(..., description="Overall risk score after simulation")
    risk_reduction: float = Field(..., description="Risk score reduction")
    baseline_schedule_risk: Optional[float] = Field(None, description="Baseline schedule risk score")
    after_schedule_risk: Optional[float] = Field(None, description="Schedule risk score after simulation")
    baseline_resource_risk: Optional[float] = Field(None, description="Baseline resource risk score")
    after_resource_risk: Optional[float] = Field(None, description="Resource risk score after simulation")
    delta_spillover_risk: Optional[float] = Field(None, description="Change in total predicted spillover items (baseline - after)")
    delta_projected_velocity: Optional[float] = Field(None, description="Change in projected velocity (hours per sprint): after - baseline")
    seed_used: int = Field(..., description="Monte Carlo seed used for reproducibility")
    is_positive_impact: bool = Field(..., description="True if recommendation improves at least one key metric")
    summary: str = Field(..., description="Human-readable summary of simulation result")
    scenario_recommendation_ids: Optional[List[str]] = Field(None, description="List of recommendation IDs simulated")


class AdvisorExplanation(BaseModel):
    status: str = Field(..., description="AI advisor explanation status: ok, partial, or fallback")
    executive_summary: Optional[Dict[str, Any]] = Field(
        None,
        description="Project-level executive summary produced by the AI advisor",
    )
    recommendation_explanations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Structured recommendation explanations produced by the AI advisor",
    )
    scenario_explanation: Optional[Dict[str, Any]] = Field(
        None,
        description="Structured scenario explanation produced by the AI advisor",
    )


class RecommendationResponse(BaseModel):
    session_id: str = Field(..., description="Session ID")
    project_name: str = Field(..., description="Project name")
    recommendations: List[RecommendationSummary] = Field(default_factory=list, description="Ranked recommendation list")
    advisor_explanation: Optional[AdvisorExplanation] = Field(
        None,
        description="AI advisor narrative payload for the request",
    )


class RecommendationSimulationResponse(BaseModel):
    session_id: str = Field(..., description="Session ID")
    project_name: str = Field(..., description="Project name")
    simulation_result: RecommendationSimulationResult = Field(..., description="Simulation result")
    advisor_explanation: Optional[AdvisorExplanation] = Field(
        None,
        description="AI advisor narrative payload for the simulation result",
    )


class ScopeChangeResponse(BaseModel):
    session_id: str = Field(..., description="Session ID")
    project_name: str = Field(..., description="Project name")
    dry_run: bool = Field(False, description="Whether this was a preview (dry_run=true) or actual change (dry_run=false)")
    descoped_item_ids: List[str] = Field(default_factory=list, description="Work items removed from scope")
    changed_item_count: int = Field(..., ge=0, description="Number of work items updated")
    updated_remaining_effort_hours: float = Field(..., ge=0.0, description="Remaining effort after scope change")
    forecast: ForecastResult = Field(..., description="Updated deterministic forecast")
    risk_analysis: RiskResult = Field(..., description="Updated risk analysis")

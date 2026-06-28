from datetime import datetime

from app.api.models_phase3 import (
    ForecastResult,
    MonteCarloResult,
    OnTimeRisk,
    RecommendationSimulationResult,
    RiskResult,
)
from app.domain.models import (
    Blocker,
    BlockerCategory,
    BlockerSeverity,
    BlockerStatus,
    Dependency,
    DependencyType,
    ProjectInfo,
    ProjectState,
    Resource,
    SkillLevel,
    Sprint,
    SprintActual,
    SprintStatus,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
    Priority,
)
from app.engines.advisor_input_builder import AdvisorInputBuilder
from app.engines.metrics_engine import ProjectMetrics
from app.engines.recommendation_engine.models import (
    ConfidenceLevel,
    Recommendation,
    RecommendationAction,
)


def _build_state() -> ProjectState:
    start = datetime(2025, 1, 1)
    target = datetime(2025, 3, 31)
    sprint = Sprint(
        sprint_id="SPR-1",
        sprint_name="Sprint 1",
        sprint_number=1,
        start_date=start,
        end_date=datetime(2025, 1, 14),
        working_days=10,
        sprint_goal="Build",
        status=SprintStatus.IN_PROGRESS,
        planned_velocity_hrs=100.0,
    )
    resource = Resource(
        resource_id="R-1",
        name="Alex",
        role="Engineer",
        primary_skill="Backend",
        secondary_skill=None,
        skill_level=SkillLevel.MID,
        allocation_pct=0.8,
        availability_pct=0.9,
        daily_capacity_hrs=8.0,
    )
    work_item = WorkItem(
        item_id="WI-1",
        title="Implement feature",
        work_type=WorkItemType.STORY,
        assigned_sprint="SPR-1",
        original_sprint="SPR-1",
        assigned_resource="R-1",
        required_skill="Backend",
        priority=Priority.HIGH,
        estimated_effort_hrs=40.0,
        current_estimate_hrs=40.0,
        actual_effort_hrs=10.0,
        remaining_effort_hrs=30.0,
        progress_pct=0.25,
        status=WorkItemStatus.IN_PROGRESS,
    )
    blocker = Blocker(
        blocker_id="B-1",
        related_item_id="WI-1",
        impacted_item_ids=["WI-1"],
        description="Dependency pending",
        severity=BlockerSeverity.HIGH,
        status=BlockerStatus.OPEN,
        owner="Alex",
        raised_date=start,
        target_resolution_date=None,
        actual_resolution_date=None,
        category=BlockerCategory.OTHER,
    )
    dependency = Dependency(
        dependency_id="D-1",
        predecessor_item_id="WI-1",
        successor_item_id="WI-2",
        dependency_type=DependencyType.FINISH_TO_START,
        lag_days=2,
    )
    actual = SprintActual(
        sprint_id="SPR-1",
        sprint_number=1,
        planned_effort_hrs=100.0,
        actual_effort_hrs=80.0,
        variance_hrs=20.0,
        tasks_planned=5,
        tasks_completed=4,
        completion_rate=0.8,
        carryover_count=1,
    )
    return ProjectState(
        project_id="P-1",
        project_info=ProjectInfo(
            project_name="Demo",
            sponsor="Ops",
            business_unit="Engineering",
            project_manager="Pat",
            start_date=start,
            release_date=None,
            target_end_date=target,
            sprint_duration_days=14,
            methodology="Agile",
            customer="Contoso",
            status="Active",
        ),
        team=[resource],
        sprints=[sprint],
        work_items=[work_item, WorkItem(
            item_id="WI-2",
            title="Second item",
            work_type=WorkItemType.STORY,
            assigned_sprint="SPR-1",
            original_sprint="SPR-1",
            assigned_resource="R-1",
            required_skill="Backend",
            priority=Priority.MEDIUM,
            estimated_effort_hrs=20.0,
            current_estimate_hrs=20.0,
            actual_effort_hrs=0.0,
            remaining_effort_hrs=20.0,
            progress_pct=0.0,
            status=WorkItemStatus.NOT_STARTED,
        )],
        dependencies=[dependency],
        blockers=[blocker],
        actuals=[actual],
    )


def _build_metrics() -> ProjectMetrics:
    return ProjectMetrics.model_construct(
        total_items=2,
        completed_items=1,
        in_progress_items=1,
        blocked_items=1,
        not_started_items=1,
        completion_pct=0.5,
        total_effort_hours=60.0,
        remaining_effort_hours=30.0,
        completed_effort_hours=30.0,
        average_item_effort=30.0,
        planned_total_velocity=100.0,
        actual_avg_velocity=80.0,
        velocity_variance=20.0,
        velocity_std_dev=4.47,
        team_size=1,
        avg_allocation_pct=0.8,
        avg_availability_pct=0.9,
        underutilized_resource_count=0,
        blocker_count_by_severity={"HIGH": 1},
        active_blocker_count=1,
        estimated_blocker_velocity_impact=0.2,
        project_start_date=datetime(2025, 1, 1),
        project_end_date=datetime(2025, 3, 31),
        current_sprint_number=1,
        completed_sprints=0,
        dependency_count=1,
        critical_path_length=2,
        expected_spillover_items=1,
        historical_total_carryover_items=1,
        historical_carryover_rate=0.5,
        executive_metrics=None,
        work_metrics=None,
        sprint_metrics=[],
        historical_metrics=None,
        velocity_metrics=None,
        resource_metrics=None,
        blocker_metrics=None,
        dependency_metrics=None,
        planning_metrics=None,
        quality_metrics=None,
        risk_input_metrics=None,
        forecast_input_metrics=None,
        recommendation_input_metrics=None,
    )


def _build_forecast() -> ForecastResult:
    return ForecastResult.model_construct(
        target_end_date=datetime(2025, 3, 31),
        expected_finish_date=datetime(2025, 4, 14),
        expected_delay_days=14.0,
        remaining_effort_hours=30.0,
        completion_percentage=0.5,
        projected_velocity=80.0,
        on_track=False,
        raw_remaining_effort_hours=30.0,
        critical_path_remaining_hours=20.0,
        predicted_spillover_items=1.0,
        spillover_delay_days=2.0,
        spillover_penalty_hours=20.0,
        blocker_penalty_hours=10.0,
        forecast_adjusted_effort_hours=30.0,
        scope_growth_hours=0.0,
        scope_growth_percent=0.0,
        scope_impact_days=0.0,
        scope_growth_message="",
        delay_breakdown=None,
        schedule_diagnostics=None,
        effort_breakdown=None,
        confidence=None,
        forecast_drivers=[],
        forecast_evidence=[],
        forecast_assumptions=None,
        forecast_explanation=None,
        forecast_vs_montecarlo_note="",
    )


def _build_monte_carlo() -> MonteCarloResult:
    return MonteCarloResult.model_construct(
        target_end_date=datetime(2025, 3, 31),
        simulation_count=100,
        statistics=None,
        on_time_probability=0.42,
        on_time_risk_level=OnTimeRisk.HIGH,
        simulations_on_time=42,
        simulations_late=58,
        most_likely_finish_date=datetime(2025, 4, 1),
        best_case_finish_date=datetime(2025, 3, 20),
        p80_finish_date=datetime(2025, 4, 8),
        p90_finish_date=datetime(2025, 4, 12),
        p95_finish_date=datetime(2025, 4, 15),
    )


def _build_recommendation() -> Recommendation:
    return Recommendation(
        recommendation_id="REC-1",
        title="Resolve blocker",
        description="Resolve the blocker",
        action_type=RecommendationAction.RESOLVE_BLOCKER,
        priority_score=91.0,
        confidence=ConfidenceLevel.HIGH,
        estimated_hours_recovered=12.0,
        estimated_delay_reduction_days=3.0,
        estimated_risk_reduction=12.0,
        affected_item_ids=["WI-1"],
        affected_resource_ids=["R-1"],
        affected_sprint_ids=["SPR-1"],
        affected_blocker_ids=["B-1"],
        root_cause_signal_id="SIG-1",
        impact_evidence=[],
    )


def test_advisor_builder_projects_current_engine_outputs() -> None:
    state = _build_state()
    builder = AdvisorInputBuilder()

    advisor_input = builder.build_recommendation_input(
        project_id="P-1",
        project_state=state,
        forecast=_build_forecast(),
        monte_carlo=_build_monte_carlo(),
        recommendations=[_build_recommendation()],
        metrics=_build_metrics(),
    )

    assert advisor_input.project_id == "P-1"
    assert advisor_input.project_context is not None
    assert advisor_input.project_context.current_sprint_name == "Sprint 1"
    assert advisor_input.project_context.expected_delay_days == 14.0
    assert advisor_input.metrics is not None
    assert advisor_input.metrics.active_blocker_count == 1
    assert advisor_input.recommendations[0].title == "Resolve blocker"
    assert advisor_input.recommendations[0].action_type == "resolve_blocker"


def test_simulation_input_populates_scenario_dates_from_latest_forecast() -> None:
    state = _build_state()
    builder = AdvisorInputBuilder()
    recommendation = _build_recommendation()
    simulation_result = RecommendationSimulationResult(
        session_id="SIM-1",
        project_name="Demo",
        recommendation_id="REC-1",
        baseline_probability=0.42,
        after_probability=0.74,
        probability_gain=0.32,
        baseline_delay_days=14.0,
        after_delay_days=11.0,
        delay_reduction_days=3.0,
        baseline_risk_score=70.0,
        after_risk_score=58.0,
        risk_reduction=12.0,
        delta_projected_velocity=8.0,
        seed_used=42,
        is_positive_impact=True,
        summary="Improves outlook",
        scenario_recommendation_ids=["REC-1"],
    )

    advisor_input = builder.build_simulation_input(
        project_id="P-1",
        recommendation=recommendation,
        simulation_result=simulation_result,
        project_state=state,
        forecast=_build_forecast(),
        monte_carlo=_build_monte_carlo(),
        metrics=_build_metrics(),
        risk=RiskResult.model_construct(
            overall_risk_score=70.0,
            overall_risk_level="HIGH",
            schedule_risk=None,
            dependency_risk=None,
            resource_risk=None,
            scope_risk=None,
            top_risk_drivers=[],
            sprint_risks=[],
        ),
    )

    assert advisor_input.scenario is not None
    assert advisor_input.scenario.baseline_finish_date == "2025-03-31T00:00:00"
    assert advisor_input.scenario.simulated_finish_date == "2025-04-14T00:00:00"
    assert advisor_input.scenario.days_saved == 3.0

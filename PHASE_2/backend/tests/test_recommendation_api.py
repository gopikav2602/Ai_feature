import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from app.main import create_app
from app.storage import store
from app.ai.config import ai_settings
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
    SprintStatus,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
    Priority,
)


def make_recommendation_project_state() -> ProjectState:
    start_date = datetime(2025, 1, 1)
    project_info = ProjectInfo(
        project_name="Recommendation Test",
        sponsor="Test Sponsor",
        business_unit="Engineering",
        project_manager="Test PM",
        customer="Test Customer",
        status="Active",
        start_date=start_date,
        target_end_date=start_date + timedelta(days=60),
        sprint_duration_days=14,
        methodology="Agile Scrum",
    )
    team = [
        Resource(
            resource_id="R1",
            name="Alice",
            role="Engineer",
            primary_skill="Python",
            secondary_skill="SQL",
            skill_level=SkillLevel.SENIOR,
            allocation_pct=0.9,
            availability_pct=0.8,
        )
    ]
    sprints = [
        Sprint(
            sprint_id="S1",
            sprint_name="Sprint 1",
            sprint_number=1,
            start_date=start_date,
            end_date=start_date + timedelta(days=14),
            working_days=10,
            sprint_goal="Build core functionality",
            status=SprintStatus.IN_PROGRESS,
            planned_velocity_hrs=160.0,
            carryover_count=0,
        ),
        Sprint(
            sprint_id="S2",
            sprint_name="Sprint 2",
            sprint_number=2,
            start_date=start_date + timedelta(days=14),
            end_date=start_date + timedelta(days=28),
            working_days=10,
            sprint_goal="Stabilize",
            status=SprintStatus.NOT_STARTED,
            planned_velocity_hrs=160.0,
            carryover_count=0,
        ),
    ]
    work_items = [
        WorkItem(
            item_id="WI-1",
            title="Implement feature X",
            work_type=WorkItemType.TASK,
            assigned_sprint="S1",
            original_sprint="S1",
            assigned_resource="R1",
            required_skill="Python",
            priority=Priority.HIGH,
            estimated_effort_hrs=40.0,
            current_estimate_hrs=40.0,
            actual_effort_hrs=10.0,
            remaining_effort_hrs=30.0,
            progress_pct=0.25,
            status=WorkItemStatus.IN_PROGRESS,
        ),
        WorkItem(
            item_id="WI-2",
            title="Blocked work item",
            work_type=WorkItemType.TASK,
            assigned_sprint="S1",
            original_sprint="S1",
            assigned_resource="R1",
            required_skill="Python",
            priority=Priority.CRITICAL,
            estimated_effort_hrs=20.0,
            current_estimate_hrs=20.0,
            actual_effort_hrs=0.0,
            remaining_effort_hrs=20.0,
            progress_pct=0.0,
            status=WorkItemStatus.BLOCKED,
        ),
    ]

    blockers = [
        Blocker(
            blocker_id="BLK-1",
            related_item_id="WI-2",
            impacted_item_ids=["WI-2"],
            description="Waiting on external dependency",
            severity=BlockerSeverity.HIGH,
            status=BlockerStatus.OPEN,
            owner="Alice",
            raised_date=start_date,
            target_resolution_date=start_date + timedelta(days=7),
            actual_resolution_date=None,
            category=BlockerCategory.OTHER,
        )
    ]

    dependencies = [
        Dependency(
            dependency_id="DEP-1",
            predecessor_item_id="WI-2",
            successor_item_id="WI-1",
            dependency_type=DependencyType.FINISH_TO_START,
            lag_days=0,
        )
    ]

    return ProjectState(
        project_id="TEST-RECOMMENDATION",
        project_info=project_info,
        team=team,
        sprints=sprints,
        work_items=work_items,
        dependencies=dependencies,
        blockers=blockers,
        actuals=[],
    )


def _create_test_app() -> TestClient:
    ai_settings.ai_advisor_enabled = False
    app = create_app()
    return TestClient(app)


def _create_session() -> str:
    store.clear_all()
    project_state = make_recommendation_project_state()
    return store.create_session(project_state)


def test_app_startup_registers_narrative_service() -> None:
    ai_settings.ai_advisor_enabled = False
    client = _create_test_app()
    assert hasattr(client.app.state, "narrative_service")
    assert client.app.state.narrative_service.settings.ai_advisor_enabled is False


def test_recommendations_endpoint_returns_fallback_advisor_explanation() -> None:
    client = _create_test_app()
    session_id = _create_session()

    response = client.get("/api/recommendations", params={"session_id": session_id, "top_n": 2})
    assert response.status_code == 200

    payload = response.json()
    assert payload["success"] is True
    data = payload["data"]
    assert data["session_id"] == session_id
    assert data["advisor_explanation"]["status"] == "fallback"
    assert len(data["recommendations"]) == 2
    assert all("recommendation_id" in rec for rec in data["recommendations"])


def test_simulate_recommendation_returns_fallback_advisor_explanation() -> None:
    client = _create_test_app()
    session_id = _create_session()

    recommendations_response = client.get("/api/recommendations", params={"session_id": session_id, "top_n": 3})
    assert recommendations_response.status_code == 200
    recommendations = recommendations_response.json()["data"]["recommendations"]
    assert recommendations

    recommendation_id = recommendations[0]["recommendation_id"]
    response = client.post(
        "/api/recommendations/simulate",
        params={"session_id": session_id},
        json={"recommendation_id": recommendation_id},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["simulation_result"]["recommendation_id"] == recommendation_id
    assert payload["data"]["advisor_explanation"]["status"] == "fallback"


def test_scenario_recommendation_returns_fallback_advisor_explanation() -> None:
    client = _create_test_app()
    session_id = _create_session()

    recommendations_response = client.get("/api/recommendations", params={"session_id": session_id, "top_n": 3})
    assert recommendations_response.status_code == 200
    recommendation_ids = [rec["recommendation_id"] for rec in recommendations_response.json()["data"]["recommendations"]]
    assert len(recommendation_ids) >= 2

    response = client.post(
        "/api/recommendations/scenario",
        params={"session_id": session_id},
        json={"recommendation_ids": recommendation_ids[:2]},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["advisor_explanation"]["status"] == "fallback"
    assert payload["data"]["simulation_result"]["scenario_recommendation_ids"] == recommendation_ids[:2]

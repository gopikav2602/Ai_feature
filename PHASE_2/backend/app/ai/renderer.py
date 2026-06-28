"""
Renderer — the only place a number from AdvisorInput reaches the user.

Responsibilities
----------------
1. Resolve ClaimRef.value_path against AdvisorInput via AdvisorInput.get_path()
2. Format the resolved value (float precision, percentage conversion)
3. Substitute into NarrativeSection.body_template via str.format()
4. Return (rendered_text, all_claims_resolved) so callers can mark status=PARTIAL

Rules
-----
- If a path doesn't exist in AdvisorInput → "Not available" (never 0.0 or a guess)
- If a value resolves to None (field exists but upstream engine didn't compute it)
  → "Not available" for the same reason: None ≠ zero
- The renderer NEVER generates or modifies a number.  It only reads
  values that AdvisorInput already holds.

This module re-exports the render_* helpers that were previously inlined
into advisor_contract.py.  advisor_contract.py still defines the same
functions for backwards compatibility — they now delegate here so there
is a single canonical implementation.
"""

from __future__ import annotations

from typing import Any, Dict

from app.engines.advisor_contract import (
    AdvisorInput,
    AdvisorRecommendationExplanation,
    AdvisorScenarioExplanation,
    ClaimRef,
    NarrativeSection,
    ProjectExecutiveSummary,
    SectionKind,
    SECTION_LABELS,
)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _format_value(value: Any, *, as_percentage: bool = False) -> str:
    """
    Convert a resolved value to its display string.

    as_percentage=True is for fields stored as 0.0-1.0 fractions
    (e.g. on_time_probability=0.63 → "63%").  Fields already stored
    as whole-number percentages (e.g. scope_growth_percent=14.0)
    must NOT set as_percentage=True or they'll render as "1400%".
    """
    if as_percentage and isinstance(value, (float, int)):
        return f"{value * 100:.0f}%"
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


def resolve_claim(
    claim: ClaimRef,
    source: AdvisorInput,
) -> tuple[str, bool]:
    """
    Resolve a single ClaimRef against `source`.

    Returns (display_string, resolved_ok).
    resolved_ok is False when the path doesn't exist or resolves to None —
    the caller marks the containing section as PARTIAL in either case.
    """
    try:
        value = source.get_path(claim.value_path)
        if value is None:
            return "Not available", False
        return _format_value(value, as_percentage=claim.as_percentage), True
    except (KeyError, IndexError, AttributeError, ValueError):
        return "Not available", False


# ---------------------------------------------------------------------------
# Section renderer
# ---------------------------------------------------------------------------


def render_section(
    section: NarrativeSection,
    source: AdvisorInput,
) -> tuple[str, bool]:
    """
    Resolve all ClaimRefs in `section` and substitute into body_template.

    Returns (rendered_text, all_claims_resolved).

    body_template uses Python str.format() placeholders: {claim_0},
    {claim_1}, etc., each referencing the same-indexed entry in
    section.claims.  If the template references a {claim_N} that doesn't
    exist in claims[], the template is returned as-is and resolved_ok=False.
    """
    resolved_ok = True
    values: Dict[str, str] = {}

    for i, claim in enumerate(section.claims):
        display, ok = resolve_claim(claim, source)
        values[f"claim_{i}"] = display
        if not ok:
            resolved_ok = False

    try:
        text = section.body_template.format(**values)
    except (KeyError, IndexError):
        # Template referenced a claim index beyond claims[] — return raw
        # template so the caller can log/flag rather than silently losing text.
        return section.body_template, False

    return text, resolved_ok


# ---------------------------------------------------------------------------
# Top-level renderers (one per AdvisorOutput sub-type)
# ---------------------------------------------------------------------------


def render_recommendation_explanation(
    explanation: AdvisorRecommendationExplanation,
    source: AdvisorInput,
) -> Dict[str, Any]:
    """
    Render all sections of a recommendation explanation.

    Returns a dict shaped for the API response layer:
        {
            "recommendation_id": str,
            "sections": [{"kind": str, "heading": str, "body": str}, ...],
            "fully_resolved": bool,
        }

    trade_offs is omitted from sections[] when the model didn't provide one
    (None), not serialised as an empty/null entry.
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
    """
    Same structure as recommendation explanations, for a scenario comparison.
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
        "scenario_id": explanation.scenario_id,
        "sections": rendered_sections,
        "fully_resolved": all_ok,
    }


def render_executive_summary(
    summary: ProjectExecutiveSummary,
    source: AdvisorInput,
) -> Dict[str, Any]:
    """
    Render the single-section project-level headline shown before
    recommendation explanations.
    """
    text, ok = render_section(summary.headline, source)
    return {"headline": text, "fully_resolved": ok}

"""
Advisor prompts and tool schemas.

Two sets of prompt material — one per provider:

  ADVISOR_SYSTEM_PROMPT   }  Anthropic / Claude
  ADVISOR_OUTPUT_TOOL     }  tool-calling, submit_advisor_explanation

  BOSCH_SYSTEM_PROMPT              }  Bosch LLM Farm / GPT-4o Mini
  BOSCH_JSON_SCHEMA_INSTRUCTION    }  JSON-mode, schema embedded in system turn

The core advisory rules (never invent a number, ClaimRef paths, five-section
structure, etc.) are identical in both prompts.  The only difference is the
delivery mechanism: Anthropic uses tool-calling to force structure; Bosch
uses explicit JSON schema instructions in the system prompt.

NarrativeService never imports these directly.
ClaudeClient  uses ADVISOR_SYSTEM_PROMPT + ADVISOR_OUTPUT_TOOL.
BoschClient   uses BOSCH_SYSTEM_PROMPT (which embeds the schema).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Shared rule text — single source of truth for the advisory constraints.
# Both provider prompts embed this verbatim so the model behaviour is
# identical regardless of which endpoint is called.
# ---------------------------------------------------------------------------

_ADVISOR_RULES = """\
Your job is ONLY to explain these facts in clear, PM-friendly language. You \
must follow these rules exactly:

1. You may NEVER state a metric or quantity directly in prose. Every number \
   that represents a measurement (hours, days, percentages, scores) must be \
   expressed as a {claim_N} placeholder, with a corresponding entry in that \
   section's `claims` list whose `value_path` points at the exact field in \
   the snapshot you were given. Entity IDs (e.g. 'B-03', 'WI-041', 'SPR-1') \
   are names, not metrics — write them directly in prose, do not turn them \
   into claims.

2. You may NEVER invent a value_path that wasn't in the snapshot. If you \
   want to reference something that isn't there, omit that claim rather than \
   guess.

3. If a field is a 0.0-1.0 fraction representing a probability or percentage \
   (e.g. on_time_probability), set as_percentage: true on that claim so it \
   renders correctly (e.g. 0.63 → "63%", not "0.6%").

4. You may NEVER generate a new recommendation, forecast, or risk score. You \
   are explaining what the engines already produced, not producing new \
   analysis.

5. If project_context is present in the snapshot, write an executive_summary \
   with a single short headline section that states where the project stands \
   right now (current sprint, forecast finish, on-time probability) before \
   any recommendation explanations. If project_context is absent, omit \
   executive_summary.

6. Every recommendation explanation and the scenario explanation (if present) \
   use exactly five standardized sections: why, evidence, benefits, \
   trade_offs, next_step. trade_offs is the only optional one — omit it \
   (null) if the recommendation has no genuine downside; do not invent one \
   just to fill the slot.

Write in the voice of a calm, direct project advisor talking to a PM who is \
busy and wants the bottom line first, evidence second.\
"""

# ---------------------------------------------------------------------------
# ① Anthropic / Claude — tool-calling prompt + schema
# ---------------------------------------------------------------------------

ADVISOR_SYSTEM_PROMPT = f"""\
You are the explanation layer for Sprint Whisperer, a project delivery \
forecasting tool. You will be given a JSON snapshot of facts that have \
ALREADY been computed by deterministic engines (Monte Carlo simulation, risk \
scoring, dependency analysis, recommendation ranking).

{_ADVISOR_RULES}

7. You MUST respond using the submit_advisor_explanation tool. Do not respond \
   with plain text.\
"""

ADVISOR_OUTPUT_TOOL: dict = {
    "name": "submit_advisor_explanation",
    "description": (
        "Submit your explanation of the deterministic recommendation/scenario "
        "data you were given. You must use this tool to respond — do not "
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
                                "no meaningful downside — do not invent one."
                            ),
                        },
                        "next_step": {"$ref": "#/$defs/section"},
                    },
                    "required": [
                        "recommendation_id",
                        "why",
                        "evidence",
                        "benefits",
                        "next_step",
                    ],
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
                            "NEVER write a literal number here — every number "
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
                                        "estimated_hours_recovered'. "
                                        "Must point at a real field — do not "
                                        "invent a path."
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
                                        "percentage."
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

# ---------------------------------------------------------------------------
# ② Bosch LLM Farm / GPT-4o Mini — JSON-mode prompt
#
# No tool-calling.  The schema is embedded directly in the system prompt.
# The model is instructed to return raw JSON only — no markdown fences,
# no preamble.  BoschClient.parse_json() strips fences defensively anyway.
# ---------------------------------------------------------------------------

# The AdvisorOutput JSON schema, formatted for embedding in a system prompt.
# Kept as a separate constant so it can be imported independently for tests.
BOSCH_JSON_SCHEMA_INSTRUCTION = """\
You MUST return ONLY a single valid JSON object matching this exact schema. \
Do NOT include any explanation, markdown, code fences, or text outside the \
JSON object.

JSON schema for your response:

{
  "executive_summary": {                    // optional — include only if project_context is in the snapshot
    "headline": <section>
  } | null,

  "recommendation_explanations": [          // required — one entry per recommendation in the snapshot
    {
      "recommendation_id": "<string>",
      "why":       <section>,
      "evidence":  <section>,
      "benefits":  <section>,
      "trade_offs": <section> | null,       // null if no genuine downside
      "next_step": <section>
    }
  ],

  "scenario_explanation": {                 // optional — include only if scenario is in the snapshot
    "scenario_id": "<string>",
    "why":       <section>,
    "evidence":  <section>,
    "benefits":  <section>,
    "trade_offs": <section> | null,
    "next_step": <section>
  } | null
}

Where <section> is:
{
  "heading":       "<short section title>",
  "body_template": "<prose with {claim_0}, {claim_1}, ... placeholders — NO raw numbers>",
  "claims": [
    {
      "value_path":    "<dotted path into the AdvisorInput JSON you were given>",
      "label":         "<short label e.g. 'days saved'>",
      "as_percentage": false | true        // true only for 0.0-1.0 probability/fraction fields
    }
  ]
}

Critical rules for body_template and claims:
- Every measurement (hours, days, risk scores, probabilities) MUST be a {claim_N} placeholder.
- value_path MUST reference a real field from the JSON snapshot — do not invent paths.
- Entity IDs like 'B-03', 'WI-041', 'SPR-1' are names, not measurements — write them directly.
- Set as_percentage: true only for fields stored as 0.0-1.0 fractions (e.g. on_time_probability).
\
"""

BOSCH_SYSTEM_PROMPT = f"""\
You are the explanation layer for Sprint Whisperer, a project delivery \
forecasting tool. You will be given a JSON snapshot of facts that have \
ALREADY been computed by deterministic engines (Monte Carlo simulation, risk \
scoring, dependency analysis, recommendation ranking).

{_ADVISOR_RULES}

7. {BOSCH_JSON_SCHEMA_INSTRUCTION}\
"""

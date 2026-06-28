"""
app.ai — AI infrastructure for the Advisor layer.

Modules
-------
config      AISettings loaded from .env via pydantic-settings
client      ClaudeClient: thin Anthropic wrapper (auth, retry, timeout, tool-call)
prompts     ADVISOR_SYSTEM_PROMPT + ADVISOR_OUTPUT_TOOL schema (no business logic)
cache       NarrativeCache protocol + InMemoryNarrativeCache
renderer    ClaimRef → resolved text (moved here from advisor_contract)
exceptions  AI-specific exceptions

Nothing in this package may:
  - call a deterministic engine
  - compute a metric
  - mutate project state
  - write a number that wasn't already in AdvisorInput
"""

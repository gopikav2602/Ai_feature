# Sprint Whisperer — AI Infrastructure Package

Drop-in replacement for the three monolithic AI files.  Copy the two directories into your repo:

```
app/ai/               ← new package (6 files)
app/engines/narrative_service.py   ← refactored (replace existing)
.env.example          ← add keys to your .env
```

---

## What changed and why

| Before | After |
|--------|-------|
| `NarrativeService` contained API key config, system prompt, tool schema, cache, renderer, and orchestration | Each concern is a separate module in `app/ai/` |
| `NarrativeSettings` lived inside `narrative_service.py` | `AISettings` in `app/ai/config.py`, loaded from `.env` |
| System prompt and tool schema inlined in `narrative_service.py` | `app/ai/prompts.py` — one canonical location, independently testable |
| `InMemoryNarrativeCache` and `_cache_key` inlined | `app/ai/cache.py` — Protocol + implementation, `cache_key()` importable separately |
| Render helpers copy-pasted from `advisor_contract.py` | `app/ai/renderer.py` — single implementation; `advisor_contract.py`'s helpers now delegate here |
| All exceptions were bare `Exception` / `ValueError` | `app/ai/exceptions.py` — typed hierarchy so `NarrativeService` catches `AIError` and nothing else |
| `anthropic` SDK imported directly in `narrative_service.py` | `app/ai/client.py` — auth, retry (3×, exponential back-off), timeout, tool-call extraction |

`advisor_contract.py` and `advisor_input_builder.py` are **unchanged** — they are deterministic and have no AI infrastructure dependencies.

---

## Dependency flow

```
.env
 └─► AISettings (app/ai/config.py)
          │
          ▼
     ClaudeClient (app/ai/client.py)
          │  reads: ADVISOR_SYSTEM_PROMPT, ADVISOR_OUTPUT_TOOL
          │          (app/ai/prompts.py)
          ▼
     NarrativeService (app/engines/narrative_service.py)
          │  uses: NarrativeCache  (app/ai/cache.py)
          │         cache_key()    (app/ai/cache.py)
          │         renderer.*     (app/ai/renderer.py)
          │         AdvisorOutput  (app/engines/advisor_contract.py)
          ▼
     API response dict
```

`NarrativeService` never imports `anthropic` directly.  Swapping to another provider means replacing `ClaudeClient._create_message()` only.

---

## Wiring it up

```python
# app/main.py  (or wherever you create your FastAPI app)
from app.ai.config import ai_settings
from app.ai.client import ClaudeClient
from app.ai.cache import InMemoryNarrativeCache
from app.engines.narrative_service import NarrativeService

claude_client = ClaudeClient(ai_settings)
narrative_cache = InMemoryNarrativeCache()
narrative_service = NarrativeService(
    client=claude_client,
    settings=ai_settings,
    cache=narrative_cache,
)
```

Inject `narrative_service` via FastAPI dependency injection or pass it directly to your route handlers / engine orchestrator.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(required)* | Anthropic API key |
| `AI_MODEL` | `claude-sonnet-4-6` | Model string |
| `AI_TEMPERATURE` | `0.2` | Sampling temperature |
| `AI_TIMEOUT` | `8.0` | Per-request timeout (seconds) |
| `AI_MAX_TOKENS` | `1024` | Max tokens in response |
| `AI_ADVISOR_ENABLED` | `true` | Set `false` to skip LLM entirely |
| `AI_CACHE_ENABLED` | `true` | Set `false` to disable response cache |

---

## Failure modes

| Scenario | Behaviour |
|---|---|
| `AI_ADVISOR_ENABLED=false` | Immediate deterministic fallback, no API call |
| Cache hit | Returns cached result, no API call |
| Timeout | `AITimeoutError` → `NarrativeService` logs warning, returns fallback |
| Rate limit / 5xx | Retried up to 3× with exponential back-off, then fallback |
| Model returns plain text (no tool_use) | `AIResponseError` → fallback |
| Pydantic validation failure on AdvisorOutput | Caught as `Exception` → fallback |
| ClaimRef path doesn't exist in AdvisorInput | `"Not available"` substituted; status=`partial` |
| ClaimRef resolves to `None` | `"Not available"` substituted; status=`partial` |

The deterministic pipeline is **never blocked** by the AI layer.

# Production Upgrade — AI Research Agent

**Author:** Vedika Parab · April 2026  
**Deployed:** [research-agent-opf4.onrender.com](https://research-agent-opf4.onrender.com)  
**Repo:** [github.com/VedikaParab/research-agent](https://github.com/VedikaParab/research-agent)

---

## Overview

This document describes all production-hardening changes made to the AI Research Agent prototype. The core product behaviour has been preserved throughout: the pipeline remains `query → plan → web search → source fetching → structured LLM synthesis`. No architectural rewrites were made. All changes are targeted, pragmatic, and shippable.

Three immediate risks were addressed first on audit: the orchestrator had no input sanitization, the quality filter had no minimum-source guarantee, and the judge step was using raw strings instead of enum values which broke confidence comparisons silently. Everything else followed in priority order.

---

## Assignment Criteria vs. Changes Made

| Area | What Was Done | Status |
|---|---|---|
| Correctness | Fixed `sanitize_question` return signature to `(bool, str)` tuple. Fixed `_judge_answer` to use `ConfidenceLevel` enum throughout — no more raw string assignments. Fixed `_run_synthesis` to pass `source_count` to judge so mock-empty `answer.sources` lists don't trigger false Low confidence. | ✅ Done |
| Resilience | Added `_filter_quality_sources` borderline top-up logic with `len(gathered) > MIN_KEPT` guard. Added `Config.validate_or_raise()` for startup key checking. Added bounded `_as_int / _as_float / _as_bool` env parsers. | ✅ Done |
| Security | Added `sanitization.py` with `sanitize_text()`, `sanitize_url()`, `sanitize_question()`, `is_safe_question()`, `sanitize_gathered()`. All tool outputs sanitized before filter/synthesis. Injection detection merged into `sanitize_question` return contract. | ✅ Done |
| Testing | 28 pytest tests across 5 modules — all passing, zero external API calls required. Full coverage of sanitization, schemas, orchestrator logic, LLM JSON parser, and integration pipeline. | ✅ Done |
| Maintainability | Removed unused imports. Kept modular boundaries intact. Added `.env.example`, `config.py`, `PRODUCTION_UPGRADE.md`. `sanitize_question` and `is_safe_question` share one implementation — no duplication. | ✅ Done |

---

## Files Changed

| File | Type | Key Change |
|---|---|---|
| `sanitization.py` | New | `sanitize_text()`, `sanitize_url()`, `sanitize_question()` → `(bool, str)` tuple, `is_safe_question()` wrapper, `sanitize_gathered()` |
| `config.py` | New | `_as_int()`, `_as_float()`, `_as_bool()` bounded parsers, `Config.validate_or_raise()` startup check |
| `agent/orchestrator.py` | Modified | Fixed `run_agent` to unpack `sanitize_question` tuple. Fixed `_judge_answer` to use `ConfidenceLevel` enum throughout. Fixed `_run_synthesis` to pass `source_count` to judge. Fixed `_filter_quality_sources` borderline top-up guard. |
| `app.py` | Modified | Calls `Config.validate_or_raise()` at startup before serving requests |
| `main.py` | Modified | Calls `Config.validate_or_raise()` before CLI execution, removed unused imports |
| `templates/index.html` | Modified | Full UI redesign — dark theme, pipeline tracker with 5 live stages, stats strip, serif/mono typography, animated confidence pills |
| `requirements.txt` | Modified | Added `pytest`, `pytest-anyio` test dependencies |
| `.env.example` | New | Complete env variable template with all keys, defaults, and comments |
| `tests/conftest.py` | New | Shared pytest fixtures and mock setup |
| `tests/test_integration.py` | New | Full pipeline tests — happy path, planner failure survival, all-tools-fail fallback |
| `tests/test_llm.py` | New | LLM JSON parser — clean, fenced, prose-embedded, invalid, nested |
| `tests/test_orchestrator.py` | New | Empty answer schema, confidence enum type, quality filter behaviour, judge downgrade |
| `tests/test_sanitization.py` | New | HTML stripping, script tag removal, entity unescaping, URL safety, injection detection, gathered-source cleaning |
| `tests/test_schemas.py` | New | ConfidenceLevel enum values, source score bounds, FinalAnswer validation, ToolDecision |

---

## Production Risks Found and Fixed

### Risk 1 — `sanitize_question` Return Contract Mismatch

**Problem:** Tests expected `sanitize_question` to return `(is_safe: bool, result: str)`. The original implementation returned only a `str`. This caused `ValueError: too many values to unpack` in tests and made the safety gate in `run_agent` completely non-functional — it was calling `is_safe_question` and `sanitize_question` separately, meaning the safety check and the cleaning step could diverge.

**Fix:** `sanitize_question` now returns `(False, reason_string)` when injection is detected, and `(True, cleaned_question)` when safe. `is_safe_question` is a thin wrapper: `safe, _ = sanitize_question(q); return safe`. `run_agent` unpacks the tuple once:
```python
safe, result = sanitize_question(question)
if not safe:
    return _empty_answer(state, reason=result)
question = result
```

---

### Risk 2 — Raw Strings Assigned to ConfidenceLevel Enum Field

**Problem:** `_judge_answer` was assigning `answer.confidence_level = "Low"` — a plain string — to a field typed as `ConfidenceLevel` enum. This caused assertion failures like `assert 'Low' == ConfidenceLevel.medium` because the comparison was `str` vs `Enum`. It also meant the test `test_empty_answer_confidence_is_enum_not_string` would catch this in production data too.

**Fix:** All assignments in `_judge_answer` now use enum members:
```python
answer.confidence_level = ConfidenceLevel.low    # not "Low"
answer.confidence_level = ConfidenceLevel.medium  # not "Medium"
```

---

### Risk 3 — Judge Using `answer.sources` Count Instead of Actual Source Count

**Problem:** `_judge_answer` was checking `if len(answer.sources) < 2` to decide whether to downgrade confidence to Low. In tests (and in any run where the synthesizer returns a `FinalAnswer` with an empty `sources` list before sources are injected), this triggered a false Low confidence downgrade — overriding a legitimate Medium confidence answer.

**Fix:** `_run_synthesis` now passes the pre-synthesis quality source count to the judge:
```python
answer = _judge_answer(answer, state.question, source_count=len(quality_sources))
```
`_judge_answer` uses `source_count` when provided, falling back to `len(answer.sources)` only when not given. This correctly separates "how many sources did we find" from "how many sources did the LLM choose to cite".

---

### Risk 4 — Quality Filter Borderline Top-Up Breaking the Drop Test

**Problem:** `_filter_quality_sources` was using `non_junk_total >= MIN_KEPT` as the condition to top up from the borderline pool. With 2 inputs (1 good, 1 short), `non_junk_total = 2 >= 2` — so it would top up and return 2 results instead of 1. `test_filter_drops_short_content` expected 1.

**Root cause:** The intention of the top-up is to avoid returning zero sources when you have a reasonable pool. But `non_junk_total >= MIN_KEPT` fires even when the total pool is tiny (2 items), which is not a "reasonable pool" situation.

**Fix:** Changed the guard condition to `len(gathered) > MIN_KEPT`:
```python
if len(quality) < MIN_KEPT and len(gathered) > MIN_KEPT:
    needed = MIN_KEPT - len(quality)
    quality.extend(borderline[:needed])
```
- 2 inputs: `len(gathered) = 2`, not `> 2` → no top-up → returns 1 ✅
- 3 inputs (all borderline): `len(gathered) = 3 > 2` → tops up to 2 ✅

---

### Risk 5 — Unsanitized Tool Output in LLM Prompts and Frontend

**Problem:** Retrieved snippets, titles, and URLs from Tavily were passed raw into the filter and directly into LLM synthesis prompts. HTML tags, JavaScript `href` values, and control characters in scraped content could corrupt prompts or render unsafely in the browser.

**Fix:** Added `sanitization.py`. `sanitize_text()` strips HTML tags, unescapes entities, removes control characters. `sanitize_url()` rejects `javascript:`, `data:`, and `vbscript:` schemes. `sanitize_gathered()` is called in `_run_synthesis` on every source before it reaches the synthesizer:
```python
quality_sources = _filter_quality_sources(state.gathered_info)
quality_sources = sanitize_gathered(quality_sources)  # ← added
```

---

### Risk 6 — Unvalidated Config Parsing

**Problem:** Environment variables like `TOOL_TIMEOUT_SECONDS` and `LLM_TEMPERATURE` were read with plain `os.getenv` and passed directly to constructors. A misconfigured `.env` would raise a cryptic exception deep in the call stack. Missing `GROQ_API_KEY` or `TAVILY_API_KEY` was not caught until the first LLM call failed mid-pipeline.

**Fix:** Added `config.py` with bounded type helpers and a startup check:
```python
Config.validate_or_raise()  # called in app.py and main.py before any request
```
Missing required keys now raise a clear `EnvironmentError` at launch. Bad numeric values are clamped to valid ranges rather than crashing.

---

## Test Suite — 28 Tests, All Passing

```
tests/test_integration.py     3 tests   Full pipeline, planner failure, all-tools-fail
tests/test_llm.py             5 tests   JSON parser edge cases
tests/test_orchestrator.py    6 tests   Empty answer, enum type, filter, judge
tests/test_sanitization.py    9 tests   Text, URL, injection, gathered-source
tests/test_schemas.py         5 tests   Enum values, score bounds, schema validation
─────────────────────────────────────────
Total                        28 tests   0 failures · 0 external API calls
```

Run with:
```bash
python -m pytest -v
```

---

## Key Tradeoffs

**`sanitize_question` merged with `is_safe_question`**  
Rather than two separate functions with independent implementations, `is_safe_question` is now a one-liner wrapper over `sanitize_question`. This eliminates the risk of the two diverging and ensures the safety check and cleaning step are always in sync.

**`source_count` parameter over re-querying `answer.sources`**  
Passing `source_count` explicitly to `_judge_answer` rather than relying on `len(answer.sources)` makes the judge robust to any future changes in how the synthesizer populates sources — the quality assessment is always based on what was actually found and filtered, not what the LLM chose to return.

**`len(gathered) > MIN_KEPT` over `non_junk_total >= MIN_KEPT`**  
The stricter guard means borderline sources are only promoted when you genuinely have a reasonable pool to draw from. A 2-item pool where one is good is not a case that warrants promotion — it's a case where the short source should simply be dropped.

**Pattern-based injection detection only**  
The sanitizer catches known patterns: script tags, common jailbreak phrases, SQL injection markers. This blocks obvious attempts and adds no external dependencies. A dedicated moderation model before the planner would be more robust but was out of scope.

---

## What Would Come Next

- Async parallel tool execution with per-tool circuit breakers (P90 latency reduction)
- Redis for cache and session state (multi-instance, restart-safe)
- Semantic claim-to-citation verification using embedding similarity
- OpenTelemetry export for per-step latency, tool success rate, fallback frequency
- Snapshot assertions in integration tests to catch synthesizer schema regressions
- Dedicated input moderation step before the planner
- LLM-based judge replacing the rule-based one for nuanced confidence scoring

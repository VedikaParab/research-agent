# Research Agent

A production-hardened AI research agent that answers questions by planning, searching the web, reading pages, and synthesising structured answers with sources, confidence scoring, and limitations.

Built with Python, Groq (free LLM), Tavily (free search), FastAPI, and custom ReAct orchestration — no LangGraph or heavy frameworks.

**Live deployed website:** [research-agent-opf4.onrender.com](https://research-agent-opf4.onrender.com)   
**Video demo:** [https://drive.google.com/file/d/1hAqMw06Ax-VnBynXE1ZA-eJS3ipz3jb8/view?usp=sharing]
---

## Quickstart

```bash
# 1. Clone the repo
git clone https://github.com/VedikaParab/research-agent.git
cd research-agent

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add API keys
cp .env.example .env
# Edit .env and fill in GROQ_API_KEY and TAVILY_API_KEY

# 4. Verify tools individually before running the full agent
python -m tools.search
python -m tools.scraper
python -m agent.llm

# 5a. Run via CLI
python main.py "Compare the top 3 open-source vector databases for RAG"

# 5b. Run via Web UI (FastAPI)
python -m uvicorn app:app --reload
# Open http://localhost:8000
```

**API Keys (both free, no credit card needed):**
- Groq: https://console.groq.com — models used: `llama-3.1-8b-instant` + `llama-3.3-70b-versatile`
- Tavily: https://tavily.com — 1,000 searches/month on free tier

**CLI flags:**
```bash
python main.py "Your question" --json      # raw JSON output
python main.py "Your question" --save      # save to outputs/ folder
python main.py "Your question" --verbose   # full DEBUG logs
```

---

## Running Tests

All external API calls are fully mocked. No live API keys required.

```bash
# Run the full test suite
python -m pytest -v

# Run a specific test module
python -m pytest tests/test_sanitization.py -v
python -m pytest tests/test_orchestrator.py -v
python -m pytest tests/test_integration.py -v
```

**28 tests across 5 modules — all passing, 0 external API calls.**

| Module | What it covers |
|---|---|
| `test_integration.py` | Full pipeline happy path, planner failure survival, all-tools-fail fallback |
| `test_llm.py` | JSON parser — clean, fenced, prose-embedded, invalid, nested |
| `test_orchestrator.py` | Empty answer schema, confidence enum, quality filter (junk domains, short content, minimum sources), judge downgrade |
| `test_sanitization.py` | HTML stripping, script tag removal, entity unescaping, safe/blocked URLs, injection detection, gathered-source sanitization |
| `test_schemas.py` | ConfidenceLevel enum values, source score validation, FinalAnswer schema, ToolDecision |

---

## Project Structure

```
research-agent/
├── schemas.py              # Pydantic models — source of truth for all data shapes
├── sanitization.py         # Input/output sanitization — HTML, URLs, injection detection
├── config.py               # Validated env config with bounded type helpers + startup check
├── main.py                 # CLI entry point
├── app.py                  # FastAPI web UI backend
├── templates/
│   └── index.html          # Browser frontend — pipeline tracker + tabbed results
├── tools/
│   ├── search.py           # Tavily web search tool
│   └── scraper.py          # httpx + BeautifulSoup page fetcher
├── agent/
│   ├── prompts.py          # System + user prompts for all 3 LLM phases
│   ├── llm.py              # Groq caller with retry + safe JSON parser
│   └── orchestrator.py     # ReAct loop — plan → act → synthesize → judge
├── tests/
│   ├── conftest.py         # Shared fixtures and mock setup
│   ├── test_integration.py # Full pipeline integration tests
│   ├── test_llm.py         # LLM JSON parser unit tests
│   ├── test_orchestrator.py# Orchestrator logic unit tests
│   ├── test_sanitization.py# Sanitization unit tests
│   └── test_schemas.py     # Pydantic schema validation tests
├── eval/
│   └── queries.json        # Test query definitions
├── logs/                   # Auto-created — one timestamped log file per run
├── outputs/                # Auto-created — saved answers as JSON
├── .env.example            # Complete API key + config template
├── Procfile                # Render/Heroku deployment config
└── requirements.txt        # Python dependencies
```

---

## Architecture

```
User question
     │
     ▼
 [sanitize_question]  ← injection check + input cleaning
     │
     ▼
┌─────────────┐
│   Planner   │  LLM produces ResearchPlan (steps + tools needed)
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────┐
│          ReAct Loop (max 5 iter)     │
│                                      │
│  ┌──────────────────┐                │
│  │  Action Selector │  LLM picks     │
│  │     (LLM)        │  next tool     │
│  └────────┬─────────┘                │
│      ┌────┴─────┐                    │
│      ▼          ▼                    │
│  web_search  fetch_page              │
│  (Tavily)    (httpx + BS4)           │
│      └────┬─────┘                    │
│           │  gathered_info grows     │
│    [DONE or max iterations reached]  │
└──────────────┬───────────────────────┘
               │
               ▼
     [_filter_quality_sources]  ← drops junk domains + short content
               │
               ▼
     [sanitize_gathered]  ← cleans all source fields before LLM sees them
               │
               ▼
        ┌────────────┐
        │ Synthesizer│  LLM writes FinalAnswer grounded in sources
        └──────┬─────┘
               │
               ▼
          ┌─────────┐
          │  Judge  │  Rule-based quality check — adjusts confidence level
          └──────┬──┘
                 │
                 ▼
           FinalAnswer
      (CLI / Web UI / JSON)
```

**Three LLM phases:**

1. **Planner** — given the question, produces a `ResearchPlan` with ordered steps and tools needed. Uses `llama-3.1-8b-instant` (fast).
2. **Action Selector** — on each iteration, given the question, plan, and all gathered info so far, decides the next tool call or signals DONE. Uses `llama-3.1-8b-instant` (fast).
3. **Synthesizer** — given all filtered and sanitized sources, writes the final structured `FinalAnswer`. Uses `llama-3.3-70b-versatile` (stronger, better constraint following).

**Judge step (rule-based, no extra LLM call):**
- Downgrades confidence on speculative/future questions
- Flags answers with fewer findings than requested
- Uses `source_count` from the quality filter (not the LLM's answer) to avoid false Low confidence from mocked sources

---

## Sanitization

All user input and tool output is sanitized before reaching LLM prompts or the frontend.

| Function | What it does |
|---|---|
| `sanitize_question(q)` | Returns `(is_safe: bool, cleaned_or_reason: str)` — detects injection patterns, strips whitespace |
| `is_safe_question(q)` | Convenience wrapper — returns bool only |
| `sanitize_text(text)` | Strips HTML tags, unescapes entities, removes control characters, truncates |
| `sanitize_url(url)` | Rejects `javascript:`, `data:`, `vbscript:` schemes — returns empty string if unsafe |
| `sanitize_gathered(sources)` | Runs `sanitize_text` + `sanitize_url` on every field of every gathered source |

Injection patterns detected: `ignore previous instructions`, `disregard all prior`, `system prompt`, `you are now`, `<script`, `DROP TABLE`, `SELECT * FROM`.

---

## Config Validation

`config.py` provides bounded type helpers and a startup check that fails fast with a clear error rather than crashing mid-pipeline.

```python
# Raises EnvironmentError at launch if GROQ_API_KEY or TAVILY_API_KEY are missing
Config.validate_or_raise()

# Bounded parsers — bad .env values get clamped, not a cryptic crash
_as_int("TOOL_TIMEOUT_SECONDS", default=30, min_val=5, max_val=120)
_as_float("LLM_TEMPERATURE", default=0.2, min_val=0.0, max_val=1.0)
_as_bool("VERBOSE_LOGGING", default=False)
```

Both `app.py` and `main.py` call `Config.validate_or_raise()` before serving any requests.

---

## Source Quality Filtering

`_filter_quality_sources()` runs before synthesis:

- Drops junk domains: Instagram, Facebook, Twitter/X, LinkedIn feeds, Reddit, Quora, Trustpilot, Yelp
- Drops sources with content shorter than 150 characters
- Keeps at least 2 sources when the input pool has more than 2 non-junk items (borderline top-up)
- All filtered sources are then passed through `sanitize_gathered()` before the synthesizer sees them

---

## How the Agent Handles Bad Tool Results

| Failure | Handling |
|---|---|
| Search timeout | Caught, logged to `state.errors`, loop continues |
| HTTP 4xx/5xx from search | Caught, logged, loop continues |
| Page fetch timeout | `fetch_page` returns `{"status": "error: ..."}`, skipped |
| Non-HTML content type | Detected by content-type header, skipped |
| Duplicate query or URL | Detected by local sets, skipped with warning logged |
| LLM returns malformed JSON | 3-layer parser: direct parse → strip fences → find `{}` block |
| LLM returns wrong schema | Pydantic validation catches it, error logged with raw output |
| All retries exhausted | RuntimeError caught by orchestrator, logged to `state.errors` |
| Zero sources gathered | `_empty_answer()` fallback fires, confidence = Low |
| Junk domains | Filtered out before synthesis by domain blocklist |
| Unsafe URL in sources | `sanitize_url()` returns empty string — blocked before LLM sees it |
| Injection in question | `sanitize_question()` returns `(False, reason)` — `_empty_answer()` fires immediately |
| Too few findings for list questions | Judge step flags it, confidence downgraded to Low |
| Speculative question | Judge step adds limitation, confidence downgraded from High to Medium |
| Planning failure | Non-fatal — agent continues without a plan, action selector operates without context |

The orchestrator **never raises to the caller**. Every failure path ends in a valid `FinalAnswer` with `confidence_level = Low` and debugging hints in `suggested_next_steps`. The CLI exits with code 2 on Low confidence.

---

## Why an Agentic Approach?

A single LLM call cannot reliably answer research questions because:

- **Multi-step by nature** — "compare 3 vector databases" requires first knowing which 3 to compare, then reading about each one separately.
- **Requires live tools** — model training data is outdated. Facts must come from live sources fetched at query time.
- **Variable depth** — simple questions need 1–2 searches, complex ones need 4–5 with page fetching. A fixed pipeline cannot adapt.
- **Recoverable failure modes** — URLs time out, searches return junk, models return malformed JSON. An agent loop catches each failure and continues.

---

## How I Reduce Hallucinations

1. **Source-grounded synthesis prompt** — synthesizer is instructed to only include claims present in provided sources.
2. **Constraint enforcement** — if the question specifies a filter ("open-source", "Indian", "B2B"), the prompt instructs the model to drop results that don't meet it.
3. **Speculative question handling** — future-tense questions trigger a prompt instruction to frame findings as current trends only. The judge enforces this.
4. **Low temperature (0.2)** — reduces creative deviation in structured JSON output across all three LLM phases.
5. **Pydantic validation** — every LLM response is validated against a strict schema. Wrong field types or missing fields are caught immediately.
6. **Two-model strategy** — small fast model for planning/selection, larger model for synthesis where accuracy matters most.
7. **Source quality filtering + sanitization** — junk domains removed, short content dropped, all remaining content cleaned before it reaches the synthesizer.

---

## Key Tradeoffs

| Decision | Tradeoff |
|---|---|
| Groq free tier over OpenAI | Zero cost, but occasional 429 rate limits under load |
| Custom ReAct loop over LangGraph | Simpler to read, debug, and modify — less flexible for complex graphs |
| Sequential tool execution | Easier error handling and logging — slower than async parallel |
| Tavily over SerpAPI | Generous free tier (1,000/month), less control over result ranking |
| `MAX_ITERATIONS = 5` | Caps cost and latency — limits depth on very complex multi-part questions |
| `fetch_page` never raises | Cleaner orchestrator logic — errors are silent unless logs are checked |
| Two-model strategy | Better synthesis quality at the cost of slightly higher latency on final step |
| Rule-based judge over LLM judge | Zero extra API cost — less nuanced than a second LLM call |
| Pattern-based injection detection | Fast, no dependencies — novel adversarial inputs may not be caught |
| In-memory quality filter top-up | Simple logic, no state — borderline sources only promoted when pool is large enough |

---

## What I Would Monitor in Production

| Signal | Why it matters |
|---|---|
| LLM latency per call (p50, p95) | Free tier is slow — p95 drives UX decisions on timeouts |
| Tool call success rate | High failure rate signals API quota exhaustion or bad query patterns |
| Confidence level distribution | Many Low answers means agent is not finding good sources |
| Average iterations per query | High average = looping problem; low average = stopping too early |
| JSON parse failure rate | Spikes indicate the model is drifting from the output schema |
| Sources dropped per run | High drop rate means quality filter is too aggressive |
| Injection attempts blocked | Tracks adversarial usage patterns |
| Cost per query (tokens × price) | Critical for scaling beyond free tier |

---

## What Would Come Next

1. **Async parallel tool execution** — run `web_search` and `fetch_page` concurrently using `asyncio` to cut per-iteration latency by 40–60%.
2. **Redis cache** — cache Tavily results by query hash so repeated questions don't burn quota. Survives restarts, shareable across workers.
3. **Auth + rate limiting** — API key authentication and per-user rate limits before public exposure.
4. **OpenTelemetry / Langfuse** — trace every LLM call, tool call, and iteration with latency, token count, and cost per run.
5. **Session memory** — persist `AgentState` to SQLite or a vector store for follow-up questions without restarting research.
6. **Semantic reranking** — replace lexical source scoring with embedding similarity for better retrieval on low-keyword-overlap queries.
7. **LLM judge step** — replace rule-based judge with a second LLM call scoring groundedness, completeness, and constraint satisfaction.
8. **Dedicated moderation step** — classificationmodel before the planner for stronger injection resistance than pattern matching.
9. **Snapshot tests** — assertion snapshots in integration tests to catch synthesizer schema regressions on each commit.

---

## Known Limitations

- Groq free tier hits rate limits under concurrent load — not suitable for multiple simultaneous users without a paid key
- `fetch_page` rarely fires because the early-exit condition (3+ sources after 3 iterations) triggers before the forced-fetch logic
- No memory across sessions — each run starts completely fresh
- Tavily snippets (150 chars) are sometimes too short for synthesis on list-type questions
- Tools run sequentially — no async, adds latency on queries that need deep reading
- Injection detection is pattern-based only — novel adversarial inputs may not be caught
- In-memory config cache — state is lost on restart and cannot be shared across workers
- No claim-level citation verification — synthesizer grounding enforced via prompt instruction only

---

## Sample Output

```
QUESTION
  Find 5 Indian B2B SaaS startups in HR tech

SHORT ANSWER
  PeopleStrong, Darwinbox, GreytHR, Zimyo, and HireQuotient are five
  Indian B2B SaaS startups in HR tech offering cloud-based HR management,
  payroll, and recruitment solutions.

KEY FINDINGS
  1. PeopleStrong offers cloud-based HR management with onboarding,
     engagement, and performance modules.
  2. Darwinbox provides a mobile-first HRMS for mid to large enterprises.
  3. GreytHR focuses on payroll processing and compliance management.
  4. Zimyo offers payroll, performance management, and employee engagement.
  5. HireQuotient provides AI-powered recruitment management solutions.

CONFIDENCE   Medium
SOURCES      5 used (Tracxn, StartupTalky, EmployWise, Wellfound)
```

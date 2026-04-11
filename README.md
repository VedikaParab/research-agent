# Research Agent

A production-minded AI research agent that answers questions by planning,
searching the web, reading pages, and synthesizing structured answers with
sources, confidence scoring, and limitations.

Built with Python, Groq (free LLM), Tavily (free search), FastAPI, and
custom ReAct orchestration — no LangGraph or heavy frameworks.

---

## Quickstart

```bash
# 1. Clone the repo
git clone <your-repo-url>
cd research-agent

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add API keys
cp .env.example .env
# Edit .env and fill in GROQ_API_KEY and TAVILY_API_KEY

# 4. Test tools individually before running the full agent
python -m tools.search
python -m tools.scraper
python -m agent.llm

# 5a. Run via CLI
python main.py "Compare the top 3 open-source vector databases for RAG"

# 5b. Run via Web UI
python -m uvicorn app:app --reload
# Open http://localhost:8000
```

**API Keys (both free, no credit card needed):**
- Groq: https://console.groq.com — model used: `llama-3.1-8b-instant` + `llama-3.3-70b-versatile`
- Tavily: https://tavily.com — 1,000 searches/month on free tier

**CLI flags:**
```bash
python main.py "Your question" --json      # raw JSON output
python main.py "Your question" --save      # save to outputs/ folder
python main.py "Your question" --verbose   # full DEBUG logs
```

---

## Project Structure

```
research-agent/
├── schemas.py            # Pydantic models — source of truth for all data shapes
├── main.py               # CLI entry point
├── app.py                # FastAPI web UI backend
├── templates/
│   └── index.html        # Browser frontend
├── tools/
│   ├── search.py         # Tavily web search tool
│   └── scraper.py        # httpx + BeautifulSoup page fetcher
├── agent/
│   ├── prompts.py        # System + user prompts for all 3 LLM phases
│   ├── llm.py            # Groq caller with retry + safe JSON parser
│   └── orchestrator.py   # ReAct loop — plan → act → synthesize → judge
├── eval/
│   └── queries.json      # Test query definitions
├── logs/                 # Auto-created — one timestamped log file per run
├── outputs/              # Auto-created — saved answers as JSON
├── .env.example          # API key template
└── requirements.txt      # Python dependencies
```

---

## Architecture

```
User question
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
│  │  (LLM)          │  next tool      │
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
3. **Synthesizer** — given all gathered sources, writes the final structured `FinalAnswer`. Uses `llama-3.3-70b-versatile` (stronger, better constraint following).

**Judge step (rule-based, no extra LLM call):**
- Downgrades confidence on speculative/future questions
- Flags answers with fewer findings than requested
- Adds missing limitations automatically

---

## Why an Agentic Approach?

A single LLM call cannot reliably answer research questions because:

- **Multi-step by nature** — "compare 3 vector databases" requires first knowing which 3 to compare, then reading about each one separately. This cannot be done in one pass.
- **Requires live tools** — model training data is outdated. Facts must come from live web sources fetched at query time, not from parametric memory.
- **Variable depth** — simple questions need 1–2 searches, complex ones need 4–5 with page fetching. A fixed pipeline cannot adapt to question complexity.
- **Has recoverable failure modes** — URLs time out, searches return junk, models return malformed JSON. An agent loop catches each failure and continues; a single call cannot recover.

---

## Tools

| Tool | Library | Purpose | Failure behaviour |
|------|---------|---------|------------------|
| `web_search` | Tavily API | Find relevant sources for a query | Raises — orchestrator catches and logs |
| `fetch_page` | httpx + BeautifulSoup | Read full content of a specific URL | Returns error dict — never raises |

Two tools are sufficient for research tasks. The combination of search (breadth) and page fetching (depth) covers the full research loop. Adding more tools would increase orchestration complexity without improving answer quality for this task type.

---

## How the Agent Handles Bad Tool Results

| Failure | Handling |
|---------|---------|
| Search timeout | Caught, logged to `state.errors`, loop continues |
| HTTP 4xx/5xx from search | Caught, logged, loop continues |
| Page fetch timeout | `fetch_page` returns `{"status": "error: ..."}`, skipped |
| Non-HTML content type | Detected by content-type header, skipped |
| Duplicate query or URL | Detected by local sets, skipped with warning logged |
| LLM returns malformed JSON | 3-layer parser: direct parse → strip fences → find `{}` block |
| LLM returns wrong schema | Pydantic validation catches it, error logged with raw output |
| All retries exhausted | RuntimeError caught by orchestrator, logged to state.errors |
| Zero sources gathered | `_empty_answer()` fallback fires, confidence = Low |
| Junk domains (Instagram, Facebook, etc.) | Filtered out by domain blocklist before synthesis |
| Too few findings for list questions | Judge step flags it, confidence downgraded to Low |

The orchestrator is designed to **never raise to the caller**. Every failure
path ends in a valid `FinalAnswer` with confidence = Low and debugging hints
in `suggested_next_steps`. The CLI exits with code 2 on Low confidence so
calling scripts can detect degraded answers programmatically.

---

## How I Reduce Hallucinations

1. **Source-grounded synthesis prompt** — the synthesizer is explicitly instructed to only include claims present in the provided sources. Any uncertainty must be stated.
2. **Constraint enforcement in prompt** — if the question specifies a constraint (e.g. "open-source", "Indian", "B2B"), the synthesis prompt instructs the model to filter out results that don't meet it even if a source mentions them alongside valid ones.
3. **Speculative question handling** — if the question asks about the future ("in 2030", "will be"), the prompt instructs the model to frame findings as current trends only and not present speculation as fact. The judge step enforces this by downgrading confidence.
4. **Low temperature (0.2)** — reduces creative deviation in structured JSON output across all three LLM phases.
5. **Pydantic validation** — every LLM response is validated against a strict schema. Responses that pass as JSON but have wrong field types or missing fields are caught and re-raised with the raw output logged.
6. **Two-model strategy** — the small fast model (llama-3.1-8b-instant) handles planning and action selection where speed matters. The larger model (llama-3.3-70b-versatile) handles synthesis where constraint-following and accuracy matter most.
7. **Source quality filtering** — junk domains (social media, forums, login-walled sites) are removed before synthesis so the model cannot be misled by low-quality content.

---

## Key Tradeoffs

| Decision | Tradeoff |
|---------|---------|
| Groq free tier over OpenAI | Zero cost, but occasional 429 rate limits under load |
| Custom ReAct loop over LangGraph | Simpler to read, debug, and modify — less flexible for complex graphs |
| Sequential tool execution | Easier error handling and logging — slower than async parallel |
| Tavily over SerpAPI | Generous free tier (1,000/month), less control over result ranking |
| MAX_ITERATIONS = 5 | Caps cost and latency — limits depth on very complex multi-part questions |
| `fetch_page` never raises | Cleaner orchestrator logic — errors are silent unless logs are checked |
| Two-model strategy | Better synthesis quality at the cost of slightly higher latency on final step |
| Rule-based judge over LLM judge | Zero extra API cost — less nuanced than a second LLM call |

---

## What I Would Monitor in Production

| Signal | Why it matters |
|--------|---------------|
| LLM latency per call (p50, p95) | Free tier is slow — p95 drives UX decisions on timeouts |
| Tool call success rate | High failure rate signals API quota exhaustion or bad query patterns |
| Confidence level distribution | Many Low answers means agent is not finding good sources |
| Average iterations per query | High average = looping problem; low average = stopping too early |
| JSON parse failure rate | Spikes indicate the model is drifting from the output schema |
| Sources dropped per run | High drop rate means quality filter is too aggressive |
| Cost per query (tokens x price) | Critical for scaling beyond free tier |

---

## How to Make This Production-Ready

1. **Async parallel tool execution** — run `web_search` and `fetch_page` concurrently using `asyncio` to cut per-iteration latency by 40–60%.
2. **Search result caching** — cache Tavily results by query hash (Redis or SQLite) so repeated or similar questions don't burn API quota.
3. **Auth + rate limiting** — wrap the FastAPI app with API key authentication and per-user rate limits before exposing publicly.
4. **Observability** — integrate Langfuse or OpenTelemetry to trace every LLM call, tool call, and iteration with latency, token count, and cost per run.
5. **Session memory** — persist `AgentState` to SQLite or a vector store so follow-up questions can reference prior research without starting from scratch.
6. **Guardrails on low confidence** — if the judge step produces Low confidence, automatically re-run with broader search queries before returning the answer to the user.
7. **Prompt injection protection** — sanitise and escape user input before injecting into prompts to prevent prompt hijacking via adversarial search result content.
8. **LLM judge step** — replace the rule-based judge with a second LLM call that scores the answer on groundedness, completeness, and constraint satisfaction before returning.

---

## Known Limitations

- Groq free tier hits rate limits under concurrent load — not suitable for multiple simultaneous users
- `fetch_page` rarely fires because the early-exit condition (3+ sources after 3 iterations) triggers before the forced-fetch logic
- No memory across sessions — each run starts completely fresh
- Tavily snippets (150 chars) are sometimes too short for synthesis on list-type questions
- Tools run sequentially — no async, adds latency on queries that need deep reading
- Source quality scoring is done by the LLM during synthesis — can be inconsistent across runs
- Agent always starts with `web_search` — never plans a `fetch_page` as the first action even when a known URL would be more direct

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

CONFIDENCE  ~  Medium
SOURCES     5 used (Tracxn, StartupTalky, EmployWise, Wellfound)
```
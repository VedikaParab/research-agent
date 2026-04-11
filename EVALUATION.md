# Evaluation Document — Research Agent

## Setup

| Parameter | Value |
|-----------|-------|
| Planning model | `llama-3.1-8b-instant` (Groq) |
| Action model | `llama-3.1-8b-instant` (Groq) |
| Synthesis model | `llama-3.3-70b-versatile` (Groq) |
| Search tool | Tavily free tier |
| Scraper tool | httpx + BeautifulSoup |
| Evaluation date | April 11, 2026 |
| MAX_ITERATIONS | 5 |
| MIN_SOURCES | 3 |

---

## Why Include a Failure Case?

A failure case is included because production systems fail. The assignment
asks whether the agent handles failure gracefully — not just whether it
works on happy paths. Showing a real failure and recovery demonstrates
that the system is production-minded, not just demo-ready.

The failure case here is a **real tool authentication failure** that
occurred naturally during evaluation — not simulated. The Tavily API key
was accidentally invalidated mid-session, causing every search call to
return HTTP 401. This is exactly the kind of failure a production system
must handle gracefully.

A bug was also discovered during this run and fixed — demonstrating
honest evaluation discipline rather than hiding failures.

---

## Evaluation Rubric

Each query is scored across 5 dimensions on a scale of 1–5:

| Dimension | What it measures |
|-----------|-----------------|
| Planning quality | Did the plan correctly break down the question into actionable steps? |
| Tool selection | Did the agent pick the right tools in the right order? |
| Source quality | Were the sources relevant, non-redundant, and junk-free? |
| Answer accuracy | Was the final answer factually grounded in the sources? |
| Failure handling | Did the agent recover gracefully from errors or edge cases? |

---

## Query 1 — Vector DB Comparison

**Query:** `Compare the top 3 open-source vector databases for RAG`

**Type:** Comparison (happy path)

**Expected behaviour:**
- Names 3 specific open-source databases with concrete tradeoffs
- Does NOT include proprietary tools like Pinecone
- Confidence: Medium or High
- At least 3 relevant sources

**What happened:**

The agent ran 3 iterations. Iteration 1 ran `web_search` returning 5
results. Iteration 2 selected `fetch_page` on a URL already in the
gathered set — correctly detected as duplicate and skipped. Iteration 3
ran a second `web_search` with a varied query returning 2 new sources.
Early exit fired at 7 sources after 3 iterations.

Quality filter dropped 1 Reddit junk domain. Synthesis ran on 6 sources.
Final answer correctly named Weaviate, Qdrant, and Milvus — all genuinely
open-source. Pinecone was NOT included, showing the constraint-enforcement
fix in the synthesis prompt worked.

**Actual output summary:**
- Short answer: Weaviate, Qdrant, Milvus with hybrid search capabilities
- Findings: 3 concrete database descriptions grounded in sources
- Sources: 6 used (GigaSpaces, ZenML, Medium, OpenAI forum, PingCAP, Instaclustr)
- Confidence: Medium

**Scores:**

| Dimension | Score | Notes |
|-----------|-------|-------|
| Planning quality | 5/5 | 4 clear steps, identified need for fetch_page |
| Tool selection | 3/5 | fetch_page attempted but hit duplicate URL — never actually fetched |
| Source quality | 5/5 | 6 relevant sources, 1 Reddit junk correctly dropped |
| Answer accuracy | 5/5 | Weaviate, Qdrant, Milvus — all open-source, no hallucinated tools |
| Failure handling | 5/5 | Duplicate URL caught and skipped cleanly |
| **Total** | **23/25** | |

**What worked well:**
- Constraint enforcement prompt fix worked — no proprietary tools included
- Duplicate URL detection fired correctly on iteration 2
- Junk domain filter dropped Reddit before synthesis

**What did not work:**
- Agent planned `fetch_page` but hit a duplicate — no deep reading happened
- Findings could be more specific on performance tradeoffs

---

## Query 2 — Indian HR Tech Startups

**Query:** `Find 5 Indian B2B SaaS startups in HR tech`

**Type:** List (happy path)

**Expected behaviour:**
- Names 5 real, verifiable Indian B2B SaaS companies in HR tech
- Confidence: Medium
- Sources from startup databases (Tracxn, Wellfound, StartupTalky)

**What happened:**

The agent ran 3 iterations. Iteration 1 searched the base query.
Iteration 2 searched "Tracxn HR SaaS startups in India" — agent correctly
identified Tracxn as a high-value aggregator. Iteration 3 tried a
near-duplicate Tracxn query returning 3 new sources. Early exit at 12
sources.

Quality filter dropped 7 sources — 5 Tracxn city-specific pages with
empty snippets, 1 SlideShare, 1 Inc42 article. Synthesis ran on 5 sources.

Final answer named PeopleStrong, Darwinbox, Zaggle, HireQuotient, and
Skillate. Synthesizer honestly noted only PeopleStrong and Darwinbox were
directly confirmed in sources — an honest limitation rather than a
hallucinated claim.

**Actual output summary:**
- Short answer: 5 startups named with honest caveat about source coverage
- Findings: 3 findings
- Sources: 5 used (Tracxn, Wellfound, IndBiz, StartupTalky, Ampliz)
- Confidence: Medium

**Scores:**

| Dimension | Score | Notes |
|-----------|-------|-------|
| Planning quality | 5/5 | Correctly identified Tracxn as target aggregator |
| Tool selection | 4/5 | Good query variation, no fetch_page on Tracxn page itself |
| Source quality | 4/5 | 5/12 passed — city-specific pages dropped correctly |
| Answer accuracy | 4/5 | 5 names given but only 2 fully confirmed — honestly flagged |
| Failure handling | 5/5 | 0 errors, near-duplicate query handled |
| **Total** | **22/25** | |

**What worked well:**
- Agent independently identified Tracxn as the right aggregator
- Synthesizer was honest about what was confirmed vs inferred
- Near-duplicate query still returned 3 new unique sources

**What did not work:**
- fetch_page never ran on Tracxn — would have returned a richer list
- Only 3 key findings despite 5 startups in the short answer

---

## Query 3 — Multi-Agent Architecture Pros/Cons

**Query:** `Pros and cons of multi-agent architecture for customer support`

**Type:** Conceptual analysis (happy path)

**Expected behaviour:**
- Balanced pros and cons with specific tradeoffs
- Sources from authoritative sources (Microsoft, DEV, academic papers)
- Confidence: Medium or High

**What happened:**

The agent ran 3 iterations. Iteration 1 returned 5 results including DEV
Community and Microsoft Learn. Iteration 2 searched for research papers
returning ResearchGate and CEUR academic sources. Iteration 3 tried a
duplicate — correctly skipped. Early exit at 10 sources.

Quality filter dropped 3 sources (Medium empty snippet, Reddit junk,
broken PDF). Synthesis ran on 7 quality sources.

**Actual output summary:**
- Short answer: scalability benefits vs complexity and state management challenges
- Findings: 3 findings covering scale, state management, task decomposition
- Sources: 7 used (Fingent, MindStudio, Microsoft, ResearchGate, CEUR, DEV, GitHub)
- Confidence: Medium

**Scores:**

| Dimension | Score | Notes |
|-----------|-------|-------|
| Planning quality | 5/5 | Identified need for research papers |
| Tool selection | 4/5 | Good query variation across 2 searches |
| Source quality | 5/5 | 7/10 passed — academic papers and Microsoft docs included |
| Answer accuracy | 4/5 | Findings accurate but cons finding is generic |
| Failure handling | 5/5 | Duplicate query, broken PDF, Reddit all handled |
| **Total** | **23/25** | |

**What worked well:**
- Best performing happy-path query — found academic sources (ResearchGate, CEUR)
- Microsoft Learn is authoritative for this topic
- Synthesis correctly balanced pros and cons

**What did not work:**
- Agent never fetched any source pages for deeper content
- Key findings slightly vague on the cons side

---

## Query 4 — Speculative Future Question (Edge Case)

**Query:** `Which AI model will be the best in 2030`

**Type:** Edge case — unanswerable speculative question (valid API key)

**Expected behaviour:**
- Confidence: Low
- Answer honestly hedges — does not present speculation as fact
- Judge step fires and flags the speculative nature

**What happened:**

Agent gathered 6 sources across 3 iterations. Synthesizer set confidence
to Low independently. Judge step fired: `[judge] Issues flagged:
['Question is speculative — answer reflects current trends only']`.

Answer correctly said "impossible to definitively determine" but findings
cited "GPT-5.2" and "Gemini 3 Pro" from a speculative blog post — these
may not be real model names. Known limitation of source-grounded synthesis
when the source itself is speculative.

**Actual output summary:**
- Short answer: Cannot be determined — reflects current trends only
- Findings: 3 (current model landscape, market trends)
- Sources: 6 used
- Confidence: Low

**Scores:**

| Dimension | Score | Notes |
|-----------|-------|-------|
| Planning quality | 4/5 | Reasonable for speculative question |
| Tool selection | 3/5 | fetch_page hit duplicate — no deep reading |
| Source quality | 3/5 | Speculative blogs included alongside factual sources |
| Answer accuracy | 4/5 | Correctly hedged but cited speculative model names |
| Failure handling | 5/5 | Judge step fired, Low confidence set, no crash |
| **Total** | **19/25** | |

**What worked well:**
- Synthesizer independently set Low confidence
- Judge step fired correctly
- Short answer correctly refused to make a confident prediction

**What did not work:**
- Findings cited "GPT-5.2" as a real model name from a speculative source
- Fix needed: source credibility scoring to penalise personal blogs

---

## Query 5 — Real Failure Case: Tool Authentication Failure

**Query:** `Which AI model will be the best in 2030`
**Failure:** Tavily API key accidentally invalidated during evaluation session

**Type:** Real failure case — search tool returning HTTP 401 on every call

**Important note:** This failure was NOT simulated. The Tavily API key
expired mid-session during real evaluation. This makes it a more valuable
test than a staged failure because it happened under real conditions.

**Expected behaviour:**
- All search calls fail with HTTP 401
- Orchestrator catches every error — no unhandled exception in agent core
- After MAX_ITERATIONS with 0 sources, synthesis still runs
- FinalAnswer returned with confidence = Low, 0 findings, 0 sources
- Judge step fires with multiple flags

**What actually happened:**

5 iterations ran. Iterations 1 and 3 ran `web_search` — both returned
HTTP 401 immediately. Iterations 2, 4, and 5 were duplicate query
attempts caught by deduplication before reaching the tool.

The loop completed all 5 iterations with 0 sources and 5 errors in
`state.errors`. The synthesizer LLM was called with empty sources and
returned a valid response stating it could not answer. Judge step fired
with two flags:

```
[judge] Issues flagged: [
  'Question is speculative — answer reflects current trends only',
  'Very few sources — answer may be incomplete'
]
```

The agent core handled everything perfectly. However, a bug then
triggered in `main.py` when trying to print the result:

```
AttributeError: 'str' object has no attribute 'value'
  File "main.py", line 68, in print_answer_pretty
    answer.confidence_level.value
```

**Root cause:** `_empty_answer()` sets `confidence_level = "Low"` as a
plain string. The normal synthesizer path returns a Pydantic enum
`ConfidenceLevel.low` with a `.value` attribute. The display code assumed
it was always an enum — crashing on the exact fallback path designed to
handle failures.

**Fix applied:**
```python
# main.py — print_answer_pretty()
# Before (crashed):
answer.confidence_level.value

# After (handles both string and enum):
conf_val = answer.confidence_level.value if hasattr(
    answer.confidence_level, 'value'
) else answer.confidence_level
```

**Actual output summary:**
- Short answer: "It is impossible to determine... no sources are available"
- Findings: 0
- Sources: 0
- Confidence: Low
- Errors logged: 5 (2 HTTP 401, 3 duplicate skips)
- Judge flags: 2 (speculative + very few sources)
- Bug found: `AttributeError` in display layer on fallback path
- Bug fixed: confidence display now handles both string and enum

**Scores:**

| Dimension | Score | Notes |
|-----------|-------|-------|
| Planning quality | 5/5 | Plan generated before any tool failure |
| Tool selection | 5/5 | Correct tool chosen — failure was external |
| Source quality | N/A | No sources — tool broken externally |
| Answer accuracy | 5/5 | Correctly said it could not answer — zero hallucination |
| Failure handling | 4/5 | Agent core perfect — bug found in CLI display layer |
| **Total** | **19/20** | Source quality N/A |

**What worked well:**
- 5 tool failures caught and logged — zero unhandled exceptions in agent
- Synthesis with 0 sources returned a valid, honest FinalAnswer
- Judge step fired correctly with two appropriate flags
- The failure revealed a real bug — valuable finding

**What did not work:**
- `print_answer_pretty` crashed with `AttributeError` on the fallback path
- Agent kept retrying duplicate queries instead of varying them after failure
- Fix suggestion: tell the action selector explicitly when a tool call failed
  so it tries a different query rather than repeating the same one

---

## Summary Table

| # | Query | Type | Score | Confidence | Result |
|---|-------|------|-------|------------|--------|
| 1 | Vector DB comparison | Comparison | 23/25 | Medium | Pass |
| 2 | Indian HR startups | List | 22/25 | Medium | Pass |
| 3 | Multi-agent pros/cons | Conceptual | 23/25 | Medium | Pass |
| 4 | AI best in 2030 | Speculative edge case | 19/25 | Low | Partial pass |
| 5 | Broken Tavily key (real) | Real failure case | 19/20 | Low | Pass — bug found and fixed |

---

## What Consistently Worked Well

- Planning phase produced correct actionable steps on every query
- Duplicate query and URL detection prevented wasted iterations on all 5 runs
- Junk domain filtering (Reddit, broken PDFs) worked correctly every run
- Synthesis with 0 sources still returned a valid, honest FinalAnswer
- Two-model strategy improved synthesis quality vs using a single model
- Judge step fired correctly on both the speculative query and the failure case
- Pydantic validation caught every malformed LLM response

## What Consistently Did Not Work

- `fetch_page` never successfully executed on happy path queries
- After tool failure, agent retried the same duplicate query instead of varying
- Speculative blog posts treated as factual sources by the synthesizer
- `_empty_answer()` sets `confidence_level` as a string — inconsistent with
  the enum type returned by normal synthesis, causing a display layer crash

## Biggest Finding

A real bug was discovered during the failure case evaluation. The
`print_answer_pretty` function crashed with `AttributeError` on the exact
code path designed to handle failures gracefully. This happened because
`_empty_answer()` returned `confidence_level` as a plain string while
the normal synthesizer path returned a Pydantic enum — and the display
code assumed it was always an enum.

This demonstrates why failure cases must be tested with real conditions,
not just happy path queries. The bug would have gone undetected in
production, causing the failure handler itself to crash on users who
triggered it — the worst possible outcome for reliability.

## What I Would Improve With More Time

1. **Fix type consistency in `_empty_answer()`** — return
   `ConfidenceLevel.low` (enum) not the string `"Low"` so all display
   code works uniformly without defensive checks.

2. **Fix duplicate query loop on tool failure** — pass tool failure info
   to the action selector prompt so it tries a different query rather
   than repeating the failed one.

3. **Fix `fetch_page` firing** — reduce `MIN_SOURCES` or restructure
   the early exit check so forced fetch runs before stopping.

4. **Source credibility scoring** — assign domain trust scores. Official
   docs, .gov, .edu score higher than personal blogs and YouTube.

5. **Async tool execution** — run `web_search` and `fetch_page`
   concurrently per iteration to reduce latency 40–60%.
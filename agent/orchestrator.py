# agent/orchestrator.py
import logging
from schemas import AgentState, ToolName, FinalAnswer
from agent.prompts import (
    PLANNER_SYSTEM, build_planner_prompt,
    ACTION_SYSTEM,  build_action_prompt,
    SYNTHESIS_SYSTEM, build_synthesis_prompt,
)
from agent.llm import call_planner, call_action_selector, call_synthesizer
from tools.search import web_search
from tools.scraper import fetch_page

logger = logging.getLogger(__name__)

MAX_ITERATIONS  = 5
MIN_SOURCES     = 3


# ── Entry point ────────────────────────────────────────────────────────────────

def run_agent(question: str) -> FinalAnswer:
    """
    Full ReAct loop:
      1. Plan  — LLM produces a research plan
      2. Act   — LLM picks a tool, tool runs, results collected
      3. (repeat Act until DONE or MAX_ITERATIONS)
      4. Synthesize — LLM writes the final structured answer

    Always returns a FinalAnswer — never raises to the caller.
    Failures are captured in state.errors and reflected in confidence_level.
    """
    logger.info(f"[agent] Starting research for: '{question}'")
    state = AgentState(question=question)

    # ── Phase 1: Plan ──────────────────────────────────────────────────────────
    state = _run_planning(state)

    # ── Phase 2: ReAct loop ────────────────────────────────────────────────────
    state = _run_react_loop(state)

    # ── Phase 3: Synthesize ────────────────────────────────────────────────────
    return _run_synthesis(state)


# ── Phase 1: Planning ──────────────────────────────────────────────────────────

def _run_planning(state: AgentState) -> AgentState:
    logger.info("[agent] Phase 1: Planning")
    try:
        plan = call_planner(
            system_prompt=PLANNER_SYSTEM,
            user_prompt=build_planner_prompt(state.question),
        )
        state.plan = plan
        logger.info(f"[agent] Plan ready — {len(plan.steps)} steps: {plan.steps}")

    except Exception as e:
        # planning failure is non-fatal — agent can still attempt research
        # without a formal plan, action selector will do its best
        err = f"Planning failed: {e}"
        logger.warning(f"[agent] {err} — continuing without plan")
        state.errors.append(err)

    return state


# ── Phase 2: ReAct loop ────────────────────────────────────────────────────────

def _run_react_loop(state: AgentState) -> AgentState:
    logger.info("[agent] Phase 2: ReAct loop")

    visited_urls    = set()
    used_queries    = set()
    fetch_page_used = False   # track if we've gone deep on any URL

    while state.iterations < MAX_ITERATIONS:
        state.iterations += 1
        logger.info(
            f"[agent] Iteration {state.iterations}/{MAX_ITERATIONS} "
            f"— sources so far: {len(state.gathered_info)}"
        )

        try:
            decision = call_action_selector(
                system_prompt=ACTION_SYSTEM,
                user_prompt=build_action_prompt(state),
            )
        except Exception as e:
            err = f"Action selector failed on iteration {state.iterations}: {e}"
            logger.error(f"[agent] {err}")
            state.errors.append(err)
            continue

        logger.info(
            f"[agent] Decision: action={decision.action} "
            f"query={decision.query!r} url={decision.url!r}"
        )

        # if agent wants DONE but never used fetch_page, force one fetch first
        if decision.action == ToolName.done:
            if not fetch_page_used and state.gathered_info:
                logger.info("[agent] DONE requested but no fetch_page used — forcing one fetch")
                best_url = _pick_best_url(state.gathered_info, visited_urls)
                if best_url:
                    state = _handle_fetch_page(
                        state,
                        _make_fetch_decision(best_url),
                        visited_urls,
                    )
                    fetch_page_used = True
                    continue
            logger.info(f"[agent] DONE — reason: {decision.reasoning}")
            break

        elif decision.action == ToolName.web_search:
            state = _handle_web_search(state, decision, used_queries, visited_urls)

        elif decision.action == ToolName.fetch_page:
            state = _handle_fetch_page(state, decision, visited_urls)
            fetch_page_used = True

        else:
            err = f"Unknown action '{decision.action}' on iteration {state.iterations}"
            logger.warning(f"[agent] {err}")
            state.errors.append(err)

        # inside _run_react_loop, replace the early exit block at the bottom with this:

        if len(state.gathered_info) >= MIN_SOURCES and state.iterations >= 3:
            if not fetch_page_used and state.gathered_info:
                best_url = _pick_best_url(state.gathered_info, visited_urls)
                if best_url:
                    logger.info("[agent] Forcing fetch_page before stopping")
                    state = _handle_fetch_page(
                        state,
                        _make_fetch_decision(best_url),
                        visited_urls,
                    )
                    fetch_page_used = True
                    # don't break here — let it loop once more then stop
                    continue   # <-- key change: continue not break
            logger.info(
                f"[agent] Sufficient sources ({len(state.gathered_info)}) "
                f"after {state.iterations} iterations — stopping"
            )
            break

    logger.info(
        f"[agent] ReAct loop complete — "
        f"{state.iterations} iterations, {len(state.gathered_info)} sources, "
        f"{len(state.errors)} errors"
    )
    return state


def _pick_best_url(gathered: list[dict], visited_urls: set) -> str | None:
    """Pick the highest-value unvisited URL from gathered sources."""
    PRIORITY_DOMAINS = [
        "tracxn.com", "crunchbase.com", "yourstory.com", "inc42.com",
        "techcrunch.com", "forbes.com", "dev.to", "zendesk.com",
        "microsoft.com", "google.com", "github.com",
    ]
    for domain in PRIORITY_DOMAINS:
        for item in gathered:
            url = item.get("url", "")
            if domain in url and url not in visited_urls:
                return url
    # fallback: first unvisited URL
    for item in gathered:
        url = item.get("url", "")
        if url and url not in visited_urls:
            return url
    return None


def _make_fetch_decision(url: str):
    """Create a minimal ToolDecision-like object for forced fetch calls."""
    from schemas import ToolDecision, ToolName
    return ToolDecision(
        action=ToolName.fetch_page,
        query=None,
        url=url,
        reasoning="Forced fetch to get deeper content from best available source",
    )


# ── Tool handlers ──────────────────────────────────────────────────────────────

def _handle_web_search(
    state: AgentState,
    decision,
    used_queries: set,
    visited_urls: set,
) -> AgentState:

    query = (decision.query or "").strip()

    if not query:
        err = f"Iteration {state.iterations}: web_search called with no query"
        logger.warning(f"[agent] {err}")
        state.errors.append(err)
        return state

    if query.lower() in used_queries:
        err = f"Iteration {state.iterations}: duplicate query skipped — '{query}'"
        logger.warning(f"[agent] {err}")
        state.errors.append(err)
        return state

    used_queries.add(query.lower())

    try:
        results = web_search(query)

        if not results:
            logger.warning(f"[agent] web_search returned no results for '{query}'")
            state.errors.append(f"No results for query: '{query}'")
            return state

        new_count = 0
        for r in results:
            url = r.get("url", "")
            if url and url not in visited_urls:
                state.gathered_info.append(r)
                visited_urls.add(url)
                new_count += 1

        logger.info(
            f"[agent] web_search '{query}' → "
            f"{len(results)} results, {new_count} new"
        )

    except TimeoutError as e:
        err = f"Iteration {state.iterations}: search timeout — {e}"
        logger.error(f"[agent] {err}")
        state.errors.append(err)

    except RuntimeError as e:
        err = f"Iteration {state.iterations}: search error — {e}"
        logger.error(f"[agent] {err}")
        state.errors.append(err)

    return state


def _handle_fetch_page(
    state: AgentState,
    decision,
    visited_urls: set,
) -> AgentState:

    url = (decision.url or "").strip()

    if not url:
        err = f"Iteration {state.iterations}: fetch_page called with no URL"
        logger.warning(f"[agent] {err}")
        state.errors.append(err)
        return state

    if url in visited_urls:
        err = f"Iteration {state.iterations}: duplicate URL skipped — {url}"
        logger.warning(f"[agent] {err}")
        state.errors.append(err)
        return state

    visited_urls.add(url)

    # fetch_page never raises — always returns a status dict
    result = fetch_page(url)

    if result["status"] != "ok":
        err = (
            f"Iteration {state.iterations}: "
            f"fetch_page failed for {url} — {result['status']}"
        )
        logger.warning(f"[agent] {err}")
        state.errors.append(err)
        return state

    state.gathered_info.append(result)
    logger.info(
        f"[agent] fetch_page {url} → "
        f"{len(result.get('content', ''))} chars"
    )

    return state


# ── Phase 3: Synthesis ─────────────────────────────────────────────────────────

def _judge_answer(answer: FinalAnswer, question: str) -> FinalAnswer:
    """
    Simple rule-based judge that catches obvious quality issues
    without needing an extra LLM call.
    """
    issues = []

    # check: list questions should have enough findings
    q = question.lower()
    if "5" in q and len(answer.key_findings) < 3:
        issues.append("Fewer findings than requested — sources were insufficient")
        answer.confidence_level = "Low"

    # check: future/speculative questions should be Low confidence
    speculative_words = ["2030", "2035", "future", "will be", "predict", "forecast"]
    if any(w in q for w in speculative_words):
        if answer.confidence_level.value == "High":
            logger.info("[judge] Downgrading confidence: speculative question")
            answer.confidence_level = "Medium"
        issues.append("Question is speculative — answer reflects current trends only")

    # check: too few sources
    if len(answer.sources) < 2:
        issues.append("Very few sources — answer may be incomplete")
        answer.confidence_level = "Low"

    if issues:
        answer.limitations = list(set(answer.limitations + issues))
        logger.info(f"[judge] Issues flagged: {issues}")

    return answer

def _run_synthesis(state: AgentState) -> FinalAnswer:
    quality_sources = _filter_quality_sources(state.gathered_info)
    logger.info(
        f"[agent] Phase 3: Synthesis — "
        f"{len(quality_sources)}/{len(state.gathered_info)} quality sources"
    )

    original             = state.gathered_info
    state.gathered_info  = quality_sources

    try:
        answer = call_synthesizer(
            system_prompt=SYNTHESIS_SYSTEM,
            user_prompt=build_synthesis_prompt(state),
        )
        answer = _judge_answer(answer, state.question)  # <-- add this line
        logger.info(
            f"[agent] Synthesis complete — "
            f"confidence={answer.confidence_level}, "
            f"findings={len(answer.key_findings)}, "
            f"sources={len(answer.sources)}"
        )
        return answer
    except Exception as e:
        logger.error(f"[agent] Synthesis failed: {e}")
        return _empty_answer(state, reason=str(e))
    finally:
        state.gathered_info = original

def _empty_answer(state: AgentState, reason: str = "") -> FinalAnswer:
    """
    Fallback answer when synthesis fails or no sources were gathered.
    Always returns a valid FinalAnswer so main.py never crashes.
    """
    return FinalAnswer(
        question=state.question,
        short_answer="The agent was unable to produce an answer due to errors during research.",
        key_findings=[],
        sources=[],
        confidence_level="Low",
        confidence_reasoning=f"Research or synthesis failed. Reason: {reason or 'unknown'}",
        limitations=[
            "No sources were successfully gathered or synthesized.",
            f"Errors encountered: {'; '.join(state.errors) if state.errors else 'none logged'}",
        ],
        assumptions=[],
        suggested_next_steps=[
            "Check your API keys in .env",
            "Run python tools/search.py to verify Tavily is working",
            "Run python agent/llm.py to verify OpenRouter is working",
            "Check agent.log for detailed error traces",
        ],
    )

# replace _filter_quality_sources entirely
def _filter_quality_sources(gathered: list[dict], min_length: int = 150) -> list[dict]:
    """
    Filter weak sources but be lenient — search snippets are naturally short.
    Only drop sources that are truly empty or useless (social media, login walls).
    """
    JUNK_DOMAINS = [
        "instagram.com", "facebook.com", "twitter.com", "x.com","linkedin.com/posts",
        "linkedin.com/feed", "reddit.com/r/", "quora.com",
        "trustpilot.com", "yelp.com",
    ]

    quality = []
    for item in gathered:
        url     = item.get("url", "")
        content = item.get("content") or item.get("snippet", "")

        # drop social/junk domains
        if any(junk in url for junk in JUNK_DOMAINS):
            logger.info(f"[agent] Dropping junk domain: {url}")
            continue

        # drop truly empty sources
        if len(content.strip()) < min_length:
            logger.info(f"[agent] Dropping empty source: {url}")
            continue

        quality.append(item)

    # always keep at least 3 sources even if all are borderline
    return quality if len(quality) >= 3 else gathered[:3]
# tools/search.py
import os
import logging
import requests
from dotenv import load_dotenv
from schemas import Source

load_dotenv()
logger = logging.getLogger(__name__)

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TAVILY_URL = "https://api.tavily.com/search"
DEFAULT_TIMEOUT = 10
MAX_RESULTS = 5
MIN_CONTENT_LENGTH = 100


def web_search(query: str, max_results: int = MAX_RESULTS) -> list[dict]:
    """
    Search the web using Tavily API.
    Returns raw results for the orchestrator to work with.
    Raises on total failure so the orchestrator can catch and log it.
    """
    if not TAVILY_API_KEY:
        raise EnvironmentError("TAVILY_API_KEY is not set in your .env file")

    if not query or not query.strip():
        logger.warning("web_search called with empty query — skipping")
        return []

    logger.info(f"[search] query='{query}' max_results={max_results}")

    try:
        response = requests.post(
            TAVILY_URL,
            json={
                "api_key": TAVILY_API_KEY,
                "query": query.strip(),
                "max_results": max_results,
                "search_depth": "basic",
                "include_answer": False,
                "include_raw_content": False,
            },
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()

    except requests.Timeout:
        logger.error(f"[search] Timeout after {DEFAULT_TIMEOUT}s for query='{query}'")
        raise TimeoutError(f"Tavily search timed out for query: '{query}'")

    except requests.HTTPError as e:
        logger.error(f"[search] HTTP error {response.status_code}: {e}")
        raise RuntimeError(f"Tavily returned HTTP {response.status_code}: {e}")

    except requests.RequestException as e:
        logger.error(f"[search] Network error: {e}")
        raise RuntimeError(f"Network error during search: {e}")

    raw = response.json()
    results = raw.get("results", [])

    if not results:
        logger.warning(f"[search] No results returned for query='{query}'")
        return []

    filtered = _filter_results(results)
    logger.info(f"[search] {len(results)} results returned, {len(filtered)} passed filter")

    return filtered


def _filter_results(results: list[dict]) -> list[dict]:
    """
    Drop results that are too short to be useful.
    Keeps the orchestrator from wasting synthesis tokens on junk.
    """
    cleaned = []
    for r in results:
        content = r.get("content", "") or ""
        if len(content.strip()) < MIN_CONTENT_LENGTH:
            logger.debug(f"[search] Dropping weak result: {r.get('url', 'unknown url')}")
            continue
        cleaned.append({
            "url": r.get("url", ""),
            "title": r.get("title", "Untitled"),
            "snippet": content.strip(),
        })
    return cleaned


def results_to_sources(results: list[dict]) -> list[Source]:
    """
    Convert raw search results into Source objects.
    Relevance score defaults to 0.7 here — the LLM re-scores
    during synthesis based on actual usefulness.
    """
    sources = []
    for r in results:
        try:
            sources.append(Source(
                url=r["url"],
                title=r["title"],
                snippet=r["snippet"][:500],  # cap snippet length
                relevance_score=0.7,
            ))
        except Exception as e:
            logger.warning(f"[search] Could not convert result to Source: {e}")
            continue
    return sources


# ── quick manual test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_query = "open source vector databases for RAG 2024"
    print(f"\nTesting search for: '{test_query}'\n")
    try:
        results = web_search(test_query)
        for i, r in enumerate(results, 1):
            print(f"[{i}] {r['title']}")
            print(f"    {r['url']}")
            print(f"    {r['snippet'][:120]}...")
            print()
    except Exception as e:
        print(f"Search failed: {e}")
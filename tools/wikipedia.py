# tools/wikipedia.py
import logging
import requests

logger = logging.getLogger(__name__)

WIKIPEDIA_API = "https://en.wikipedia.org/api/rest_v1/page/summary/"

def search_wikipedia(query: str) -> dict:
    """
    Fetch a Wikipedia summary for conceptual/definitional queries.
    Never raises — returns error dict on failure.
    """
    try:
        # convert query to title format
        title = query.strip().replace(" ", "_")
        response = requests.get(
            f"{WIKIPEDIA_API}{title}",
            timeout=8,
            headers={"User-Agent": "research-agent/1.0"}
        )
        response.raise_for_status()
        data = response.json()

        return {
            "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
            "title": data.get("title", "Wikipedia"),
            "snippet": data.get("extract", "")[:800],
            "status": "ok",
            "source_type": "wikipedia"
        }
    except Exception as e:
        logger.warning(f"[wikipedia] Failed for '{query}': {e}")
        return {"url": "", "title": "", "snippet": "", "status": f"error: {e}", "source_type": "wikipedia"}
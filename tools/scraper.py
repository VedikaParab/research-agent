# tools/scraper.py
import logging
import httpx
from bs4 import BeautifulSoup
from schemas import Source

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT  = 8
MAX_CONTENT_CHARS = 3000
MIN_CONTENT_LENGTH = 100

BLOCKED_EXTENSIONS = (
    ".pdf", ".docx", ".xlsx", ".pptx",
    ".jpg", ".jpeg", ".png", ".gif", ".svg",
    ".mp4", ".mp3", ".zip", ".exe",
)

JUNK_TAGS = [
    "script", "style", "nav", "footer", "header",
    "aside", "form", "noscript", "iframe", "ads",
]


def fetch_page(url: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """
    Fetch and clean a web page. Always returns a dict — never raises.
    The orchestrator checks result["status"] to decide if it's usable.
    """
    if not url or not url.strip():
        logger.warning("[scraper] fetch_page called with empty URL")
        return _error_result(url, "Empty URL provided")

    if _is_blocked_extension(url):
        logger.warning(f"[scraper] Skipping non-HTML file: {url}")
        return _error_result(url, f"Skipped: unsupported file type")

    logger.info(f"[scraper] Fetching: {url}")

    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (research-agent/1.0)"},
        ) as client:
            response = client.get(url)
            response.raise_for_status()

    except httpx.TimeoutException:
        logger.warning(f"[scraper] Timeout after {timeout}s: {url}")
        return _error_result(url, f"Timeout after {timeout}s")

    except httpx.HTTPStatusError as e:
        logger.warning(f"[scraper] HTTP {e.response.status_code}: {url}")
        return _error_result(url, f"HTTP {e.response.status_code}")

    except httpx.RequestError as e:
        logger.warning(f"[scraper] Network error for {url}: {e}")
        return _error_result(url, f"Network error: {type(e).__name__}")

    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type:
        logger.warning(f"[scraper] Non-HTML content-type '{content_type}': {url}")
        return _error_result(url, f"Non-HTML content-type: {content_type}")

    cleaned = _extract_text(response.text)

    if len(cleaned) < MIN_CONTENT_LENGTH:
        logger.warning(f"[scraper] Content too short ({len(cleaned)} chars): {url}")
        return _error_result(url, "Page content too short to be useful")

    title = _extract_title(response.text)

    logger.info(f"[scraper] Success: {len(cleaned)} chars extracted from {url}")

    return {
        "url": url,
        "title": title,
        "content": cleaned,
        "status": "ok",
    }


def _extract_text(html: str) -> str:
    """
    Strip junk tags, extract clean text, collapse whitespace.
    """
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(JUNK_TAGS):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)

    # collapse multiple spaces and newlines
    import re
    text = re.sub(r"\s+", " ", text).strip()

    return text[:MAX_CONTENT_CHARS]


def _extract_title(html: str) -> str:
    """
    Pull the <title> tag. Falls back to 'Untitled' if missing.
    """
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("title")
    if tag and tag.string:
        return tag.string.strip()[:120]
    return "Untitled"


def _is_blocked_extension(url: str) -> bool:
    """
    Bail early on non-HTML file types before making an HTTP request.
    """
    lowered = url.lower().split("?")[0]  # strip query params before checking
    return any(lowered.endswith(ext) for ext in BLOCKED_EXTENSIONS)


def _error_result(url: str, reason: str) -> dict:
    """
    Consistent error shape so orchestrator always gets the same dict structure.
    """
    return {
        "url": url,
        "title": "Error",
        "content": "",
        "status": f"error: {reason}",
    }


def fetch_page_as_source(url: str) -> Source | None:
    """
    Convenience wrapper — fetches a page and converts it directly
    to a Source object. Returns None if the fetch failed.
    """
    result = fetch_page(url)

    if result["status"] != "ok":
        logger.warning(f"[scraper] Skipping failed fetch for source: {url}")
        return None

    try:
        return Source(
            url=result["url"],
            title=result["title"],
            snippet=result["content"][:500],
            relevance_score=0.6,
        )
    except Exception as e:
        logger.warning(f"[scraper] Could not build Source from {url}: {e}")
        return None


# ── quick manual test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_url = "https://www.trychroma.com"
    print(f"\nTesting scraper for: {test_url}\n")
    result = fetch_page(test_url)
    print(f"Status : {result['status']}")
    print(f"Title  : {result['title']}")
    print(f"Content: {result['content'][:300]}...")
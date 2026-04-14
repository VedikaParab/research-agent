# sanitization.py
import re
import html
from urllib.parse import urlparse

DANGEROUS_SCHEMES = {"javascript", "data", "vbscript"}

INJECTION_PATTERNS = [
    r"ignore\s+previous\s+instructions",
    r"disregard\s+all\s+prior",
    r"system\s*prompt",
    r"you\s+are\s+now",
    r"<\s*script",
    r"DROP\s+TABLE",
    r"SELECT\s+\*\s+FROM",
]

def sanitize_text(text: str, max_length: int = 1000) -> str:
    """
    Strip HTML tags, unescape entities, remove control characters.
    Safe to use on LLM output and scraped content before rendering.
    """
    if not text:
        return ""
    # unescape HTML entities first
    text = html.unescape(text)
    # strip HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # remove control characters except newline and tab
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_length]


def sanitize_url(url: str) -> str:
    """
    Reject dangerous URL schemes. Return empty string if unsafe.
    """
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme.lower() in DANGEROUS_SCHEMES:
            return ""
        return url.strip()
    except Exception:
        return ""


def sanitize_question(question: str) -> tuple[bool, str]:
    """
    Returns (is_safe, cleaned_question_or_reason).
    If unsafe, second element is the reason. If safe, it's the cleaned question.
    """
    lowered = question.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lowered, re.IGNORECASE):
            return False, f"Injection pattern detected: {pattern}"
    return True, question.strip()

def is_safe_question(question: str) -> bool:
    """Convenience wrapper — orchestrator uses this for the safety gate."""
    safe, _ = sanitize_question(question)
    return safe

def sanitize_gathered(gathered: list[dict]) -> list[dict]:
    """
    Sanitize all text fields in gathered sources before synthesis.
    """
    clean = []
    for item in gathered:
        clean.append({
            "url": sanitize_url(item.get("url", "")),
            "title": sanitize_text(item.get("title", ""), max_length=200),
            "snippet": sanitize_text(item.get("content") or item.get("snippet", ""), max_length=800),
            "status": item.get("status", "ok"),
        })
    return clean
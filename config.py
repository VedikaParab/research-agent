# config.py
import os
from dotenv import load_dotenv

load_dotenv()

def _as_int(key: str, default: int, min_val: int, max_val: int) -> int:
    try:
        val = int(os.getenv(key, default))
        return max(min_val, min(max_val, val))
    except (ValueError, TypeError):
        return default

def _as_float(key: str, default: float, min_val: float, max_val: float) -> float:
    try:
        val = float(os.getenv(key, default))
        return max(min_val, min(max_val, val))
    except (ValueError, TypeError):
        return default

def get_required(key: str) -> str:
    val = os.getenv(key, "").strip()
    if not val:
        raise EnvironmentError(
            f"\n\nMissing required environment variable: {key}\n"
            f"Copy .env.example to .env and fill in your API keys.\n"
            f"Get Groq free at: https://console.groq.com\n"
            f"Get Tavily free at: https://tavily.com\n"
        )
    return val

def validate_or_raise():
    """Call at app startup before serving any requests."""
    get_required("GROQ_API_KEY")
    get_required("TAVILY_API_KEY")

# config values with safe defaults
MAX_ITERATIONS  = _as_int("MAX_ITERATIONS", 5, 1, 10)
MIN_SOURCES     = _as_int("MIN_SOURCES", 3, 1, 10)
REQUEST_TIMEOUT = _as_int("REQUEST_TIMEOUT", 30, 5, 120)
MAX_TOKENS      = _as_int("MAX_TOKENS", 1500, 500, 4000)
LLM_TEMPERATURE = _as_float("LLM_TEMPERATURE", 0.2, 0.0, 1.0)
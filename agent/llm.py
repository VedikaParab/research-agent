# agent/llm.py
import os
import re
import json
import time
import logging
from dotenv import load_dotenv
from openai import OpenAI
from schemas import ResearchPlan, ToolDecision, FinalAnswer

load_dotenv()
logger = logging.getLogger(__name__)

# ── CONFIG ─────────────────────────────────────────────────────────────

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

MODEL         = "llama-3.1-8b-instant"    # fast, used for planning + action
MODEL_LARGE   = "llama-3.3-70b-versatile" # stronger, used for synthesis only # fast + free + reliable

MAX_RETRIES = 3
BASE_BACKOFF = 2
MAX_TOKENS = 1500

# ── CLIENT ─────────────────────────────────────────────────────────────

if not GROQ_API_KEY:
    raise EnvironmentError("GROQ_API_KEY not set in .env")

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# ── CORE LLM CALL ─────────────────────────────────────────────────────
def call_llm(system_prompt: str, user_prompt: str, model: str = MODEL) -> str:
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"[llm] Attempt {attempt}/{MAX_RETRIES} — model={model}")

            response = client.chat.completions.create(
                model=model,
                max_tokens=MAX_TOKENS,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

            content = response.choices[0].message.content

            if not content or not content.strip():
                raise ValueError("Empty response from LLM")

            logger.info(f"[llm] Success — {len(content)} chars")
            return content.strip()

        except Exception as e:
            last_error = str(e)
            logger.warning(f"[llm] Attempt {attempt} failed: {e}")

            if attempt < MAX_RETRIES:
                wait = BASE_BACKOFF ** attempt
                logger.info(f"[llm] Waiting {wait}s before retry...")
                time.sleep(wait)

    raise RuntimeError(
        f"LLM call failed after {MAX_RETRIES} attempts. Last error: {last_error}"
    )

# ── SAFE JSON PARSER ───────────────────────────────────────────────────

def parse_json_safely(text: str) -> dict:
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except:
            pass

    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except:
            pass

    logger.error(f"[llm] JSON parse failed:\n{text[:300]}")
    raise ValueError("No valid JSON found")

# ── TYPED CALLERS ──────────────────────────────────────────────────────

def call_planner(system_prompt: str, user_prompt: str) -> ResearchPlan:
    raw = call_llm(system_prompt, user_prompt)

    try:
        data = parse_json_safely(raw)
        plan = ResearchPlan(**data)
        logger.info(f"[llm] Plan parsed — {len(plan.steps)} steps")
        return plan

    except Exception as e:
        logger.error(f"[llm] Planner failed: {e}\nRaw: {raw[:300]}")
        raise RuntimeError(f"Invalid planner output: {e}")

def call_action_selector(system_prompt: str, user_prompt: str) -> ToolDecision:
    raw = call_llm(system_prompt, user_prompt)

    try:
        data = parse_json_safely(raw)
        decision = ToolDecision(**data)
        logger.info(f"[llm] Action selected: {decision.action}")
        return decision

    except Exception as e:
        logger.error(f"[llm] Action selector failed: {e}\nRaw: {raw[:300]}")
        raise RuntimeError(f"Invalid action output: {e}")

def call_synthesizer(system_prompt: str, user_prompt: str) -> FinalAnswer:
    raw = call_llm(system_prompt, user_prompt, model=MODEL_LARGE)
    try:
        data   = parse_json_safely(raw)
        answer = FinalAnswer(**data)
        logger.info(f"[llm] Final parsed — confidence={answer.confidence_level}")
        return answer
    except Exception as e:
        logger.error(f"[llm] Synthesizer failed: {e}\nRaw: {raw[:300]}")
        raise RuntimeError(f"Invalid final output: {e}")

# ── TEST ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("\nTesting LLM...\n")

    try:
        result = call_llm(
            system_prompt="You are a helpful assistant. Respond with only valid JSON.",
            user_prompt='Return this exact JSON: {"status": "ok", "message": "Groq working"}',
        )
        print("Raw:", result)
        print("Parsed:", parse_json_safely(result))

    except Exception as e:
        print(f"Test failed: {e}")
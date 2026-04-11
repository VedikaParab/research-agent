# main.py
import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime

from agent.orchestrator import run_agent
from schemas import FinalAnswer


# ── Logging setup ──────────────────────────────────────────────────────────────

def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file   = log_dir / f"agent_{timestamp}.log"

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),   # logs to stderr, answer to stdout
        ],
    )
    logging.info(f"Logging to {log_file}")


# ── Output formatters ──────────────────────────────────────────────────────────

def print_answer_pretty(answer: FinalAnswer) -> None:
    """Human-readable output for terminal use."""
    SEP  = "─" * 60
    SEP2 = "═" * 60

    print(f"\n{SEP2}")
    print("  RESEARCH AGENT — FINAL ANSWER")
    print(f"{SEP2}\n")

    print(f"QUESTION\n{SEP}")
    print(f"  {answer.question}\n")

    print(f"SHORT ANSWER\n{SEP}")
    print(f"  {answer.short_answer}\n")

    print(f"KEY FINDINGS\n{SEP}")
    for i, finding in enumerate(answer.key_findings, 1):
        print(f"  {i}. {finding}")
    print()

    print(f"SOURCES  ({len(answer.sources)} used)\n{SEP}")
    for src in answer.sources:
        bar   = _relevance_bar(src.relevance_score)
        score = f"{src.relevance_score:.1f}"
        print(f"  [{score}] {bar}  {src.title}")
        print(f"         {src.url}")
        if src.snippet:
            preview = src.snippet[:120].replace("\n", " ")
            print(f"         \"{preview}...\"")
        print()

    conf_val = answer.confidence_level.value if hasattr(answer.confidence_level, 'value') else answer.confidence_level
    confidence_icon = {"High": "✓", "Medium": "~", "Low": "✗"}.get(conf_val, "?")
    print(f"CONFIDENCE\n{SEP}")
    print(f"  {confidence_icon}  {conf_val}")
    print(f"     {answer.confidence_reasoning}\n")

    if answer.limitations:
        print(f"LIMITATIONS\n{SEP}")
        for lim in answer.limitations:
            print(f"  • {lim}")
        print()

    if answer.assumptions:
        print(f"ASSUMPTIONS\n{SEP}")
        for assumption in answer.assumptions:
            print(f"  • {assumption}")
        print()

    if answer.suggested_next_steps:
        print(f"SUGGESTED NEXT STEPS\n{SEP}")
        for step in answer.suggested_next_steps:
            print(f"  → {step}")
        print()

    print(SEP2 + "\n")


def print_answer_json(answer: FinalAnswer) -> None:
    """Machine-readable JSON output — useful for piping or saving."""
    print(json.dumps(answer.model_dump(), indent=2))


def _relevance_bar(score: float, width: int = 8) -> str:
    """Tiny ASCII bar chart for relevance score."""
    filled = round(score * width)
    return "[" + "█" * filled + "░" * (width - filled) + "]"


# ── Save output ────────────────────────────────────────────────────────────────

def save_output(answer: FinalAnswer, output_dir: str = "outputs") -> Path:
    """
    Save the answer as a JSON file in outputs/.
    Filename includes a timestamp so repeated runs don't overwrite each other.
    """
    out_dir   = Path(output_dir)
    out_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_q    = answer.question[:40].replace(" ", "_").replace("/", "-")
    filename  = out_dir / f"{timestamp}_{safe_q}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(answer.model_dump(), f, indent=2, ensure_ascii=False)

    logging.info(f"Output saved to {filename}")
    return filename


# ── CLI ────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="research-agent",
        description="AI research agent — answers questions using web search and page fetching.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python main.py "Compare the top 3 open-source vector databases for RAG"
  python main.py "Find 5 Indian B2B SaaS startups in HR tech" --json
  python main.py "Pros and cons of multi-agent architecture" --save --verbose
        """,
    )
    parser.add_argument(
        "question",
        type=str,
        help="The research question to answer",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output the answer as raw JSON instead of formatted text",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save the answer to outputs/ as a JSON file",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    setup_logging(verbose=args.verbose)
    logger = logging.getLogger(__name__)

    question = args.question.strip()
    if not question:
        parser.error("Question cannot be empty.")

    logger.info(f"Question received: '{question}'")
    print(f"\nResearching: {question}", file=sys.stderr)
    print("This may take 30–60 seconds...\n", file=sys.stderr)

    # ── Run the agent ──────────────────────────────────────────────────────────
    try:
        answer = run_agent(question)
    except Exception as e:
        # orchestrator is designed to never raise, but just in case
        logger.critical(f"Unexpected top-level failure: {e}", exc_info=True)
        print(f"\n[ERROR] Agent crashed unexpectedly: {e}", file=sys.stderr)
        print("Check logs/ for the full traceback.", file=sys.stderr)
        sys.exit(1)

    # ── Print output ───────────────────────────────────────────────────────────
    if args.json_output:
        print_answer_json(answer)
    else:
        print_answer_pretty(answer)

    # ── Optionally save ────────────────────────────────────────────────────────
    if args.save:
        saved_path = save_output(answer)
        print(f"Saved to: {saved_path}", file=sys.stderr)

    # ── Exit code reflects confidence ──────────────────────────────────────────
    if answer.confidence_level.value == "Low":
        sys.exit(2)     # low confidence — not a crash, but signal something was wrong


if __name__ == "__main__":
    main()
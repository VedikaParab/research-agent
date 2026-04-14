import pytest
from unittest.mock import patch, MagicMock
from schemas import AgentState, ConfidenceLevel
from agent.orchestrator import _empty_answer, _filter_quality_sources, _judge_answer

def test_empty_answer_returns_valid_schema():
    state = AgentState(question="test question")
    state.errors = ["search failed: HTTP 401"]
    answer = _empty_answer(state, reason="tool failure")
    assert answer.question == "test question"
    assert answer.confidence_level == ConfidenceLevel.low
    assert len(answer.suggested_next_steps) > 0

def test_empty_answer_confidence_is_enum_not_string():
    state = AgentState(question="test")
    answer = _empty_answer(state)
    # this was the real bug found during evaluation
    assert hasattr(answer.confidence_level, 'value')
    assert answer.confidence_level.value == "Low"

def test_filter_drops_junk_domains():
    gathered = [
        {"url": "https://instagram.com/post/123", "content": "x" * 200, "title": "t", "snippet": ""},
        {"url": "https://techcrunch.com/article", "content": "x" * 200, "title": "t", "snippet": ""},
    ]
    result = _filter_quality_sources(gathered)
    urls = [r["url"] for r in result]
    assert not any("instagram" in u for u in urls)

def test_filter_drops_short_content():
    gathered = [
        {"url": "https://example.com", "content": "short", "title": "t", "snippet": ""},
        {"url": "https://example2.com", "content": "x" * 200, "title": "t", "snippet": ""},
    ]
    result = _filter_quality_sources(gathered)
    assert len(result) == 1
    assert "example2" in result[0]["url"]

def test_judge_downgrades_speculative_questions():
    from schemas import FinalAnswer, ConfidenceLevel
    answer = FinalAnswer(
        question="Which AI will be best in 2030",
        short_answer="Cannot be determined",
        key_findings=["trend 1"], sources=[],
        confidence_level=ConfidenceLevel.high,
        confidence_reasoning="sources good",
        limitations=[], assumptions=[], suggested_next_steps=[]
    )
    result = _judge_answer(answer, "Which AI will be best in 2030")
    assert result.confidence_level != ConfidenceLevel.high

def test_filter_keeps_minimum_sources():
    # even if all sources are borderline, keep at least 2
    gathered = [
        {"url": f"https://example{i}.com", "content": "short", "title": "t", "snippet": ""}
        for i in range(3)
    ]
    result = _filter_quality_sources(gathered)
    assert len(result) >= 2
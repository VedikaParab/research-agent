import pytest
from schemas import FinalAnswer, ConfidenceLevel, Source, ResearchPlan, ToolDecision, ToolName

def test_confidence_level_enum_values():
    assert ConfidenceLevel.high.value == "High"
    assert ConfidenceLevel.medium.value == "Medium"
    assert ConfidenceLevel.low.value == "Low"

def test_source_score_too_high_rejected():
    with pytest.raises(Exception):
        Source(url="http://x.com", title="X", snippet="x", relevance_score=1.5)

def test_source_score_negative_rejected():
    with pytest.raises(Exception):
        Source(url="http://x.com", title="X", snippet="x", relevance_score=-0.1)

def test_final_answer_valid():
    answer = FinalAnswer(
        question="test", short_answer="test answer",
        key_findings=["finding 1"], sources=[],
        confidence_level=ConfidenceLevel.medium,
        confidence_reasoning="test", limitations=[],
        assumptions=[], suggested_next_steps=[]
    )
    assert answer.confidence_level == ConfidenceLevel.medium

def test_tool_decision_done():
    d = ToolDecision(action=ToolName.done, query=None, url=None, reasoning="enough info")
    assert d.action == ToolName.done
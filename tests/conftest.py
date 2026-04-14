import pytest
from schemas import FinalAnswer, ConfidenceLevel, Source, AgentState

@pytest.fixture
def sample_state():
    state = AgentState(question="Compare vector databases for RAG")
    state.gathered_info = [
        {"url": "https://example.com", "title": "Test", "snippet": "x" * 300},
        {"url": "https://example2.com", "title": "Test 2", "snippet": "y" * 300},
        {"url": "https://example3.com", "title": "Test 3", "snippet": "z" * 300},
    ]
    return state

@pytest.fixture
def sample_answer():
    return FinalAnswer(
        question="test",
        short_answer="test answer",
        key_findings=["finding 1", "finding 2"],
        sources=[],
        confidence_level=ConfidenceLevel.medium,
        confidence_reasoning="test",
        limitations=["limit 1"],
        assumptions=[],
        suggested_next_steps=["step 1"]
    )
import pytest
from unittest.mock import patch, MagicMock
from schemas import FinalAnswer, ConfidenceLevel, ResearchPlan, ToolDecision, ToolName

MOCK_PLAN = ResearchPlan(
    question="test query",
    steps=["Step 1: search", "Step 2: fetch"],
    tools_needed=[ToolName.web_search],
    reasoning="test"
)

MOCK_DECISION_SEARCH = ToolDecision(
    action=ToolName.web_search,
    query="test query",
    url=None,
    reasoning="searching"
)

MOCK_DECISION_DONE = ToolDecision(
    action=ToolName.done,
    query=None,
    url=None,
    reasoning="enough info"
)

MOCK_ANSWER = FinalAnswer(
    question="test query",
    short_answer="Test answer grounded in sources.",
    key_findings=["Finding 1", "Finding 2"],
    sources=[],
    confidence_level=ConfidenceLevel.medium,
    confidence_reasoning="Good sources found",
    limitations=["Some limitation"],
    assumptions=["Some assumption"],
    suggested_next_steps=["Next step"]
)

MOCK_SEARCH_RESULTS = [
    {"url": f"https://example{i}.com", "title": f"Source {i}",
     "snippet": "x" * 300, "status": "ok"}
    for i in range(5)
]

@patch("agent.orchestrator.call_synthesizer", return_value=MOCK_ANSWER)
@patch("agent.orchestrator.call_action_selector", side_effect=[MOCK_DECISION_SEARCH, MOCK_DECISION_DONE])
@patch("agent.orchestrator.call_planner", return_value=MOCK_PLAN)
@patch("agent.orchestrator.web_search", return_value=MOCK_SEARCH_RESULTS)
def test_full_pipeline_happy_path(mock_search, mock_planner, mock_selector, mock_synth):
    from agent.orchestrator import run_agent
    answer = run_agent("test query")
    assert isinstance(answer, FinalAnswer)
    assert answer.confidence_level == ConfidenceLevel.medium
    assert len(answer.key_findings) == 2
    mock_search.assert_called_once()

@patch("agent.orchestrator.call_synthesizer", return_value=MOCK_ANSWER)
@patch("agent.orchestrator.call_action_selector", return_value=MOCK_DECISION_DONE)
@patch("agent.orchestrator.call_planner", side_effect=Exception("LLM timeout"))
@patch("agent.orchestrator.web_search", return_value=MOCK_SEARCH_RESULTS)
def test_pipeline_survives_planner_failure(mock_search, mock_planner, mock_selector, mock_synth):
    from agent.orchestrator import run_agent
    answer = run_agent("test query")
    # should not raise — returns a valid answer even with planner failure
    assert isinstance(answer, FinalAnswer)

@patch("agent.orchestrator.call_planner", return_value=MOCK_PLAN)
@patch("agent.orchestrator.call_action_selector", return_value=MOCK_DECISION_SEARCH)
@patch("agent.orchestrator.web_search", side_effect=RuntimeError("HTTP 401 Unauthorized"))
def test_pipeline_all_tools_fail_returns_low_confidence(mock_search, mock_selector, mock_planner):
    from agent.orchestrator import run_agent
    answer = run_agent("test query")
    assert isinstance(answer, FinalAnswer)
    assert answer.confidence_level == ConfidenceLevel.low
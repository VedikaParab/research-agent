import pytest
from agent.llm import parse_json_safely

def test_parse_clean_json():
    assert parse_json_safely('{"key": "value"}') == {"key": "value"}

def test_parse_fenced_json():
    assert parse_json_safely('```json\n{"key": "value"}\n```') == {"key": "value"}

def test_parse_json_in_prose():
    assert parse_json_safely('Here is the result: {"key": "value"} done.') == {"key": "value"}

def test_parse_invalid_raises():
    with pytest.raises(ValueError):
        parse_json_safely("this is not json at all")

def test_parse_nested_json():
    result = parse_json_safely('{"a": {"b": [1, 2, 3]}}')
    assert result["a"]["b"] == [1, 2, 3]
import pytest

from app.integrations.anthropic_client import AnthropicError, parse_json_strict


def test_should_parse_when_raw_json():
    data = parse_json_strict('{"findings":[],"summary":""}')
    assert data == {"findings": [], "summary": ""}


def test_should_parse_when_fenced_with_lang():
    text = '```json\n{"findings":[]}\n```'
    data = parse_json_strict(text)
    assert data == {"findings": []}


def test_should_parse_when_prose_around_object():
    text = 'Sure, here you go: {"findings":[]} hope that helps.'
    data = parse_json_strict(text)
    assert data == {"findings": []}


def test_should_raise_when_no_json():
    with pytest.raises(AnthropicError):
        parse_json_strict("no json at all")

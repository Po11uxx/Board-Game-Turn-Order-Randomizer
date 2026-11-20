import pytest
from ai_coder.ui import parse_request, build_ui


def test_requirements_are_explicit_numbered_inputs():
    request = parse_request('App', 'R1: Count players\nR2: Shuffle')
    assert [r.id for r in request.requirements] == ['R1','R2']
    with pytest.raises(ValueError):
        parse_request('App', 'Shuffle somehow')


def test_ui_builds_without_credentials(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    app = build_ui()
    assert app is not None

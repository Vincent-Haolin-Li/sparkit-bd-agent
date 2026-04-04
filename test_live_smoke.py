import os

import pytest

from config import OPENAI_API_KEY, TAVILY_API_KEY
from researcher import research_target
from scorer import score_target
from searcher import search_targets
from fastapi.testclient import TestClient
import server


RUN_LIVE_TESTS = os.getenv("RUN_LIVE_TESTS") == "1"


pytestmark = pytest.mark.live


def _skip_if_not_live():
    if not RUN_LIVE_TESTS:
        pytest.skip("Set RUN_LIVE_TESTS=1 to run live tests")


def test_live_tavily_search_smoke():
    _skip_if_not_live()
    if not TAVILY_API_KEY:
        pytest.skip("TAVILY_API_KEY is missing")

    result = search_targets("fashion PR agency for independent designers", n=1)
    assert result.get("success") is True
    assert isinstance(result.get("data", []), list)


def test_live_llm_score_smoke():
    _skip_if_not_live()
    if not OPENAI_API_KEY:
        pytest.skip("OPENAI_API_KEY is missing")

    profile = {
        "name": "Smoke Test Studio",
        "standard_fields": {
            "what_they_do": "PR and digital storytelling for fashion creators",
            "positioning": "Works with sustainable independent brands",
            "clients": ["Indie Label A"],
            "recent_work": [{"text": "Creator launch campaign"}],
            "contacts": [],
            "team_size": "10-20",
        },
        "source_url": "https://example.com",
        "contact_url": "https://example.com/contact",
        "confidence": "medium",
    }

    score = score_target(profile)
    assert 1 <= score["fashion_tech_fit"] <= 5
    assert 1 <= score["creator_fit"] <= 5
    assert 1 <= score["sustainability_fit"] <= 5


def test_live_research_smoke():
    _skip_if_not_live()
    if not OPENAI_API_KEY:
        pytest.skip("OPENAI_API_KEY is missing")

    data = research_target("Example Domain", "https://example.com", "Example domain snippet")
    assert data.get("success") is True
    assert isinstance(data.get("steps", []), list)
    assert isinstance(data.get("data", {}), dict)


def test_live_run_endpoint_smoke():
    _skip_if_not_live()
    if not OPENAI_API_KEY or not TAVILY_API_KEY:
        pytest.skip("OPENAI_API_KEY or TAVILY_API_KEY is missing")

    client = TestClient(server.app)
    with client.stream("GET", "/run", params={"brief": "fashion PR agency", "n_targets": 1}) as response:
        body = b"".join(response.iter_bytes()).decode("utf-8")

    assert response.status_code == 200
    assert '"event": "searching"' in body
    assert ('"event": "done"' in body) or ('"event": "error"' in body)

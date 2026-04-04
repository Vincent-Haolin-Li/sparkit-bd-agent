import asyncio

import bd_agent


def test_search_node_success(monkeypatch):
    def fake_search_targets(brief, n=5):
        assert brief == "find partners"
        assert n == 20
        return {
            "success": True,
            "data": [
                {"title": "Alpha", "url": "https://alpha.test", "snippet": "s1"},
                {"title": "Beta", "url": "https://beta.test", "snippet": "s2"},
            ],
        }

    monkeypatch.setattr(bd_agent, "search_targets", fake_search_targets)

    result = asyncio.run(bd_agent.search_node({"brief": "find partners", "n": 3}))

    assert result["candidate_index"] == 0
    assert len(result["candidates"]) == 2
    assert result["events"][0]["event"] == "search_done"


def test_search_node_error_emits_search_error(monkeypatch):
    def fake_search_targets(brief, n=5):
        return {"success": False, "error": "tavily down", "data": []}

    monkeypatch.setattr(bd_agent, "search_targets", fake_search_targets)

    result = asyncio.run(bd_agent.search_node({"brief": "find partners", "n": 2}))
    event_names = [e["event"] for e in result["events"]]

    assert event_names == ["search_error", "search_done"]


def test_prepare_candidate_node_with_data():
    result = asyncio.run(
        bd_agent.prepare_candidate_node(
            {
                "candidate_index": 0,
                "candidates": [{"title": "Alpha", "url": "https://alpha.test"}],
            }
        )
    )
    assert result["current_candidate"]["title"] == "Alpha"
    assert result["events"][0]["event"] == "researching"


def test_prepare_candidate_node_end_of_list():
    result = asyncio.run(bd_agent.prepare_candidate_node({"candidate_index": 1, "candidates": [{"title": "A"}]}))
    assert result["current_candidate"] is None
    assert result["events"] == []


def test_research_candidate_node_directory_skip():
    result = asyncio.run(
        bd_agent.research_candidate_node(
            {
                "candidate_index": 0,
                "current_candidate": {
                    "title": "Top 10 PR agencies",
                    "url": "https://list.test",
                    "snippet": "best list",
                },
                "candidates": [{"title": "Top 10 PR agencies", "url": "https://list.test", "snippet": "best list"}],
                "seen_urls": {"https://list.test"},
                "seen_domains": {"list.test"},
                "max_entities_per_directory": 10,
                "max_candidates_total": 20,
            }
        )
    )

    event_names = [e["event"] for e in result["events"]]
    assert result["skip_current"] is True
    assert "directory_detected" in event_names
    assert "research_skipped" in event_names


def test_research_candidate_node_valid_profile(monkeypatch):
    def fake_research_target(title, url, snippet):
        return {
            "data": {
                "name": "Alpha Studio",
                "what_they_do": "PR for indie designers",
            },
            "steps": ["fetched"],
            "fetched_homepage": True,
        }

    monkeypatch.setattr(bd_agent, "research_target", fake_research_target)

    result = asyncio.run(
        bd_agent.research_candidate_node(
            {
                "candidate_index": 0,
                "current_candidate": {
                    "title": "Alpha",
                    "url": "https://alpha.test",
                    "snippet": "snippet",
                },
            }
        )
    )

    assert result["skip_current"] is False
    assert result["current_profile"]["name"] == "Alpha Studio"
    assert result["events"][-1]["event"] == "research_done"


def test_research_candidate_node_directory_expands_entities(monkeypatch):
    result = asyncio.run(
        bd_agent.research_candidate_node(
            {
                "candidate_index": 0,
                "current_candidate": {
                    "title": "Top 10 PR agencies",
                    "url": "https://list.test",
                    "snippet": "best list",
                },
                "candidates": [{"title": "Top 10 PR agencies", "url": "https://list.test", "snippet": "best list"}],
                "seen_urls": {"https://list.test"},
                "seen_domains": {"list.test"},
                "max_entities_per_directory": 10,
                "max_candidates_total": 20,
            }
        )
    )

    event_names = [e["event"] for e in result["events"]]
    assert result["skip_current"] is True
    assert "directory_detected" in event_names
    assert "research_skipped" in event_names


def test_refill_candidates_node_adds_candidates(monkeypatch):
    def fake_search_targets(query, n=5):
        assert "official website" in query
        return {
            "success": True,
            "data": [{"title": "Gamma", "url": "https://gamma.test", "snippet": "gamma"}],
        }

    monkeypatch.setattr(bd_agent, "search_targets", fake_search_targets)

    result = asyncio.run(
        bd_agent.refill_candidates_node(
            {
                "brief": "find partners",
                "n": 2,
                "search_attempts": 1,
                "candidates": [{"title": "Alpha", "url": "https://alpha.test", "snippet": ""}],
                "seen_urls": {"https://alpha.test"},
                "seen_domains": {"alpha.test"},
                "max_candidates_total": 20,
            }
        )
    )

    assert result["refill_added"] == 1
    assert any(c["url"] == "https://gamma.test" for c in result["candidates"])
    assert result["events"][0]["event"] == "candidate_pool_refilled"


def test_route_after_advance_prefers_refill_when_needed():
    state = {
        "qualified_count": 0,
        "n": 2,
        "candidate_index": 2,
        "candidates": [{}, {}],
        "search_attempts": 1,
        "max_search_attempts": 3,
    }
    assert bd_agent.route_after_advance(state) == "refill_candidates"


def test_score_candidate_node_emits_score_done(monkeypatch):
    def fake_score_target(profile):
        return {
            "score": 4.2,
            "fashion_tech_fit": 4,
            "creator_fit": 4,
            "sustainability_fit": 5,
            "rationale": "Good fit",
            "reasoning_steps": [],
            "steps": ["Scored"],
        }

    monkeypatch.setattr(bd_agent, "score_target", fake_score_target)

    result = asyncio.run(
        bd_agent.score_candidate_node(
            {
                "candidate_index": 0,
                "current_profile": {"name": "Alpha"},
            }
        )
    )

    assert result["current_scoring"]["score"] == 4.2
    assert result["events"][-1]["event"] == "score_done"


def test_email_candidate_node_appends_assembled(monkeypatch):
    def fake_draft_email(profile, scoring):
        return {
            "subject": "Hi",
            "body": "Short",
            "hook_fact": "fact",
            "word_count": 1,
        }

    monkeypatch.setattr(bd_agent, "draft_email", fake_draft_email)

    result = asyncio.run(
        bd_agent.email_candidate_node(
            {
                "candidate_index": 0,
                "current_profile": {"name": "Alpha"},
                "current_scoring": {"score": 4.0},
                "assembled": [],
            }
        )
    )

    assert len(result["assembled"]) == 1
    assert result["events"][0]["event"] == "email_step"
    assert result["events"][1]["event"] == "email_done"


def test_directory_classifier_does_not_skip_best_alone():
    candidate = {
        "title": "Best Fashion School in Japan - Example University",
        "url": "https://example-university.edu/fashion",
        "snippet": "Official program page",
    }
    assert bd_agent.is_directory_candidate(candidate) is False


def test_directory_classifier_skips_top_n_list_path():
    candidate = {
        "title": "Top 20 Fashion Schools",
        "url": "https://example.com/top-20-fashion-schools",
        "snippet": "Ranking list",
    }
    assert bd_agent.is_directory_candidate(candidate) is True


def test_route_helpers():
    assert bd_agent.route_after_prepare({"current_candidate": None}) == "finalize"
    assert bd_agent.route_after_prepare({"current_candidate": {"title": "A"}}) == "research_candidate"

    assert bd_agent.route_after_research({"skip_current": True}) == "advance_candidate"
    assert bd_agent.route_after_research({"skip_current": False}) == "prepare_scoring"

    assert bd_agent.route_after_advance({"qualified_count": 2, "n": 2, "candidate_index": 0, "candidates": [{}], "search_attempts": 1, "max_search_attempts": 3}) == "finalize"
    assert bd_agent.route_after_advance({"qualified_count": 0, "n": 2, "candidate_index": 1, "candidates": [{}, {}], "search_attempts": 1, "max_search_attempts": 3}) == "prepare_candidate"

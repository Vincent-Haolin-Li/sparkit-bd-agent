import asyncio
import os

import bd_agent


def test_bd_graph_runs_linear_pipeline(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    call_counter = {"count": 0}

    def fake_search_targets(brief, n=5):
        call_counter["count"] += 1
        if call_counter["count"] == 1:
            return {
                "data": [
                    {"title": "Alpha", "url": "https://alpha.test", "snippet": "alpha snippet"},
                    {"title": "Bad", "url": "https://bad.test", "snippet": "bad snippet"},
                ]
            }
        return {
            "data": [
                {"title": "Gamma", "url": "https://gamma.test", "snippet": "gamma snippet"},
            ]
        }

    def fake_research_target(title, url, snippet):
        if title == "Bad":
            return {"data": {"name": title}, "steps": ["bad profile"], "fetched_homepage": True}
        return {
            "data": {
                "name": "Alpha Studio" if title == "Alpha" else "Gamma Studio",
                "what_they_do": "Makes creator fashion tech.",
                "source_url": url,
                "contact_url": f"{url}/contact",
                "confidence": "high",
            },
            "steps": ["researched profile"],
            "fetched_homepage": True,
        }

    def fake_score_target(profile):
        return {
            "score": 4.6,
            "fashion_tech_fit": 5,
            "creator_fit": 4,
            "sustainability_fit": 4,
            "rationale": "Good fit",
            "reasoning_steps": [{"dimension": "Fashion Tech Fit", "score": 5, "reasoning": "Strong signal"}],
            "steps": ["Scored"],
        }

    def fake_draft_email(profile, scoring):
        return {
            "subject": "Hello Alpha",
            "body": "Short body",
            "hook_fact": "Strong signal",
            "word_count": 2,
            "contact_url": profile.get("contact_url"),
        }

    monkeypatch.setattr(bd_agent, "search_targets", fake_search_targets)
    monkeypatch.setattr(bd_agent, "research_target", fake_research_target)
    monkeypatch.setattr(bd_agent, "score_target", fake_score_target)
    monkeypatch.setattr(bd_agent, "draft_email", fake_draft_email)

    async def collect():
        events = []
        async for chunk in bd_agent.BD_GRAPH.astream({"brief": "find partners", "n": 2}, stream_mode="updates"):
            for node_output in chunk.values():
                events.extend(node_output.get("events", []))
        return events

    events = asyncio.run(collect())
    event_names = [event["event"] for event in events]

    assert "candidate_pool_refilled" in event_names
    assert event_names[-1] == "done"

    done_event = events[-1]
    result = done_event["data"]["result"]
    assert result["summary"]["total_targets"] == 2
    assert os.path.exists(done_event["data"]["saved_to"])

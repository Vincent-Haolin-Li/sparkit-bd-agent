import asyncio
import os

import bd_agent


def test_pipeline_offline_end_to_end(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    def fake_search_targets(brief, n=5):
        return {
            "success": True,
            "data": [
                {"title": "Alpha", "url": "https://alpha.test", "snippet": "alpha snippet"},
                {"title": "Beta", "url": "https://beta.test", "snippet": "beta snippet"},
            ],
        }

    def fake_research_target(title, url, snippet):
        return {
            "success": True,
            "fetched_homepage": True,
            "steps": [f"researched {title}"],
            "data": {
                "name": title,
                "what_they_do": f"{title} does creator PR",
                "source_url": url,
                "contact_url": f"{url}/contact",
                "confidence": "high",
            },
        }

    def fake_score_target(profile):
        name = profile.get("name", "")
        score = 4.8 if name == "Alpha" else 3.7
        return {
            "score": score,
            "fashion_tech_fit": 5 if name == "Alpha" else 3,
            "creator_fit": 4,
            "sustainability_fit": 4 if name == "Alpha" else 3,
            "rationale": f"{name} fit",
            "reasoning_steps": [],
            "steps": ["Scored"],
        }

    def fake_draft_email(profile, scoring):
        return {
            "subject": f"Hello {profile.get('name')}",
            "body": "Short body",
            "hook_fact": "hook",
            "word_count": 2,
            "contact_email": None,
            "contact_url": profile.get("contact_url"),
        }

    monkeypatch.setattr(bd_agent, "search_targets", fake_search_targets)
    monkeypatch.setattr(bd_agent, "research_target", fake_research_target)
    monkeypatch.setattr(bd_agent, "score_target", fake_score_target)
    monkeypatch.setattr(bd_agent, "draft_email", fake_draft_email)

    async def collect_events():
        events = []
        async for chunk in bd_agent.BD_GRAPH.astream({"brief": "find partners", "n": 2}, stream_mode="updates"):
            for node_output in chunk.values():
                events.extend(node_output.get("events", []))
        return events

    events = asyncio.run(collect_events())
    assert events[-1]["event"] == "done"

    done = events[-1]["data"]
    result = done["result"]

    assert result["summary"]["total_targets"] == 2
    assert result["summary"]["top_target"] == "Alpha"
    assert result["targets"][0]["rank"] == 1
    assert result["targets"][0]["profile"]["name"] == "Alpha"
    assert result["targets"][0]["scoring"]["score"] >= result["targets"][1]["scoring"]["score"]

    output_path = done["saved_to"]
    assert os.path.exists(output_path)

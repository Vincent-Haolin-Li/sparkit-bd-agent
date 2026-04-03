import asyncio
import json
import os
from datetime import datetime
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from emailer import draft_email
from researcher import research_target
from scorer import score_target
from searcher import search_targets


def is_directory_candidate(candidate: dict[str, Any]) -> bool:
    text = " ".join([
        str(candidate.get("title", "")),
        str(candidate.get("snippet", "")),
        str(candidate.get("url", "")),
    ]).lower()
    keywords = [
        "top ", "best ", "directory", "list of", "rank", "ranking",
        "agencies in", "agencies for", "clutch", "sortlist", "designrush",
    ]
    return any(k in text for k in keywords)


def has_minimum_profile_info(profile: dict[str, Any]) -> bool:
    what_they_do = str(profile.get("what_they_do", "")).strip()
    positioning = str(profile.get("positioning", "")).strip()
    has_intro = bool(what_they_do or positioning)

    contacts = profile.get("contacts")
    has_email = False
    if isinstance(contacts, list):
        for c in contacts:
            if not isinstance(c, dict):
                continue
            email_text = str(c.get("email", "")).strip()
            if "@" in email_text:
                has_email = True
                break

    # Skip only when BOTH intro and email are missing
    return has_intro or has_email


class BDState(TypedDict, total=False):
    brief: str
    n: int
    candidates: list[dict[str, Any]]
    candidate_index: int
    current_candidate: dict[str, Any] | None
    current_profile: dict[str, Any] | None
    current_scoring: dict[str, Any] | None
    assembled: list[dict[str, Any]]
    skip_current: bool
    result: dict[str, Any]
    saved_to: str
    events: list[dict[str, Any]]


async def search_node(state: BDState) -> BDState:
    brief = state["brief"]
    n = state.get("n", 5)
    search_result = await asyncio.to_thread(search_targets, brief, n)
    candidates = search_result.get("data", [])

    events = []
    if not search_result.get("success", True):
        events.append({
            "event": "search_error",
            "data": {
                "message": search_result.get("error", "Search failed"),
            },
        })

    events.append({
        "event": "search_done",
        "data": {
            "count": len(candidates),
            "candidates": candidates,
        },
    })

    return {
        "candidates": candidates,
        "candidate_index": 0,
        "assembled": [],
        "events": events,
    }


async def prepare_candidate_node(state: BDState) -> BDState:
    index = state.get("candidate_index", 0)
    candidates = state.get("candidates", [])
    if index >= len(candidates):
        return {"current_candidate": None, "events": []}

    candidate = candidates[index]
    return {
        "current_candidate": candidate,
        "current_profile": None,
        "current_scoring": None,
        "skip_current": False,
        "events": [{
            "event": "researching",
            "data": {
                "index": index + 1,
                "title": candidate.get("title", ""),
                "url": candidate.get("url", ""),
            },
        }],
    }


async def research_candidate_node(state: BDState) -> BDState:
    candidate = state.get("current_candidate") or {}
    index = state.get("candidate_index", 0)

    if is_directory_candidate(candidate):
        return {
            "current_profile": {},
            "skip_current": True,
            "events": [{
                "event": "research_skipped",
                "data": {
                    "index": index + 1,
                    "reason": "Search result is a ranking/directory page, not an agency website",
                    "url": candidate.get("url", ""),
                    "steps": ["Skipped before fetch using title/snippet/url pattern match"],
                },
            }],
        }

    research = await asyncio.to_thread(
        research_target,
        candidate.get("title", ""),
        candidate.get("url", ""),
        candidate.get("snippet", ""),
    )
    profile = research.get("data", {})
    steps = research.get("steps", [])
    fetched_homepage = bool(research.get("fetched_homepage", False))

    events = [{"event": "research_step", "data": {"index": index + 1, "step": s}} for s in steps]

    if not fetched_homepage:
        events.append({
            "event": "research_skipped",
            "data": {
                "index": index + 1,
                "reason": "Website unreachable or blocked during fetch",
                "url": candidate.get("url", ""),
                "steps": steps,
            },
        })
        return {
            "current_profile": profile,
            "skip_current": True,
            "events": events,
        }

    if profile.get("is_list_page"):
        events.append({
            "event": "research_skipped",
            "data": {
                "index": index + 1,
                "reason": "Website appears to be a list/directory page, not the agency's own site",
                "url": candidate.get("url", ""),
                "steps": steps,
            },
        })
        return {
            "current_profile": profile,
            "skip_current": True,
            "events": events,
        }

    if not has_minimum_profile_info(profile):
        events.append({
            "event": "research_skipped",
            "data": {
                "index": index + 1,
                "reason": "Insufficient information: missing both company intro and contact email",
                "url": candidate.get("url", ""),
                "steps": steps,
            },
        })
        return {
            "current_profile": profile,
            "skip_current": True,
            "events": events,
        }

    events.append({
        "event": "research_done",
        "data": {
            "index": index + 1,
            "name": profile.get("name"),
            "what_they_do": profile.get("what_they_do"),
            "url": candidate.get("url", ""),
            "steps": steps,
        },
    })
    return {
        "current_profile": profile,
        "skip_current": False,
        "events": events,
    }


async def prepare_scoring_node(state: BDState) -> BDState:
    index = state.get("candidate_index", 0)
    profile = state.get("current_profile") or {}
    return {
        "events": [{
            "event": "scoring",
            "data": {"index": index + 1, "name": profile.get("name")},
        }]
    }


async def score_candidate_node(state: BDState) -> BDState:
    index = state.get("candidate_index", 0)
    profile = state.get("current_profile") or {}
    scoring = await asyncio.to_thread(score_target, profile)

    events = [{"event": "scoring_step", "data": {"index": index + 1, "step": s}} for s in scoring.get("steps", [])]
    events.append({
        "event": "score_done",
        "data": {
            "index": index + 1,
            "name": profile.get("name"),
            "score": scoring["score"],
            "fashion_tech_fit": scoring["fashion_tech_fit"],
            "creator_fit": scoring["creator_fit"],
            "sustainability_fit": scoring["sustainability_fit"],
            "rationale": scoring.get("rationale", ""),
            "reasoning_steps": scoring.get("reasoning_steps", []),
            "steps": scoring.get("steps", []),
        },
    })
    return {
        "current_scoring": scoring,
        "skip_current": False,
        "events": events,
    }


async def prepare_email_node(state: BDState) -> BDState:
    index = state.get("candidate_index", 0)
    profile = state.get("current_profile") or {}
    return {
        "events": [{
            "event": "emailing",
            "data": {"index": index + 1, "name": profile.get("name")},
        }]
    }


async def email_candidate_node(state: BDState) -> BDState:
    index = state.get("candidate_index", 0)
    profile = state.get("current_profile") or {}
    scoring = state.get("current_scoring") or {}
    assembled = list(state.get("assembled", []))
    email = await asyncio.to_thread(draft_email, profile, scoring)
    assembled.append({
        "profile": profile,
        "scoring": scoring,
        "outreach": email,
    })

    events = [{"event": "email_step", "data": {"index": index + 1, "step": "Drafting personalized email..."}}]
    events.append({
        "event": "email_done",
        "data": {
            "index": index + 1,
            "name": profile.get("name"),
            "subject": email["subject"],
            "word_count": email["word_count"],
        },
    })
    return {
        "assembled": assembled,
        "events": events,
    }


def advance_candidate_node(state: BDState) -> BDState:
    return {
        "candidate_index": state.get("candidate_index", 0) + 1,
        "current_candidate": None,
        "current_profile": None,
        "current_scoring": None,
        "skip_current": False,
        "events": [],
    }


def finalize_node(state: BDState) -> BDState:
    assembled = list(state.get("assembled", []))
    assembled.sort(key=lambda item: item["scoring"]["score"], reverse=True)
    targets = [{"rank": i + 1, **item} for i, item in enumerate(assembled)]
    scores = [target["scoring"]["score"] for target in targets]

    result = {
        "brief": state["brief"],
        "generated_at": datetime.now().isoformat(),
        "targets": targets,
        "summary": {
            "total_targets": len(targets),
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "top_target": targets[0]["profile"].get("name", "") if targets else "",
        },
    }

    os.makedirs("output", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f"output/pipeline_{timestamp}.json"
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)

    return {
        "result": result,
        "saved_to": out_path,
        "events": [{
            "event": "done",
            "data": {"result": result, "saved_to": out_path},
        }],
    }


def route_after_prepare(state: BDState) -> str:
    return "finalize" if state.get("current_candidate") is None else "research_candidate"


def route_after_research(state: BDState) -> str:
    return "advance_candidate" if state.get("skip_current") else "prepare_scoring"


def route_after_advance(state: BDState) -> str:
    return "prepare_candidate" if state.get("candidate_index", 0) < len(state.get("candidates", [])) else "finalize"


def build_bd_graph():
    graph = StateGraph(BDState)
    graph.add_node("search", search_node)
    graph.add_node("prepare_candidate", prepare_candidate_node)
    graph.add_node("research_candidate", research_candidate_node)
    graph.add_node("prepare_scoring", prepare_scoring_node)
    graph.add_node("score_candidate", score_candidate_node)
    graph.add_node("prepare_email", prepare_email_node)
    graph.add_node("email_candidate", email_candidate_node)
    graph.add_node("advance_candidate", advance_candidate_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "search")
    graph.add_edge("search", "prepare_candidate")
    graph.add_conditional_edges("prepare_candidate", route_after_prepare, {
        "research_candidate": "research_candidate",
        "finalize": "finalize",
    })
    graph.add_conditional_edges("research_candidate", route_after_research, {
        "prepare_scoring": "prepare_scoring",
        "advance_candidate": "advance_candidate",
    })
    graph.add_edge("prepare_scoring", "score_candidate")
    graph.add_edge("score_candidate", "prepare_email")
    graph.add_edge("prepare_email", "email_candidate")
    graph.add_edge("email_candidate", "advance_candidate")
    graph.add_conditional_edges("advance_candidate", route_after_advance, {
        "prepare_candidate": "prepare_candidate",
        "finalize": "finalize",
    })
    graph.add_edge("finalize", END)
    return graph.compile()


BD_GRAPH = build_bd_graph()

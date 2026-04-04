import asyncio
import json
import os
from datetime import datetime
from typing import Any, TypedDict
from urllib.parse import urlparse

from langgraph.graph import END, START, StateGraph

from emailer import draft_email
from researcher import extract_directory_entities, fetch_page, research_target
from scorer import score_target
from searcher import search_targets


DIRECTORY_KEYWORDS = [
    "top ", "best ", "directory", "list of", "rank", "ranking",
    "agencies in", "agencies for", "clutch", "sortlist", "designrush",
    "universities offering", "programs in", "schools in",
]


def is_directory_candidate(candidate: dict[str, Any]) -> bool:
    text = " ".join([
        str(candidate.get("title", "")),
        str(candidate.get("snippet", "")),
        str(candidate.get("url", "")),
    ]).lower()
    return any(k in text for k in DIRECTORY_KEYWORDS)


def normalize_domain(url: str) -> str:
    try:
        return urlparse(url or "").netloc.lower().replace("www.", "")
    except Exception:
        return ""


def has_minimum_profile_info(profile: dict[str, Any]) -> bool:
    standard_fields = profile.get("standard_fields")
    if isinstance(standard_fields, dict) and (
        "what_they_do" in standard_fields
        or "positioning" in standard_fields
        or "contacts" in standard_fields
    ):
        what_they_do = str(standard_fields.get("what_they_do", "")).strip()
        positioning = str(standard_fields.get("positioning", "")).strip()
        has_intro = bool(what_they_do or positioning)
        contacts = standard_fields.get("contacts", [])
    else:
        what_they_do = str(profile.get("what_they_do", "")).strip()
        positioning = str(profile.get("positioning", "")).strip()
        has_intro = bool(what_they_do or positioning)
        contacts = profile.get("contacts", [])

    has_email = False
    if isinstance(contacts, list):
        for c in contacts:
            if not isinstance(c, dict):
                continue
            email_text = str(c.get("email", "")).strip()
            if "@" in email_text:
                has_email = True
                break

    return has_intro or has_email


def build_candidate(title: str, url: str, snippet: str = "") -> dict[str, Any]:
    return {
        "title": title or url,
        "url": url,
        "snippet": snippet,
    }


def merge_candidates(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    seen_urls: set[str],
    seen_domains: set[str],
    max_total: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    merged = list(existing)
    added = []

    for c in incoming:
        if len(merged) >= max_total:
            break
        url = str(c.get("url", "")).strip()
        if not url:
            continue
        domain = normalize_domain(url)
        if url in seen_urls or (domain and domain in seen_domains):
            continue
        seen_urls.add(url)
        if domain:
            seen_domains.add(domain)
        merged.append(c)
        added.append(c)

    return merged, added


class BDState(TypedDict, total=False):
    brief: str
    n: int
    candidates: list[dict[str, Any]]
    candidate_index: int
    current_candidate: dict[str, Any] | None
    current_profile: dict[str, Any] | None
    current_scoring: dict[str, Any] | None
    assembled: list[dict[str, Any]]
    qualified_count: int
    skip_current: bool
    result: dict[str, Any]
    saved_to: str
    events: list[dict[str, Any]]
    seen_urls: set[str]
    seen_domains: set[str]
    search_attempts: int
    max_search_attempts: int
    max_candidates_total: int
    max_entities_per_directory: int
    refill_added: int


async def search_node(state: BDState) -> BDState:
    brief = state["brief"]
    n = state.get("n", 5)
    initial_k = max(20, n * 6)

    search_result = await asyncio.to_thread(search_targets, brief, initial_k)
    candidates = search_result.get("data", [])

    seen_urls: set[str] = set()
    seen_domains: set[str] = set()
    deduped = []
    for c in candidates:
        url = str(c.get("url", "")).strip()
        if not url:
            continue
        domain = normalize_domain(url)
        if url in seen_urls or (domain and domain in seen_domains):
            continue
        seen_urls.add(url)
        if domain:
            seen_domains.add(domain)
        deduped.append(c)

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
            "count": len(deduped),
            "candidates": deduped,
        },
    })

    return {
        "candidates": deduped,
        "candidate_index": 0,
        "assembled": [],
        "qualified_count": 0,
        "events": events,
        "seen_urls": seen_urls,
        "seen_domains": seen_domains,
        "search_attempts": 1,
        "max_search_attempts": 4,
        "max_candidates_total": 220,
        "max_entities_per_directory": 10,
        "refill_added": 0,
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
    events = []

    if is_directory_candidate(candidate):
        url = candidate.get("url", "")
        events.append({
            "event": "directory_detected",
            "data": {
                "index": index + 1,
                "title": candidate.get("title", ""),
                "url": url,
            },
        })

        html, _, fetch_steps = await asyncio.to_thread(fetch_page, url)
        events.append({
            "event": "directory_expansion_started",
            "data": {"index": index + 1, "url": url},
        })

        entities = extract_directory_entities(html, url)
        entities = entities[: state.get("max_entities_per_directory", 10)]

        discovered_candidates = []
        for entity in entities:
            entity_name = entity.get("name", "").strip()
            entity_url = entity.get("url", "").strip()

            if not entity_url:
                events.append({
                    "event": "entity_search_fallback",
                    "data": {"index": index + 1, "name": entity_name},
                })
                fallback_q = f"{entity_name} official website"
                fallback = await asyncio.to_thread(search_targets, fallback_q, 2)
                fallback_items = fallback.get("data", [])
                for item in fallback_items:
                    fallback_url = str(item.get("url", "")).strip()
                    if not fallback_url:
                        continue
                    if is_directory_candidate(item):
                        continue
                    entity_url = fallback_url
                    break

            if not entity_url:
                events.append({
                    "event": "entity_skipped",
                    "data": {
                        "index": index + 1,
                        "name": entity_name,
                        "reason": "No resolvable official website",
                    },
                })
                continue

            if normalize_domain(entity_url) == normalize_domain(url):
                continue

            discovered_candidates.append(build_candidate(entity_name, entity_url, f"Discovered from {url}"))
            events.append({
                "event": "entity_discovered",
                "data": {
                    "index": index + 1,
                    "name": entity_name,
                    "url": entity_url,
                },
            })

        candidates = list(state.get("candidates", []))
        seen_urls = set(state.get("seen_urls", set()))
        seen_domains = set(state.get("seen_domains", set()))
        max_total = state.get("max_candidates_total", 220)

        merged, added = merge_candidates(candidates, discovered_candidates, seen_urls, seen_domains, max_total)

        events.append({
            "event": "directory_expansion_done",
            "data": {
                "index": index + 1,
                "url": url,
                "discovered": len(added),
                "steps": fetch_steps,
            },
        })

        return {
            "current_profile": {},
            "skip_current": True,
            "candidates": merged,
            "seen_urls": seen_urls,
            "seen_domains": seen_domains,
            "events": events,
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

    events.extend([{"event": "research_step", "data": {"index": index + 1, "step": s}} for s in steps])

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
        "qualified_count": state.get("qualified_count", 0) + 1,
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


async def refill_candidates_node(state: BDState) -> BDState:
    brief = state["brief"]
    attempts = state.get("search_attempts", 1)
    n = state.get("n", 5)
    query = f"{brief} official website contact -ranking -top -best -directory"
    k = max(10, n * 4)

    search_result = await asyncio.to_thread(search_targets, query, k)
    incoming = [build_candidate(i.get("title", ""), i.get("url", ""), i.get("snippet", "")) for i in search_result.get("data", [])]

    candidates = list(state.get("candidates", []))
    seen_urls = set(state.get("seen_urls", set()))
    seen_domains = set(state.get("seen_domains", set()))

    merged, added = merge_candidates(
        candidates,
        incoming,
        seen_urls,
        seen_domains,
        state.get("max_candidates_total", 220),
    )

    events = [{
        "event": "candidate_pool_refilled",
        "data": {
            "attempt": attempts + 1,
            "added": len(added),
            "total_candidates": len(merged),
            "query": query,
        },
    }]

    return {
        "candidates": merged,
        "seen_urls": seen_urls,
        "seen_domains": seen_domains,
        "search_attempts": attempts + 1,
        "refill_added": len(added),
        "events": events,
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
    qualified = state.get("qualified_count", 0)
    target_n = state.get("n", 5)
    index = state.get("candidate_index", 0)
    candidates_count = len(state.get("candidates", []))
    attempts = state.get("search_attempts", 1)
    max_attempts = state.get("max_search_attempts", 4)

    if qualified >= target_n:
        return "finalize"
    if index < candidates_count:
        return "prepare_candidate"
    if attempts < max_attempts:
        return "refill_candidates"
    return "finalize"


def route_after_refill(state: BDState) -> str:
    return "prepare_candidate" if state.get("refill_added", 0) > 0 else "finalize"


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
    graph.add_node("refill_candidates", refill_candidates_node)
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
        "refill_candidates": "refill_candidates",
        "finalize": "finalize",
    })
    graph.add_conditional_edges("refill_candidates", route_after_refill, {
        "prepare_candidate": "prepare_candidate",
        "finalize": "finalize",
    })
    graph.add_edge("finalize", END)
    return graph.compile()


BD_GRAPH = build_bd_graph()

import json
import re
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_BASE_URL, CHAT_MODEL, SPARKIT_CONTEXT
from prompts import SCORE_PROMPT

client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)


def _evidence_snippet(profile: dict) -> str:
    pieces = []
    for key in ["what_they_do", "positioning", "team_size"]:
        value = profile.get(key)
        if value:
            pieces.append(str(value).strip())
    clients = profile.get("clients") or []
    if isinstance(clients, list) and clients:
        pieces.append("Clients: " + ", ".join(str(c) for c in clients[:3]))
    recent_work = profile.get("recent_work") or []
    if isinstance(recent_work, list) and recent_work:
        rw = [str(item.get("text", "")).strip() for item in recent_work[:2] if isinstance(item, dict)]
        rw = [x for x in rw if x]
        if rw:
            pieces.append("Recent work: " + "; ".join(rw))
    return " | ".join(pieces)[:280]


def _fallback_reasoning(dimension: str, score: int, profile: dict) -> str:
    evidence = _evidence_snippet(profile)
    if dimension == "fashion_tech":
        if score <= 2:
            return f"No explicit fashion-tech or digital innovation evidence in the profile. Available evidence: {evidence or 'none provided.'}"
        return f"Some digital/fashion-tech signals are present but limited in specificity. Evidence: {evidence or 'profile text.'}"
    if dimension == "creator":
        if score <= 2:
            return f"No explicit evidence of work with independent or emerging creators in the profile. Available evidence: {evidence or 'none provided.'}"
        return f"Profile suggests creator-aligned work, but evidence is limited. Evidence: {evidence or 'profile text.'}"
    if score <= 2:
        return f"Weak sustainability evidence in the profile. Available evidence: {evidence or 'none provided.'}"
    return f"Strong sustainability positioning is visible in the profile. Evidence: {evidence or 'profile text.'}"


def score_target(profile: dict) -> dict:
    """Score a company profile on 3 dimensions with detailed reasoning."""
    steps = [
        "Analyzing fashion tech fit...",
        "Analyzing creator fit...",
        "Analyzing sustainability fit..."
    ]

    prompt = SCORE_PROMPT.format(
        sparkit_context=SPARKIT_CONTEXT,
        profile=json.dumps(profile, ensure_ascii=False, indent=2)
    )

    try:
        resp = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=500
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        data = json.loads(raw)

        ft = max(1, min(5, int(data.get("fashion_tech_fit", 3))))
        cr = max(1, min(5, int(data.get("creator_fit", 3))))
        su = max(1, min(5, int(data.get("sustainability_fit", 3))))

        ft_reason = (data.get("fashion_tech_reasoning") or "").strip() or _fallback_reasoning("fashion_tech", ft, profile)
        cr_reason = (data.get("creator_reasoning") or "").strip() or _fallback_reasoning("creator", cr, profile)
        su_reason = (data.get("sustainability_reasoning") or "").strip() or _fallback_reasoning("sustainability", su, profile)

        reasoning_steps = [
            {"dimension": "Fashion Tech Fit", "score": ft, "reasoning": ft_reason},
            {"dimension": "Creator Fit", "score": cr, "reasoning": cr_reason},
            {"dimension": "Sustainability Fit", "score": su, "reasoning": su_reason}
        ]

        final_score = round(ft * 0.4 + cr * 0.35 + su * 0.25, 1)
        steps.append(f"Final score: {final_score}/5")

        rationale = (data.get("rationale") or "").strip()
        if not rationale:
            rationale = f"Overall fit is {final_score}/5 based on extracted evidence across fashion-tech, creator, and sustainability dimensions."

        return {
            "score": final_score,
            "fashion_tech_fit": ft,
            "creator_fit": cr,
            "sustainability_fit": su,
            "rationale": rationale,
            "reasoning_steps": reasoning_steps,
            "steps": steps
        }
    except Exception as e:
        return {
            "score": 2.5,
            "fashion_tech_fit": 3,
            "creator_fit": 3,
            "sustainability_fit": 2,
            "rationale": f"Scoring error: {str(e)[:50]}",
            "reasoning_steps": [],
            "steps": ["Scoring failed"]
        }

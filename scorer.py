import json
import re
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_BASE_URL, CHAT_MODEL, SPARKIT_CONTEXT

client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

def score_target(profile: dict) -> dict:
    """Score a company profile on 3 dimensions with detailed reasoning."""
    steps = [
        "Analyzing fashion tech fit...",
        "Analyzing creator fit...",
        "Analyzing sustainability fit..."
    ]

    prompt = f"""Score this company for fit with Sparkit.

Sparkit context:
{SPARKIT_CONTEXT}

Company profile:
{json.dumps(profile, ensure_ascii=False, indent=2)}

CRITICAL: Base scores ONLY on factual evidence in the profile. Cite specific facts.

Score on 3 dimensions (1-5 scale):
1. fashion_tech_fit: Evidence of fashion-tech/digital innovation work
2. creator_fit: Evidence of working with independent/emerging creators
3. sustainability_fit: Evidence of sustainability/ethical production focus

Scoring guide:
- 5: Multiple explicit examples with names/details
- 4: Clear evidence with at least one specific example
- 3: Indirect signals or adjacent work
- 2: Weak/generic signals only
- 1: No evidence

Return JSON with SPECIFIC reasoning citing facts:
{{
  "fashion_tech_fit": 1-5,
  "fashion_tech_reasoning": "cite specific client/project/positioning from profile",
  "creator_fit": 1-5,
  "creator_reasoning": "cite specific evidence",
  "sustainability_fit": 1-5,
  "sustainability_reasoning": "cite specific evidence",
  "rationale": "overall summary with key hook fact"
}}

Return ONLY JSON, no markdown."""

    try:
        resp = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=400
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        data = json.loads(raw)

        ft = max(1, min(5, int(data.get("fashion_tech_fit", 3))))
        cr = max(1, min(5, int(data.get("creator_fit", 3))))
        su = max(1, min(5, int(data.get("sustainability_fit", 3))))

        reasoning_steps = [
            {"dimension": "Fashion Tech Fit", "score": ft, "reasoning": data.get("fashion_tech_reasoning", "")},
            {"dimension": "Creator Fit", "score": cr, "reasoning": data.get("creator_reasoning", "")},
            {"dimension": "Sustainability Fit", "score": su, "reasoning": data.get("sustainability_reasoning", "")}
        ]

        final_score = round(ft * 0.4 + cr * 0.35 + su * 0.25, 1)
        steps.append(f"Final score: {final_score}/5")

        return {
            "score": final_score,
            "fashion_tech_fit": ft,
            "creator_fit": cr,
            "sustainability_fit": su,
            "rationale": data.get("rationale", ""),
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

import json
import re
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_BASE_URL, CHAT_MODEL, SPARKIT_CONTEXT

client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

def draft_email(profile: dict, scoring: dict) -> dict:
    """Draft a highly personalized outreach email."""

    rationale = scoring.get("rationale", "")

    prompt = f"""Write a cold outreach email from Sparkit to {profile.get('name')}.

Sparkit context:
{SPARKIT_CONTEXT}

Target company:
{json.dumps(profile, ensure_ascii=False, indent=2)}

Key insight from scoring: {rationale}

CRITICAL RULES:
1. Open with ONE specific fact about their work (client name, campaign, or specialty) - NOT generic praise
2. Connect Sparkit's value to THEIR specific context
3. Under 120 words total
4. Conversational, human tone - avoid corporate jargon
5. End with: "Would a 15-minute call next week work?"
6. NO placeholders like [Name] - use actual company name

Return JSON:
{{
  "subject": "specific subject under 8 words (reference their work, not generic)",
  "body": "email body in plain text",
  "hook_fact": "the specific fact you opened with"
}}

Return ONLY JSON, no markdown."""

    try:
        resp = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=500
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        data = json.loads(raw)

        body = data.get("body", "")
        word_count = len(body.split())

        if word_count > 130:
            trim_resp = client.chat.completions.create(
                model=CHAT_MODEL,
                messages=[{"role": "user", "content": f"Trim to under 120 words, keep the hook and CTA:\n\n{body}"}],
                temperature=0,
                max_tokens=300
            )
            body = trim_resp.choices[0].message.content.strip()
            word_count = len(body.split())

        return {
            "subject": data.get("subject", ""),
            "body": body,
            "hook_fact": data.get("hook_fact", ""),
            "word_count": word_count,
            "contact_url": profile.get("contact_url")
        }
    except Exception as e:
        return {
            "subject": f"Sparkit x {profile.get('name', 'Your Company')}",
            "body": "Let's explore a partnership.",
            "hook_fact": "",
            "word_count": 4,
            "contact_url": profile.get("contact_url")
        }

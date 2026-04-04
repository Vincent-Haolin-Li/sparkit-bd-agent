import json
import re
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_BASE_URL, CHAT_MODEL, SPARKIT_CONTEXT
from prompts import EMAIL_PROMPT

client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

def draft_email(profile: dict, scoring: dict) -> dict:
    """Draft a highly personalized outreach email."""

    rationale = scoring.get("rationale", "")

    prompt = EMAIL_PROMPT.format(
        sparkit_context=SPARKIT_CONTEXT,
        profile=json.dumps(profile, ensure_ascii=False, indent=2),
        rationale=rationale
    )

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

        # Extract email from contacts - handle both old and new profile structures
        contact_email = None

        # Try new structure first (standard_fields)
        standard_fields = profile.get("standard_fields")
        if isinstance(standard_fields, dict) and "contacts" in standard_fields:
            contacts = standard_fields.get("contacts") or []
        else:
            contacts = profile.get("contacts", [])

        if contacts and isinstance(contacts, list):
            for contact in contacts:
                if isinstance(contact, dict) and contact.get("email"):
                    contact_email = contact["email"]
                    break

        return {
            "subject": data.get("subject", ""),
            "body": body,
            "hook_fact": data.get("hook_fact", ""),
            "word_count": word_count,
            "contact_email": contact_email,
            "contact_url": profile.get("contact_url") if not contact_email else None
        }
    except Exception as e:
        # Extract email from contacts if available - handle both structures
        contact_email = None

        standard_fields = profile.get("standard_fields")
        if isinstance(standard_fields, dict) and "contacts" in standard_fields:
            contacts = standard_fields.get("contacts") or []
        else:
            contacts = profile.get("contacts", [])

        if contacts and isinstance(contacts, list):
            for contact in contacts:
                if isinstance(contact, dict) and contact.get("email"):
                    contact_email = contact["email"]
                    break

        return {
            "subject": f"Sparkit x {profile.get('name', 'Your Company')}",
            "body": "Let's explore a partnership.",
            "hook_fact": "",
            "word_count": 4,
            "contact_email": contact_email,
            "contact_url": profile.get("contact_url") if not contact_email else None
        }

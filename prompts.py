from config import SPARKIT_CONTEXT

RESEARCH_PROMPT = """You are an information extraction assistant. Below is the raw content scraped from {url}.

---
{raw_content}
---

Based ONLY on the content above, extract the following fields. If a field is not mentioned, return null. Do NOT guess or invent information.

Return a JSON object with these exact keys:
- name: company name (string or null)
- what_they_do: what they do, 2-3 sentences (string or null)
- clients: list of client/brand names mentioned (array of strings, max 5)
- contacts: list of people with roles visible on the page (array of {{"name": string, "role": string}}, max 3)
- recent_work: recent campaigns, projects, or press mentions (array of {{"text": string, "url": string or null}}, max 3) — include the URL if a link was visible in the content, otherwise null
- positioning: their specialty or niche in 1-2 sentences (string or null)

Return only valid JSON, no markdown, no explanation."""

SCORE_PROMPT = """You are evaluating potential partners for Sparkit, a fashion-tech platform for independent creators.

Sparkit context:
{sparkit_context}

Target company profile:
{profile}

Score this company on each dimension from 1 (poor fit) to 5 (excellent fit):
- fashion_tech_fit: How relevant are they to fashion technology and innovation?
- creator_fit: How aligned are they with independent/emerging creators?
- sustainability_fit: How committed are they to sustainability?

Scoring guide:
- 5: Direct, explicit evidence in the profile
- 4: Strong indirect signals
- 3: Adjacent or partial alignment
- 2: Weak signals only
- 1: No meaningful alignment

Return a JSON object with:
- fashion_tech_fit: integer 1-5
- creator_fit: integer 1-5
- sustainability_fit: integer 1-5
- rationale: one sentence referencing a specific fact from the profile

Return only valid JSON, no markdown."""
EMAIL_PROMPT = """You are writing a cold outreach email on behalf of Sparkit to a potential partner.

Sparkit context:
{sparkit_context}

Target company profile:
{profile}

Rules:
1. Keep the entire email under 500 words. (Subject line + body)
2. Open with ONE specific hook that references a real fact from their profile (a client, campaign, value, or specialty). This hook must be a direct observation, not generic praise.
3. Immediately after the hook, state how Sparkit helps them achieve a relevant goal or solve a pain point. Use their language, not our features.
4. Limit Sparkit’s self-description to one concise sentence that ties back to their world.
5. End with a low‑friction CTA that explicitly suggests a specific, short next step (e.g., “Would a quick 15‑minute call next week work?”).
6. Write in a conversational, friendly tone — avoid bullet points, jargon, or corporate phrases.
7. Do NOT use placeholders like [Name]. Use the actual company name.
8. Return only a valid JSON object with exactly three fields: "subject", "body", "hook_fact". No markdown, no extra text.

Example structure (do not copy content):
{
  "subject": "Short, specific subject line",
  "body": "Hook sentence. Transition showing mutual benefit. One line about Sparkit. Call to action.",
  "hook_fact": "The specific fact you used from their profile"
}

Make sure the body is plain text (no markdown) and does not contain any stray text like "Contact form".
"""
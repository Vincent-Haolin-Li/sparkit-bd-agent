from config import SPARKIT_CONTEXT

RESEARCH_PROMPT = """Extract ALL company information from this webpage. Return ONLY valid JSON.

URL: {url}

Content:
{source_text}

CRITICAL RULES:
1. Extract ONLY factual information visible in the content. Do NOT invent or guess.
2. PRIORITY: Extract ALL email addresses and phone numbers found. Email is most important.
3. If this is a LIST PAGE (directory, top 10, etc), extract the FIRST agency's info and provide its URL in "real_agency_url".
4. Extract ANY additional information you find: awards, certifications, social media, press mentions, team members, office locations, etc.
5. Return all extracted fields, even if some are empty. Use null for missing values.

Return JSON with standard fields + any extra fields found:
{{
  "name": "exact company name from page",
  "what_they_do": "2-3 sentences describing their work",
  "positioning": "their specialty/niche in 1-2 sentences",
  "clients": ["actual client names mentioned"],
  "recent_work": [{{"text": "specific project/campaign", "url": "link if available"}}],
  "contacts": [{{"name": "person name or 'General'", "role": "their role if visible", "email": "ALL emails found - separate multiple with semicolon", "phone": "ALL phone numbers found - separate multiple with semicolon"}}],
  "team_size": "number or description if mentioned",
  "real_agency_url": "if list page, first agency's website URL",

  "awards": "any awards or certifications mentioned",
  "founded_year": "founding year if mentioned",
  "office_locations": ["city1", "city2"],
  "social_media": {{"linkedin": "url", "instagram": "url", "twitter": "url"}},
  "press_mentions": ["recent news or press mentions"],
  "team_members": ["key team members if listed"],
  "company_size": "employee count if mentioned",
  "specialties": ["specific areas of expertise"],
  "any_other_info": "any other relevant information found"
}}

Return ONLY JSON, no markdown. Include all fields even if empty/null."""

SCORE_PROMPT = """Score this company for fit with Sparkit.

Sparkit context:
{sparkit_context}

Company profile:
{profile}

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

EMAIL_PROMPT = """You are writing a cold outreach email on behalf of Sparkit to a potential partner.

Sparkit context:
{sparkit_context}

Target company profile:
{profile}

Scoring insight: {rationale}

Rules:
1. PURPOSE: This is an initial partnership inquiry, not a sales pitch
2. Keep the entire email under 500 words (subject + body)
3. Open with ONE specific hook that references a real fact from their profile (a client, campaign, value, or specialty)
4. Immediately after the hook, explain why Sparkit + their expertise = mutual value
5. Limit Sparkit's self-description to one concise sentence
6. End with: "Would a 15-minute call next week work?"
7. Write in conversational, friendly tone — avoid jargon or corporate phrases
8. Do NOT use placeholders like [Name]. Use the actual company name.

Subject line rules:
- Start with action verb: "Partnership", "Collaboration", "Let's work together"
- Reference both parties' core business
- Under 8 words
- Example: "Partnership: Indie designers + your PR expertise"

Return only valid JSON with exactly three fields: "subject", "body", "hook_fact". No markdown, no extra text.

Example:
{{
  "subject": "Partnership: Indie designers + your PR expertise",
  "body": "Hook sentence. Transition showing mutual benefit. One line about Sparkit. Call to action.",
  "hook_fact": "The specific fact you used from their profile"
}}
"""

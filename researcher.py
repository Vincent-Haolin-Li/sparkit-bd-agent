import httpx
import json
import re
from html2text import html2text
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_BASE_URL, CHAT_MODEL
from urllib.parse import urljoin

client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

def find_key_pages(base_url: str, html_text: str) -> dict:
    """Find About, Contact, and Team pages from HTML"""
    pages = {"about": None, "contact": None, "team": None}

    about_patterns = [r'href=["\']([^"\']*(?:about|who-we-are|our-story|our-team)[^"\']*)["\']']
    contact_patterns = [r'href=["\']([^"\']*(?:contact|get-in-touch|reach-us)[^"\']*)["\']']
    team_patterns = [r'href=["\']([^"\']*(?:team|people|our-people)[^"\']*)["\']']

    for pattern in about_patterns:
        match = re.search(pattern, html_text, re.IGNORECASE)
        if match:
            pages["about"] = urljoin(base_url, match.group(1))
            break

    for pattern in contact_patterns:
        match = re.search(pattern, html_text, re.IGNORECASE)
        if match:
            pages["contact"] = urljoin(base_url, match.group(1))
            break

    for pattern in team_patterns:
        match = re.search(pattern, html_text, re.IGNORECASE)
        if match:
            pages["team"] = urljoin(base_url, match.group(1))
            break

    return pages

def fetch_page(url: str) -> tuple[str, str, list]:
    """Fetch a URL and convert HTML to Markdown. Returns (html, text, steps)."""
    steps = []
    try:
        steps.append(f"Visiting: {url}")
        resp = httpx.get(url, timeout=10, follow_redirects=True)
        resp.raise_for_status()
        html = resp.text
        text = html2text(html)
        steps.append(f"Got {len(text)} characters")
        return html, text, steps
    except Exception as e:
        steps.append(f"Failed to fetch: {str(e)}")
        return "", "", steps

def extract_profile(url: str, snippet: str, page_text: str, extra_info: str = "", contact_url: str = None) -> tuple[dict, list]:
    """Extract company profile from page text using LLM. Returns (profile, steps)."""
    steps = []
    source_text = page_text if len(page_text) > 200 else snippet

    if extra_info:
        source_text = source_text[:2500] + "\n\n=== Additional Context ===\n" + extra_info[:1500]

    confidence = "high" if len(page_text) > 500 else ("medium" if snippet else "low")

    is_list_page = any(keyword in source_text.lower() for keyword in [
        "top 10", "top 20", "best agencies", "agency list", "directory"
    ]) and source_text.count("http") > 5

    if is_list_page:
        steps.append("Detected list page, extracting first real agency")

    steps.append(f"Analyzing content ({len(source_text)} chars)")

    prompt = f"""Extract company information from this webpage. Return ONLY valid JSON.

URL: {url}

Content:
{source_text[:4000]}

CRITICAL: Extract ONLY factual information visible in the content. Do NOT invent or guess.

If this is a LIST PAGE (directory, top 10, etc), extract the FIRST agency's info and provide its URL in "real_agency_url".

Return JSON:
{{
  "name": "exact company name from page",
  "what_they_do": "2-3 sentences describing their work",
  "positioning": "their specialty/niche in 1-2 sentences",
  "clients": ["actual client names mentioned"],
  "recent_work": [{{"text": "specific project/campaign", "url": "link if available"}}],
  "contacts": [{{"name": "person name", "role": "their role", "email": "email if visible"}}],
  "team_size": "number or description if mentioned",
  "real_agency_url": "if list page, first agency's website URL"
}}

Return ONLY JSON, no markdown."""

    try:
        steps.append("Calling LLM to extract information...")
        resp = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=1000
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        data = json.loads(raw)

        name = data.get('name', 'Unknown')
        what_they_do = data.get('what_they_do', '')[:80]
        steps.append(f"Extracted: {name} - {what_they_do}")

        if data.get("real_agency_url") and data["real_agency_url"] != url:
            steps.append(f"Found real agency site: {data['real_agency_url']}")
            _, real_text, fetch_steps = fetch_page(data["real_agency_url"])
            steps.extend(fetch_steps)
            if real_text:
                data, extract_steps = extract_profile(data["real_agency_url"], "", real_text, "", contact_url)
                steps.extend(extract_steps)
                return data, steps

    except Exception as e:
        steps.append(f"Extraction failed: {str(e)[:100]}")
        data = {
            "name": None, "what_they_do": None, "clients": [],
            "positioning": None, "recent_work": [], "contacts": [], "team_size": None
        }

    data["source_url"] = url
    data["contact_url"] = contact_url
    data["confidence"] = confidence
    return data, steps

def research_target(title: str, url: str, snippet: str) -> dict:
    """Fetch and extract profile from a URL."""
    all_steps = []

    # Visit homepage
    html, page_text, fetch_steps = fetch_page(url)
    all_steps.extend(fetch_steps)

    # Find key pages
    extra_info = ""
    contact_url = None
    if html and len(page_text) > 200:
        key_pages = find_key_pages(url, html)
        contact_url = key_pages.get("contact")

        # Visit About page
        if key_pages["about"]:
            _, about_text, about_steps = fetch_page(key_pages["about"])
            if about_text:
                extra_info += about_text[:2000]

        # Visit Team page
        if key_pages["team"]:
            _, team_text, team_steps = fetch_page(key_pages["team"])
            if team_text:
                extra_info += "\n" + team_text[:1500]

        # Visit Contact page
        if key_pages["contact"]:
            _, contact_text, contact_steps = fetch_page(key_pages["contact"])
            if contact_text:
                extra_info += "\n" + contact_text[:1000]

    # Extract information
    profile, extract_steps = extract_profile(url, snippet, page_text, extra_info, contact_url)
    all_steps.extend(extract_steps)

    if not profile.get("name"):
        profile["name"] = title

    return {"success": True, "data": profile, "steps": all_steps}



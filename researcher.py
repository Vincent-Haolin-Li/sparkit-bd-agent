import httpx
import json
import re
from html2text import html2text
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_BASE_URL, CHAT_MODEL
from prompts import RESEARCH_PROMPT
from urllib.parse import urljoin

client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

BAD_EMAIL_SUFFIXES = {
    "jpg", "jpeg", "png", "gif", "webp", "svg", "avif", "ico",
    "css", "js", "map", "pdf", "zip", "xml", "json", "txt",
}


def is_plausible_email(email: str) -> bool:
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        return False

    local, domain = email.rsplit("@", 1)
    if not local or not domain or "." not in domain:
        return False

    tld = domain.rsplit(".", 1)[-1]
    if tld in BAD_EMAIL_SUFFIXES:
        return False

    if re.search(r"\b\d{2,5}x\d{2,5}\b", email):
        return False

    return True

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


def extract_emails(text: str) -> list[str]:
    """Extract unique plausible email addresses from text."""
    if not text:
        return []
    matches = re.findall(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", text, flags=re.IGNORECASE)
    seen = set()
    emails = []
    for m in matches:
        email = m.strip().strip(".,;:()[]<>{}\"'").lower()
        if not is_plausible_email(email):
            continue
        if email not in seen:
            seen.add(email)
            emails.append(email)
    return emails


def extract_mailto_emails(html: str) -> list[str]:
    """Extract emails from mailto links in HTML."""
    if not html:
        return []
    matches = re.findall(r'href=["\']mailto:([^"\'?#]+)', html, flags=re.IGNORECASE)
    seen = set()
    emails = []
    for m in matches:
        email = m.strip().lower()
        if not is_plausible_email(email):
            continue
        if email not in seen:
            seen.add(email)
            emails.append(email)
    return emails


def extract_phones(text: str) -> list[str]:
    """Extract likely phone numbers from text, rejecting GPS coordinates."""
    if not text:
        return []
    matches = re.findall(r"(?:\+?\d[\d\s().\-]{7,}\d)", text)
    seen = set()
    phones = []
    for m in matches:
        phone = " ".join(m.split())
        digits_only = re.sub(r"\D", "", phone)
        if not (8 <= len(digits_only) <= 16):
            continue
        # Reject GPS-like coordinates: bare decimal numbers like 51.5042839
        if re.fullmatch(r"-?\d{1,3}\.\d{4,}", phone.strip()):
            continue
        # Reject sequences of coordinate-like numbers separated by semicolons/spaces
        if re.search(r"\d+\.\d{5,}", phone):
            continue
        if phone not in seen:
            seen.add(phone)
            phones.append(phone)
    return phones

def extract_profile(
    url: str,
    snippet: str,
    page_text: str,
    extra_info: str = "",
    contact_url: str = None,
    source_emails: list[str] | None = None,
) -> tuple[dict, list]:
    """Extract company profile from page text using LLM. Returns (profile, steps)."""
    steps = []
    source_text = page_text if len(page_text) > 200 else snippet

    # Keep more contact-heavy text so email extraction has better recall
    contact_window = extra_info[:5000] if extra_info else ""
    main_window = source_text[:5000] if source_text else ""
    combined_text = (contact_window + "\n" + main_window).strip()

    if extra_info:
        source_text = "=== Contact Information ===\n" + contact_window + "\n\n=== Main Content ===\n" + main_window
    else:
        source_text = main_window

    confidence = "high" if len(page_text) > 500 else ("medium" if snippet else "low")

    is_list_page = any(keyword in source_text.lower() for keyword in [
        "top 10", "top 20", "best agencies", "agency list", "directory"
    ]) and source_text.count("http") > 5

    if is_list_page:
        steps.append("Detected list page, extracting first real agency")

    fallback_emails = extract_emails(combined_text)
    fallback_phones = extract_phones(combined_text)

    high_confidence_emails = []
    if source_emails:
        seen = set()
        for e in source_emails:
            normalized = (e or "").strip().lower()
            if normalized and normalized not in seen and is_plausible_email(normalized):
                seen.add(normalized)
                high_confidence_emails.append(normalized)

    if high_confidence_emails:
        fallback_emails = high_confidence_emails + [e for e in fallback_emails if e not in set(high_confidence_emails)]
        steps.append(f"Detected {len(high_confidence_emails)} high-confidence email(s) from mailto links")
    if fallback_emails:
        steps.append(f"Detected {len(fallback_emails)} raw email(s) from pages")
    if fallback_phones:
        steps.append(f"Detected {len(fallback_phones)} raw phone number(s) from pages")

    steps.append(f"Analyzing content ({len(source_text)} chars)")

    prompt = RESEARCH_PROMPT.format(
        url=url,
        source_text=source_text[:9000]
    )

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

    contacts = data.get("contacts")
    if not isinstance(contacts, list):
        contacts = []

    existing_emails = []
    existing_phones = []
    for c in contacts:
        if not isinstance(c, dict):
            continue
        email_text = c.get("email") or ""
        phone_text = c.get("phone") or ""
        existing_emails.extend(extract_emails(email_text))
        existing_phones.extend(extract_phones(phone_text))

    if fallback_emails and not existing_emails:
        contacts.insert(0, {
            "name": "General",
            "role": "",
            "email": "; ".join(fallback_emails),
            "phone": "; ".join(fallback_phones) if fallback_phones else ""
        })
        steps.append("Added fallback contact from regex email extraction")
    elif fallback_emails and existing_emails:
        merged = []
        seen = set(existing_emails)
        for e in fallback_emails:
            if e not in seen:
                seen.add(e)
                merged.append(e)
        if merged:
            for c in contacts:
                if isinstance(c, dict):
                    current = c.get("email") or ""
                    c["email"] = "; ".join(extract_emails(current) + merged) if current else "; ".join(merged)
                    break
            steps.append("Merged additional regex emails into contacts")

    data["contacts"] = contacts
    data["source_url"] = url
    data["contact_url"] = contact_url
    data["confidence"] = confidence
    data["is_list_page"] = bool(is_list_page and not data.get("real_agency_url"))
    return data, steps

def research_target(title: str, url: str, snippet: str) -> dict:
    """Fetch and extract profile from a URL."""
    all_steps = []

    # Visit homepage
    html, page_text, fetch_steps = fetch_page(url)
    all_steps.extend(fetch_steps)

    source_emails = extract_mailto_emails(html)

    # Find key pages
    extra_info = ""
    contact_url = None
    if html and len(page_text) > 200:
        key_pages = find_key_pages(url, html)
        contact_url = key_pages.get("contact")

        # Visit About page
        if key_pages["about"]:
            about_html, about_text, about_steps = fetch_page(key_pages["about"])
            all_steps.extend(about_steps)
            source_emails.extend(extract_mailto_emails(about_html))
            if about_text:
                extra_info += about_text[:2500]

        # Visit Team page
        if key_pages["team"]:
            team_html, team_text, team_steps = fetch_page(key_pages["team"])
            all_steps.extend(team_steps)
            source_emails.extend(extract_mailto_emails(team_html))
            if team_text:
                extra_info += "\n" + team_text[:2000]

        # Visit Contact page
        if key_pages["contact"]:
            contact_html, contact_text, contact_steps = fetch_page(key_pages["contact"])
            all_steps.extend(contact_steps)
            source_emails.extend(extract_mailto_emails(contact_html))
            if contact_text:
                extra_info += "\n" + contact_text[:4000]

    # Extract information
    profile, extract_steps = extract_profile(url, snippet, page_text, extra_info, contact_url, source_emails)
    all_steps.extend(extract_steps)

    if not profile.get("name"):
        profile["name"] = title

    return {
        "success": True,
        "data": profile,
        "steps": all_steps,
        "fetched_homepage": bool(page_text.strip())
    }



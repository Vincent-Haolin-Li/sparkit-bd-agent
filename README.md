# Sparkit BD Outreach Pipeline

An autonomous BD outreach agent built on **LangGraph**, orchestrating a full pipeline as a compiled state machine: web search → company research → fit scoring → personalized email drafts → structured JSON output. Each candidate flows through conditional routing with smart skip logic, and every step streams real-time events to the browser via SSE.

## How It Works

The pipeline is implemented as a LangGraph `StateGraph` with typed state (`BDState`), replacing the earlier hardcoded for-loop. This gives the system conditional branching, per-node event emission, and a clear path toward planner/executor evolution.

```
Brief Input
    ↓
searcher.py       → Tavily API search (returns up to N candidates)
    ↓
bd_agent.py       → LangGraph state machine orchestrates per-candidate loop
    ↓  ┌──────────────────────────────────────────────────────┐
    ↓  │  For each candidate:                                 │
    ↓  │    1. Pre-filter: skip ranking/directory pages        │
    ↓  │    2. researcher.py → Fetch homepage + About/Team/    │
    ↓  │       Contact pages, extract profile via LLM          │
    ↓  │    3. Post-filter: skip unreachable / list pages /    │
    ↓  │       insufficient info                               │
    ↓  │    4. scorer.py → Score on 3 dimensions with reasoning│
    ↓  │    5. emailer.py → Draft personalized outreach email  │
    ↓  └──────────────────────────────────────────────────────┘
    ↓
server.py         → SSE streaming to web UI with real-time progress
    ↓
Output JSON       → Ranked targets with profiles, scores, and emails
```

## Features

### Research & Extraction
- **Multi-page crawling**: Automatically discovers and visits About, Team, and Contact pages via regex link detection on the homepage HTML
- **LLM-powered extraction**: Sends crawled content to LLM with structured JSON prompt; extracts company name, description, positioning, clients, recent work, contacts, and team size
- **List page detection**: Identifies directory/ranking pages (e.g. "Top 10 agencies") both pre-fetch (keyword matching on search result title/snippet/URL) and post-fetch (content analysis), and follows through to the real agency site when possible

### Contact Extraction (v1.2)
- **Three-tier email sourcing with priority**:
  1. `mailto:` links extracted directly from raw HTML across all crawled pages (highest confidence)
  2. Regex extraction from converted text content (medium confidence)
  3. LLM extraction from prompt response (baseline)
- **Email validation (`is_plausible_email`)**: Rejects false positives by checking:
  - File extension suffixes (`.jpg`, `.png`, `.svg`, `.css`, `.js`, `.pdf`, etc.)
  - Image dimension patterns in the string (e.g. `683x1024`)
  - Basic structural validity (local part, domain, TLD)
- **Fallback merge logic**: If LLM misses emails that regex found, they are deduplicated and merged into the contact list; if LLM has some and regex has others, new ones are appended without duplicates
- **Phone extraction with GPS filtering**: Rejects coordinate-like decimals (e.g. `51.5042839`) that commonly appear in embedded map scripts

### Smart Skip Logic (v1.2)
The pipeline applies a layered skip strategy to avoid wasting LLM calls on low-value candidates. Crucially, skipping is never based on the final score — only on data availability:

| Stage | Condition | Rationale |
|-------|-----------|-----------|
| Pre-fetch | Search result title/snippet/URL matches directory keywords (`top`, `best`, `ranking`, `clutch`, `sortlist`, `designrush`, etc.) | Avoids fetching pages that are aggregator listings, not agency websites |
| Post-fetch | Homepage returned empty response or HTTP error | Site is unreachable or blocked; no data to extract |
| Post-extraction | `is_list_page` flag set (content contains "top 10/20", "agency list" + many outbound links) | Page is a directory even if it wasn't caught pre-fetch |
| Post-extraction | Both company intro (`what_they_do` + `positioning`) AND contact email are missing | Relaxed threshold: keeps candidates that have either a description or an email, only skips when both are absent |

Each skip emits a `research_skipped` event with the reason, URL, and detailed steps so the user can see exactly why a candidate was dropped.

### Scoring & Reasoning (v1.2)
- **Three-dimension scoring**: Fashion-tech fit (40%), Creator fit (35%), Sustainability fit (25%) — weighted to Sparkit's priorities
- **Evidence-based reasoning**: LLM is prompted to cite specific facts from the profile for each dimension score
- **Fallback reasoning generation**: When LLM returns empty reasoning for a dimension, the system generates a fallback explanation using `_evidence_snippet` (extracts key facts from profile fields: what_they_do, positioning, clients, recent_work) and `_fallback_reasoning` (produces dimension-specific text based on score level and available evidence)
- **Score clamping**: All dimension scores are clamped to 1-5 range to prevent LLM hallucination of out-of-range values

### Email Generation
- **Personalized hooks**: Each email opens with a specific fact from the target's profile (a client name, campaign, or specialty)
- **Word count control**: If the LLM generates over 130 words, a second trimming call reduces it to under 120 while preserving the hook and CTA
- **Contact routing**: Email is sent to the best available contact — prioritizes direct email addresses extracted from the site, falls back to contact form URL when no email is found

### Orchestration (v1.2)
- **LangGraph StateGraph**: The pipeline runs as a compiled state machine (`bd_agent.py`) with typed state (`BDState`), not a hardcoded for-loop
- **Conditional routing**: Three routing functions control flow — `route_after_prepare` (has more candidates?), `route_after_research` (skip or score?), `route_after_advance` (loop or finalize?)
- **Event-driven architecture**: Every node emits structured events; `server.py` only does SSE serialization and HTTP handling
- **Recursion limit**: Set to 200 to support pipelines with many candidates without hitting LangGraph's default limit

### Frontend & Observability
- **Real-time SSE streaming**: Every pipeline step (search, research, scoring, email) streams progress to the browser
- **Expandable log details**: Research steps, scoring reasoning, and skip reasons are shown with expand/collapse toggles
- **Candidate list display**: All search results shown with numbering immediately after search completes
- **Process persistence**: Progress logs remain visible and scrollable after pipeline completion, not discarded
- **Error visibility**: Search errors and skip events are surfaced in the log with full context

## Output Format

Each target includes:
- **Profile**: Company name, what they do, clients, key contacts (with email/phone), recent work
- **Scoring**: Overall score + breakdown by dimension with specific reasoning
- **Email**: Subject line + body + hook fact used + direct email link (if available) or contact form
- **Confidence**: High/Medium/Low based on data quality

## Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/YOUR_USERNAME/sparkit-bd-agent.git
cd sparkit-bd-agent
```

### 2. Create Virtual Environment

```bash
conda create -n sparkit-bd python=3.12 -y
conda activate sparkit-bd
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API Keys

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` with your actual API keys:
```
OPENAI_API_KEY=your_siliconflow_api_key
OPENAI_BASE_URL=https://api.siliconflow.cn/v1
CHAT_MODEL=moonshotai/Kimi-K2-Instruct-0905
TAVILY_API_KEY=your_tavily_api_key
```

**Where to get API keys:**
- **SiliconFlow**: https://cloud.siliconflow.cn (free tier available)
- **Tavily**: https://tavily.com (1000 searches/month free)

### 5. Run the Server

```bash
python server.py
```

Visit: `http://localhost:8000/static/simple.html`

## Customization

Change the targeting domain by editing `config.py`:

```python
SPARKIT_CONTEXT = """
Your company description and what you're looking for...
"""
```

No other code changes needed.

## Project Structure

```
sparkit-bd-agent/
├── server.py          # FastAPI server, SSE streaming, HTTP entry point
├── bd_agent.py        # LangGraph state machine orchestration
├── searcher.py        # Tavily API search wrapper
├── researcher.py      # Multi-page crawling + LLM profile extraction
├── scorer.py          # Three-dimension fit scoring with reasoning
├── emailer.py         # Personalized outreach email generation
├── prompts.py         # All LLM prompt templates (research, scoring, email)
├── config.py          # API keys, model config, Sparkit context
├── static/
│   └── simple.html    # Web UI with real-time progress
├── output/            # Pipeline JSON output files
├── test_bd_agent.py   # Agent orchestration tests
└── test_server.py     # Server endpoint tests
```

## Testing

Run the test suite:
```bash
python -m pytest test_bd_agent.py test_server.py -v
```

## Changelog

### v1.2 (Current)
- **Email extraction hardening**: Added `is_plausible_email` validation to reject asset-filename false positives (`.jpg`, `.png`, `.svg`, etc.) and image-dimension patterns (`683x1024`); added `extract_mailto_emails` for high-confidence email sourcing from HTML `mailto:` links; three-tier email priority with deduplication merge
- **Phone extraction hardening**: Added GPS coordinate rejection to prevent map-embedded decimals from appearing as phone numbers
- **Smart skip logic**: Four-layer skip strategy (directory keyword pre-filter → unreachable homepage → list page detection → insufficient info) with relaxed threshold — only skips when both company intro and contact email are missing; no score-based filtering
- **Scoring reasoning fallback**: Auto-generates dimension-specific reasoning when LLM returns empty, using evidence extracted from profile fields
- **LangGraph state machine**: Migrated from hardcoded server loop to `StateGraph` with typed state, conditional routing, and per-node event emission
- **Frontend observability**: Skip reasons, search errors, and detailed research steps visible in UI with expand/collapse

### v1.1
- Fixed LangGraph recursion limit (increased to 200 for multi-candidate pipelines)
- Added streaming events for research, scoring, and email steps
- Improved contact extraction with email/phone priority
- Enhanced LLM prompts to extract all contact information
- Real-time step-by-step progress display in frontend
- Scoring reasoning displayed with LLM thinking process
- Email display prioritizes direct email addresses over contact forms
- Process logs remain visible and collapsible after completion

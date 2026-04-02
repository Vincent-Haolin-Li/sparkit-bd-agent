# Sparkit BD Outreach Pipeline

An autonomous agent that takes a targeting brief and produces a complete outreach pipeline: web search → company research → fit scoring → personalized email drafts → structured JSON output.

## Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/YOUR_USERNAME/sparkit-bd-agent.git
cd sparkit-bd-agent
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API Keys

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

### 4. Run the Server

```bash
python server.py
```

Visit: `http://localhost:8000/static/simple.html`

## How It Works

```
Brief Input
    ↓
searcher.py       → Tavily API search
    ↓
researcher.py     → Fetch website + About/Contact pages + LLM extraction
    ↓
scorer.py         → LLM scores 3 dimensions (fashion-tech, creator, sustainability)
    ↓
emailer.py        → LLM drafts personalized email with specific hook
    ↓
Output JSON       → Ranked targets with profiles, scores, and emails
```

## Features

- **Smart Research**: Automatically visits About, Team, and Contact pages
- **List Page Detection**: Skips directory/ranking pages, extracts real agencies
- **Detailed Scoring**: Shows reasoning for each dimension
- **Personalized Emails**: Uses specific facts as hooks, not generic templates
- **Real-time Progress**: Stream scoring and email generation steps in UI
- **Hallucination Prevention**: Only extracts facts from actual website content

## Output Format

Each target includes:
- **Profile**: Company name, what they do, clients, contacts, recent work
- **Scoring**: Overall score + breakdown by dimension with reasoning
- **Email**: Subject line + body + hook fact used
- **Confidence**: High/Medium/Low based on data quality

## Customization

Change the targeting domain by editing `config.py`:

```python
SPARKIT_CONTEXT = """
Your company description and what you're looking for...
"""
```

No other code changes needed.

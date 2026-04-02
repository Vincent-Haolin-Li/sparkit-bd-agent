import os
from dotenv import load_dotenv

load_dotenv()
# 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
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://ai.ltcraft.cn/v1")
CHAT_MODEL      = os.getenv("CHAT_MODEL", "claude-sonnet-4-6")
TAVILY_API_KEY  = os.getenv("TAVILY_API_KEY")

SPARKIT_CONTEXT = """
Sparkit is a fashion-tech platform where independent creators design, produce,
and sell original clothing. Core values:
- AI-powered design tools for independent creators
- Vetted manufacturing network (speed to market)
- Sustainability and ethical production
- Creator economy — helping indie designers build real businesses

Ideal partners: PR agencies working with emerging/indie fashion brands,
fashion incubators and accelerators, sustainable fashion advocates,
creator-focused media and blogs, fashion-tech investors.
"""

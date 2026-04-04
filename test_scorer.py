import pytest
from unittest.mock import patch, MagicMock
from scorer import _evidence_snippet, _fallback_reasoning


class TestEvidenceSnippet:
    """Test evidence snippet generation"""

    def test_evidence_from_standard_fields(self):
        """Test extracting evidence from standard fields"""
        profile = {
            "standard_fields": {
                "what_they_do": "We provide PR services",
                "positioning": "Sustainability focused",
                "team_size": "15 people",
                "clients": ["Client A", "Client B", "Client C"],
                "recent_work": [
                    {"text": "Campaign X", "url": "https://example.com"},
                    {"text": "Campaign Y"}
                ]
            }
        }

        snippet = _evidence_snippet(profile)

        assert "PR services" in snippet
        assert "Sustainability" in snippet
        assert "15 people" in snippet
        assert "Client A" in snippet
        assert "Campaign X" in snippet

    def test_evidence_from_old_structure(self):
        """Test extracting evidence from old profile structure"""
        profile = {
            "what_they_do": "We provide PR services",
            "positioning": "Sustainability focused",
            "team_size": "15 people",
            "clients": ["Client A"],
            "recent_work": []
        }

        snippet = _evidence_snippet(profile)

        assert "PR services" in snippet
        assert "Sustainability" in snippet

    def test_evidence_with_extra_fields(self):
        """Test that extra fields are included in evidence"""
        profile = {
            "standard_fields": {
                "what_they_do": "PR services",
                "positioning": None,
                "team_size": None,
                "clients": [],
                "recent_work": []
            },
            "extra_fields": {
                "awards": "Best PR Agency 2024",
                "founded_year": "2010",
                "specialties": ["Fashion", "Tech"]
            }
        }

        snippet = _evidence_snippet(profile)

        assert "PR services" in snippet
        assert "awards" in snippet or "Best PR Agency" in snippet

    def test_empty_profile(self):
        """Test with empty profile"""
        profile = {
            "standard_fields": {
                "what_they_do": None,
                "positioning": None,
                "team_size": None,
                "clients": [],
                "recent_work": []
            }
        }

        snippet = _evidence_snippet(profile)

        # Should return empty or minimal string
        assert isinstance(snippet, str)

    def test_snippet_length_limit(self):
        """Test that snippet respects length limit"""
        profile = {
            "standard_fields": {
                "what_they_do": "A" * 500,
                "positioning": "B" * 500,
                "team_size": "C" * 500,
                "clients": ["D" * 100 for _ in range(10)],
                "recent_work": []
            }
        }

        snippet = _evidence_snippet(profile)

        assert len(snippet) <= 280


class TestFallbackReasoning:
    """Test fallback reasoning generation"""

    def test_fashion_tech_low_score(self):
        """Test fallback reasoning for low fashion-tech score"""
        profile = {
            "standard_fields": {
                "what_they_do": "General PR",
                "positioning": None,
                "team_size": None,
                "clients": [],
                "recent_work": []
            }
        }

        reasoning = _fallback_reasoning("fashion_tech", 1, profile)

        assert "No explicit fashion-tech" in reasoning
        assert isinstance(reasoning, str)
        assert len(reasoning) > 0

    def test_fashion_tech_high_score(self):
        """Test fallback reasoning for high fashion-tech score"""
        profile = {
            "standard_fields": {
                "what_they_do": "AI-powered design tools",
                "positioning": "Fashion tech innovation",
                "team_size": None,
                "clients": [],
                "recent_work": []
            }
        }

        reasoning = _fallback_reasoning("fashion_tech", 4, profile)

        assert "digital" in reasoning.lower() or "tech" in reasoning.lower()

    def test_creator_fit_reasoning(self):
        """Test fallback reasoning for creator fit"""
        profile = {
            "standard_fields": {
                "what_they_do": "Support emerging designers",
                "positioning": None,
                "team_size": None,
                "clients": [],
                "recent_work": []
            }
        }

        reasoning = _fallback_reasoning("creator", 3, profile)

        assert isinstance(reasoning, str)
        assert len(reasoning) > 0

    def test_sustainability_reasoning(self):
        """Test fallback reasoning for sustainability"""
        profile = {
            "standard_fields": {
                "what_they_do": "Sustainable fashion PR",
                "positioning": "Eco-friendly focus",
                "team_size": None,
                "clients": [],
                "recent_work": []
            }
        }

        reasoning = _fallback_reasoning("sustainability", 4, profile)

        assert isinstance(reasoning, str)
        assert len(reasoning) > 0

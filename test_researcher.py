import pytest
from researcher import (
    is_plausible_email,
    extract_emails,
    extract_mailto_emails,
    extract_phones,
    normalize_profile,
    dedupe_contacts,
    extract_directory_entities,
)


class TestEmailValidation:
    """Test email validation logic"""

    def test_valid_emails(self):
        """Test that valid emails pass validation"""
        assert is_plausible_email("john@example.com") is True
        assert is_plausible_email("contact@company.co.uk") is True
        assert is_plausible_email("info+tag@domain.org") is True

    def test_invalid_emails(self):
        """Test that invalid emails fail validation"""
        assert is_plausible_email("") is False
        assert is_plausible_email("notanemail") is False
        assert is_plausible_email("@example.com") is False
        assert is_plausible_email("user@") is False

    def test_file_extension_rejection(self):
        """Test that file extensions are rejected"""
        assert is_plausible_email("image.jpg@domain.com") is False
        assert is_plausible_email("style.css@domain.com") is False
        assert is_plausible_email("script.js@domain.com") is False

    def test_image_dimension_rejection(self):
        """Test that image dimensions are rejected"""
        assert is_plausible_email("683x1024@domain.com") is False
        assert is_plausible_email("user@683x1024.com") is False

    def test_case_insensitive(self):
        """Test that email validation is case insensitive"""
        assert is_plausible_email("JOHN@EXAMPLE.COM") is True
        assert is_plausible_email("John@Example.Com") is True


class TestEmailExtraction:
    """Test email extraction from text"""

    def test_extract_single_email(self):
        """Test extracting a single email from text"""
        text = "Contact us at support@example.com for help"
        emails = extract_emails(text)
        assert "support@example.com" in emails

    def test_extract_multiple_emails(self):
        """Test extracting multiple emails from text"""
        text = "Email john@example.com or jane@example.com"
        emails = extract_emails(text)
        assert len(emails) >= 2
        assert "john@example.com" in emails
        assert "jane@example.com" in emails

    def test_no_duplicates(self):
        """Test that duplicate emails are not returned"""
        text = "Contact support@example.com or support@example.com"
        emails = extract_emails(text)
        assert emails.count("support@example.com") == 1

    def test_empty_text(self):
        """Test extracting from empty text"""
        emails = extract_emails("")
        assert emails == []

    def test_no_emails_in_text(self):
        """Test text with no emails"""
        text = "This is just plain text with no email addresses"
        emails = extract_emails(text)
        assert emails == []


class TestMailtoExtraction:
    """Test mailto link extraction"""

    def test_extract_mailto_link(self):
        """Test extracting email from mailto link"""
        html = '<a href="mailto:contact@example.com">Contact</a>'
        emails = extract_mailto_emails(html)
        assert "contact@example.com" in emails

    def test_extract_multiple_mailto_links(self):
        """Test extracting multiple mailto links"""
        html = '''
        <a href="mailto:john@example.com">John</a>
        <a href="mailto:jane@example.com">Jane</a>
        '''
        emails = extract_mailto_emails(html)
        assert len(emails) >= 2
        assert "john@example.com" in emails
        assert "jane@example.com" in emails

    def test_mailto_with_subject(self):
        """Test mailto link with subject parameter"""
        html = '<a href="mailto:contact@example.com?subject=Hello">Contact</a>'
        emails = extract_mailto_emails(html)
        assert "contact@example.com" in emails

    def test_empty_html(self):
        """Test extracting from empty HTML"""
        emails = extract_mailto_emails("")
        assert emails == []


class TestPhoneExtraction:
    """Test phone number extraction"""

    def test_extract_us_phone(self):
        """Test extracting US phone number"""
        text = "Call us at +1-555-123-4567"
        phones = extract_phones(text)
        assert len(phones) > 0

    def test_extract_international_phone(self):
        """Test extracting international phone number"""
        text = "Contact: +44 20 7946 0958"
        phones = extract_phones(text)
        assert len(phones) > 0

    def test_reject_gps_coordinates(self):
        """Test that GPS coordinates are rejected"""
        text = "Location: 51.5042839, -0.1275"
        phones = extract_phones(text)
        # Should not extract GPS coordinates as phone numbers
        for phone in phones:
            assert not phone.startswith("51.5")

    def test_empty_text(self):
        """Test extracting from empty text"""
        phones = extract_phones("")
        assert phones == []

    def test_no_duplicates(self):
        """Test that duplicate phone numbers are not returned"""
        text = "Call +1-555-123-4567 or +1-555-123-4567"
        phones = extract_phones(text)
        assert phones.count("+1-555-123-4567") <= 1


class TestContactDedup:
    def test_remove_redundant_general_when_named_share_same_email(self):
        contacts = [
            {"name": "Jake Posner", "role": "Founder", "email": "hello@jaan-studio.com", "phone": ""},
            {"name": "Annabel Matthews", "role": "Client Partner", "email": "hello@jaan-studio.com", "phone": ""},
            {"name": "General", "role": "", "email": "hello@jaan-studio.com", "phone": ""},
        ]

        deduped = dedupe_contacts(contacts)

        assert len(deduped) == 2
        assert all(c["name"].lower() != "general" for c in deduped)

    def test_keep_general_for_unique_email(self):
        contacts = [
            {"name": "Jake Posner", "role": "Founder", "email": "jake@jaan-studio.com", "phone": ""},
            {"name": "General", "role": "", "email": "hello@jaan-studio.com", "phone": ""},
        ]

        deduped = dedupe_contacts(contacts)

        assert len(deduped) == 2
        assert any(c["name"].lower() == "general" for c in deduped)


class TestDirectoryEntityExtraction:
    def test_extract_directory_entities_with_links(self):
        html = '''
        <a href="https://alpha.edu">Alpha Fashion School</a>
        <a href="https://beta.edu">Beta Design Institute</a>
        <a href="/rankings">Top 100 Rankings</a>
        '''

        entities = extract_directory_entities(html, "https://list.test")

        names = [e["name"] for e in entities]
        assert "Alpha Fashion School" in names
        assert "Beta Design Institute" in names
        assert all("ranking" not in n.lower() for n in names)

    """Test profile normalization"""

    def test_normalize_standard_fields(self):
        """Test that standard fields are properly normalized"""
        raw_profile = {
            "name": "Test Company",
            "what_they_do": "We do things",
            "positioning": "We are the best",
            "clients": ["Client A", "Client B"],
            "recent_work": [],
            "contacts": [],
            "team_size": "10-20",
            "source_url": "https://example.com",
            "contact_url": "https://example.com/contact",
            "confidence": "high",
            "is_list_page": False,
        }

        normalized = normalize_profile(raw_profile)

        assert normalized["name"] == "Test Company"
        assert normalized["standard_fields"]["what_they_do"] == "We do things"
        assert normalized["standard_fields"]["positioning"] == "We are the best"
        assert normalized["standard_fields"]["clients"] == ["Client A", "Client B"]
        assert normalized["source_url"] == "https://example.com"
        assert normalized["confidence"] == "high"

    def test_normalize_extra_fields(self):
        """Test that extra fields are captured"""
        raw_profile = {
            "name": "Test Company",
            "what_they_do": "We do things",
            "positioning": "We are the best",
            "clients": [],
            "recent_work": [],
            "contacts": [],
            "team_size": None,
            "source_url": "https://example.com",
            "contact_url": None,
            "confidence": "high",
            "is_list_page": False,
            "awards": "Best Company 2024",
            "founded_year": "2020",
            "social_media": {"linkedin": "https://linkedin.com/company/test"},
        }

        normalized = normalize_profile(raw_profile)

        assert "extra_fields" in normalized
        assert normalized["extra_fields"]["awards"] == "Best Company 2024"
        assert normalized["extra_fields"]["founded_year"] == "2020"
        assert "linkedin" in normalized["extra_fields"]["social_media"]

    def test_normalize_skips_empty_extra_fields(self):
        """Test that empty extra fields are not included"""
        raw_profile = {
            "name": "Test Company",
            "what_they_do": "We do things",
            "positioning": "We are the best",
            "clients": [],
            "recent_work": [],
            "contacts": [],
            "team_size": None,
            "source_url": "https://example.com",
            "contact_url": None,
            "confidence": "high",
            "is_list_page": False,
            "awards": None,
            "founded_year": "",
            "social_media": {},
        }

        normalized = normalize_profile(raw_profile)

        # extra_fields should not be present or should be empty
        extra_fields = normalized.get("extra_fields", {})
        assert len(extra_fields) == 0

    def test_normalize_ensures_list_fields(self):
        """Test that list fields are always lists"""
        raw_profile = {
            "name": "Test Company",
            "what_they_do": "We do things",
            "positioning": "We are the best",
            "clients": None,
            "recent_work": None,
            "contacts": None,
            "team_size": None,
            "source_url": "https://example.com",
            "contact_url": None,
            "confidence": "high",
            "is_list_page": False,
        }

        normalized = normalize_profile(raw_profile)

        assert isinstance(normalized["standard_fields"]["clients"], list)
        assert isinstance(normalized["standard_fields"]["recent_work"], list)
        assert isinstance(normalized["standard_fields"]["contacts"], list)

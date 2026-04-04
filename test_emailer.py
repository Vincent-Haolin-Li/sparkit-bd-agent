import pytest
from unittest.mock import patch, MagicMock
from emailer import draft_email


class TestEmailDrafting:
    """Test email drafting logic"""

    def test_extract_email_from_standard_fields(self):
        """Test extracting email from new profile structure"""
        profile = {
            "name": "Test Company",
            "standard_fields": {
                "contacts": [
                    {"name": "John", "email": "john@example.com", "role": "CEO"}
                ]
            },
            "contact_url": "https://example.com/contact"
        }
        scoring = {"rationale": "Good fit"}

        with patch('emailer.client.chat.completions.create') as mock_create:
            mock_create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(
                    content='{"subject": "Test", "body": "Hello", "hook_fact": "fact"}'
                ))]
            )

            result = draft_email(profile, scoring)

            assert result["contact_email"] == "john@example.com"
            assert result["contact_url"] is None  # Should be None when email exists

    def test_extract_email_from_old_structure(self):
        """Test extracting email from old profile structure"""
        profile = {
            "name": "Test Company",
            "contacts": [
                {"name": "Jane", "email": "jane@example.com", "role": "Manager"}
            ],
            "contact_url": "https://example.com/contact"
        }
        scoring = {"rationale": "Good fit"}

        with patch('emailer.client.chat.completions.create') as mock_create:
            mock_create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(
                    content='{"subject": "Test", "body": "Hello", "hook_fact": "fact"}'
                ))]
            )

            result = draft_email(profile, scoring)

            assert result["contact_email"] == "jane@example.com"

    def test_fallback_to_contact_url(self):
        """Test fallback to contact_url when no email found"""
        profile = {
            "name": "Test Company",
            "standard_fields": {
                "contacts": []
            },
            "contact_url": "https://example.com/contact"
        }
        scoring = {"rationale": "Good fit"}

        with patch('emailer.client.chat.completions.create') as mock_create:
            mock_create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(
                    content='{"subject": "Test", "body": "Hello", "hook_fact": "fact"}'
                ))]
            )

            result = draft_email(profile, scoring)

            assert result["contact_email"] is None
            assert result["contact_url"] == "https://example.com/contact"

    def test_word_count_calculation(self):
        """Test that word count is calculated correctly"""
        profile = {
            "name": "Test Company",
            "standard_fields": {"contacts": []},
            "contact_url": "https://example.com/contact"
        }
        scoring = {"rationale": "Good fit"}

        with patch('emailer.client.chat.completions.create') as mock_create:
            mock_create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(
                    content='{"subject": "Test", "body": "Hello world test", "hook_fact": "fact"}'
                ))]
            )

            result = draft_email(profile, scoring)

            assert result["word_count"] == 3

    def test_email_trimming_when_too_long(self):
        """Test that long emails are trimmed"""
        profile = {
            "name": "Test Company",
            "standard_fields": {"contacts": []},
            "contact_url": "https://example.com/contact"
        }
        scoring = {"rationale": "Good fit"}

        long_body = " ".join(["word"] * 150)  # 150 words

        with patch('emailer.client.chat.completions.create') as mock_create:
            # First call returns long email, second call returns trimmed
            mock_create.side_effect = [
                MagicMock(choices=[MagicMock(message=MagicMock(
                    content=f'{{"subject": "Test", "body": "{long_body}", "hook_fact": "fact"}}'
                ))]),
                MagicMock(choices=[MagicMock(message=MagicMock(
                    content="Trimmed email with fewer words"
                ))])
            ]

            result = draft_email(profile, scoring)

            # Should have called trim function
            assert mock_create.call_count == 2
            assert result["word_count"] <= 120

    def test_error_handling_returns_fallback(self):
        """Test that errors return fallback email"""
        profile = {
            "name": "Test Company",
            "standard_fields": {"contacts": []},
            "contact_url": "https://example.com/contact"
        }
        scoring = {"rationale": "Good fit"}

        with patch('emailer.client.chat.completions.create') as mock_create:
            mock_create.side_effect = Exception("API Error")

            result = draft_email(profile, scoring)

            assert "Sparkit x Test Company" in result["subject"]
            assert result["body"] == "Let's explore a partnership."
            assert result["word_count"] == 4

    def test_multiple_contacts_uses_first(self):
        """Test that first contact with email is used"""
        profile = {
            "name": "Test Company",
            "standard_fields": {
                "contacts": [
                    {"name": "John", "email": "john@example.com"},
                    {"name": "Jane", "email": "jane@example.com"}
                ]
            },
            "contact_url": "https://example.com/contact"
        }
        scoring = {"rationale": "Good fit"}

        with patch('emailer.client.chat.completions.create') as mock_create:
            mock_create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(
                    content='{"subject": "Test", "body": "Hello", "hook_fact": "fact"}'
                ))]
            )

            result = draft_email(profile, scoring)

            assert result["contact_email"] == "john@example.com"

    def test_subject_line_generation(self):
        """Test that subject line is generated"""
        profile = {
            "name": "Test Company",
            "standard_fields": {"contacts": []},
            "contact_url": "https://example.com/contact"
        }
        scoring = {"rationale": "Good fit"}

        with patch('emailer.client.chat.completions.create') as mock_create:
            mock_create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(
                    content='{"subject": "Partnership: Indie designers + your expertise", "body": "Hello", "hook_fact": "fact"}'
                ))]
            )

            result = draft_email(profile, scoring)

            assert result["subject"] == "Partnership: Indie designers + your expertise"

    def test_hook_fact_extraction(self):
        """Test that hook fact is extracted"""
        profile = {
            "name": "Test Company",
            "standard_fields": {"contacts": []},
            "contact_url": "https://example.com/contact"
        }
        scoring = {"rationale": "Good fit"}

        with patch('emailer.client.chat.completions.create') as mock_create:
            mock_create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(
                    content='{"subject": "Test", "body": "Hello", "hook_fact": "You work with emerging designers"}'
                ))]
            )

            result = draft_email(profile, scoring)

            assert result["hook_fact"] == "You work with emerging designers"

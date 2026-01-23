"""Tests for tmail.composer module."""

import os

import pytest

from tmail.composer import (
    ComposerError,
    ComposedEmail,
    generate_template,
    get_editor,
    parse_template,
    TEMPLATE_SEPARATOR,
)
from tmail.config import Config, Defaults, Identity, SmtpServer


@pytest.fixture
def sample_config() -> Config:
    """Create a sample configuration for testing."""
    smtp1 = SmtpServer(name="personal_smtp", host="smtp.example.com")
    smtp2 = SmtpServer(name="work_smtp", host="smtp.company.com")
    return Config(
        defaults=Defaults(default_identity="Personal Email"),
        smtp_servers=[smtp1, smtp2],
        identities=[
            Identity(
                name="Personal Email",
                email="user@example.com",
                display_name="Test User",
                smtp_server="personal_smtp",
                reply_to=["user@example.com", "alias@example.com"],
            ),
            Identity(
                name="Work Email",
                email="work@company.com",
                display_name="",
                smtp_server="work_smtp",
                reply_to=["work@company.com"],
            ),
        ],
    )


class TestGetEditor:
    """Tests for get_editor function."""

    def test_visual_env(self, monkeypatch):
        """VISUAL environment variable takes precedence."""
        monkeypatch.setenv("VISUAL", "code")
        monkeypatch.setenv("EDITOR", "vim")
        assert get_editor() == "code"

    def test_editor_env(self, monkeypatch):
        """EDITOR environment variable is used if VISUAL not set."""
        monkeypatch.delenv("VISUAL", raising=False)
        monkeypatch.setenv("EDITOR", "nano")
        assert get_editor() == "nano"

    def test_fallback_to_vi(self, monkeypatch):
        """Falls back to vi if no environment variable set."""
        monkeypatch.delenv("VISUAL", raising=False)
        monkeypatch.delenv("EDITOR", raising=False)
        assert get_editor() == "vi"


class TestGenerateTemplate:
    """Tests for generate_template function."""

    def test_includes_instructions(self, sample_config: Config):
        """Template includes instruction comments."""
        template = generate_template(sample_config)
        assert "# Lines starting with '#'" in template
        assert "FROM IDENTITY" in template
        assert "REPLY-TO" in template

    def test_includes_all_identities(self, sample_config: Config):
        """Template includes all configured identities."""
        template = generate_template(sample_config)
        assert "user@example.com" in template
        assert "work@company.com" in template
        assert "Personal Email" in template
        assert "Work Email" in template

    def test_default_identity_uncommented(self, sample_config: Config):
        """Default identity is uncommented."""
        template = generate_template(sample_config)
        lines = template.split("\n")
        
        # Find from lines (not comments)
        from_lines = [l for l in lines if "From:" in l and not l.strip().startswith("#")]
        
        # Default identity should be uncommented
        assert len(from_lines) == 1
        assert "user@example.com" in from_lines[0]

    def test_prefills_recipients(self, sample_config: Config):
        """Template includes pre-filled recipients."""
        template = generate_template(
            sample_config,
            recipients=["recipient@example.com"],
        )
        assert "To: recipient@example.com" in template

    def test_prefills_subject(self, sample_config: Config):
        """Template includes pre-filled subject."""
        template = generate_template(
            sample_config,
            subject="Test Subject",
        )
        assert "Subject: Test Subject" in template

    def test_includes_separator(self, sample_config: Config):
        """Template includes body separator."""
        template = generate_template(sample_config)
        assert TEMPLATE_SEPARATOR in template

    def test_prefills_body(self, sample_config: Config):
        """Template includes pre-filled body."""
        template = generate_template(
            sample_config,
            body="Hello, World!",
        )
        assert "Hello, World!" in template

    def test_shows_reply_to_options(self, sample_config: Config):
        """Template shows reply-to options for selected identity."""
        template = generate_template(
            sample_config,
            identity_name="Personal Email",
        )
        assert "alias@example.com" in template


class TestParseTemplate:
    """Tests for parse_template function."""

    def test_parses_basic_template(self):
        """parse_template extracts basic fields."""
        content = """
From: sender@example.com  # [Personal]
To: recipient@example.com
Subject: Test Subject
---
Hello, this is the body.
"""
        result = parse_template(content)
        
        assert result.from_addr == "sender@example.com"
        assert result.from_name is None
        assert result.to == ["recipient@example.com"]
        assert result.subject == "Test Subject"
        assert "Hello, this is the body." in result.body

    def test_parses_from_with_name(self):
        """parse_template extracts email and name from 'Name <email>' format."""
        content = """
From: Test User <sender@example.com>  # [Personal]
To: recipient@example.com
Subject: Test
---
Body
"""
        result = parse_template(content)
        assert result.from_addr == "sender@example.com"
        assert result.from_name == "Test User"

    def test_parses_multiple_recipients(self):
        """parse_template handles comma-separated recipients."""
        content = """
From: sender@example.com
To: user1@example.com, user2@example.com
Cc: cc1@example.com, cc2@example.com
Bcc: bcc@example.com
Subject: Test
---
Body
"""
        result = parse_template(content)
        
        assert result.to == ["user1@example.com", "user2@example.com"]
        assert result.cc == ["cc1@example.com", "cc2@example.com"]
        assert result.bcc == ["bcc@example.com"]

    def test_ignores_comments(self):
        """parse_template ignores comment lines."""
        content = """
# This is a comment
From: sender@example.com
# Another comment
To: recipient@example.com
Subject: Test
---
Body
"""
        result = parse_template(content)
        assert result.from_addr == "sender@example.com"

    def test_parses_empty_fields(self):
        """parse_template handles empty fields."""
        content = """
From: sender@example.com
To: recipient@example.com
Cc:
Bcc:
Subject:
---
"""
        result = parse_template(content)
        
        assert result.cc == []
        assert result.bcc == []
        assert result.subject == ""
        assert result.body == ""

    def test_parses_reply_to(self):
        """parse_template extracts Reply-To header."""
        content = """
From: sender@example.com
Reply-To: reply@example.com
To: recipient@example.com
Subject: Test
---
Body
"""
        result = parse_template(content)
        assert result.reply_to == "reply@example.com"

    def test_raises_on_missing_separator(self):
        """parse_template raises error when separator missing."""
        content = """
From: sender@example.com
To: recipient@example.com
Subject: Test
Body without separator
"""
        with pytest.raises(ComposerError, match="missing separator"):
            parse_template(content)

    def test_preserves_multiline_body(self):
        """parse_template preserves multiline body."""
        content = """
From: sender@example.com
To: recipient@example.com
Subject: Test
---
Line 1
Line 2
Line 3
"""
        result = parse_template(content)
        
        assert "Line 1" in result.body
        assert "Line 2" in result.body
        assert "Line 3" in result.body


class TestComposedEmail:
    """Tests for ComposedEmail dataclass."""

    def test_cancelled_flag(self):
        """ComposedEmail can indicate cancellation."""
        email = ComposedEmail(
            to=[],
            cc=[],
            bcc=[],
            from_addr="",
            from_name=None,
            reply_to=None,
            subject="",
            body="",
            cancelled=True,
        )
        assert email.cancelled is True

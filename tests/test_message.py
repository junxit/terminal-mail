"""Tests for tmail.message module."""

import tempfile
from pathlib import Path

import pytest

from tmail.message import (
    EmailData,
    MessageError,
    build_message,
    format_message_summary,
)


class TestEmailData:
    """Tests for EmailData dataclass."""

    def test_all_recipients(self):
        """all_recipients returns combined list."""
        data = EmailData(
            to=["to@example.com"],
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
            from_addr="from@example.com",
        )
        assert data.all_recipients() == [
            "to@example.com",
            "cc@example.com",
            "bcc@example.com",
        ]

    def test_is_empty_true(self):
        """is_empty returns True for empty body."""
        data = EmailData(
            to=["to@example.com"],
            from_addr="from@example.com",
            body="",
        )
        assert data.is_empty() is True

    def test_is_empty_whitespace(self):
        """is_empty returns True for whitespace-only body."""
        data = EmailData(
            to=["to@example.com"],
            from_addr="from@example.com",
            body="   \n\t  ",
        )
        assert data.is_empty() is True

    def test_is_empty_false(self):
        """is_empty returns False for non-empty body."""
        data = EmailData(
            to=["to@example.com"],
            from_addr="from@example.com",
            body="Hello",
        )
        assert data.is_empty() is False

    def test_validate_no_recipients(self):
        """validate returns error for no recipients."""
        data = EmailData(
            to=[],
            from_addr="from@example.com",
        )
        errors = data.validate()
        assert "No recipients specified" in errors

    def test_validate_no_from(self):
        """validate returns error for no from address."""
        data = EmailData(
            to=["to@example.com"],
            from_addr="",
        )
        errors = data.validate()
        assert "No from address specified" in errors

    def test_validate_attachment_not_found(self, tmp_path: Path):
        """validate returns error for missing attachment."""
        data = EmailData(
            to=["to@example.com"],
            from_addr="from@example.com",
            attachments=[tmp_path / "nonexistent.txt"],
        )
        errors = data.validate()
        assert any("not found" in e for e in errors)

    def test_validate_attachment_is_directory(self, tmp_path: Path):
        """validate returns error for directory attachment."""
        data = EmailData(
            to=["to@example.com"],
            from_addr="from@example.com",
            attachments=[tmp_path],
        )
        errors = data.validate()
        assert any("not a file" in e for e in errors)

    def test_validate_valid(self, tmp_path: Path):
        """validate returns no errors for valid data."""
        attachment = tmp_path / "test.txt"
        attachment.write_text("content")

        data = EmailData(
            to=["to@example.com"],
            from_addr="from@example.com",
            subject="Test",
            body="Hello",
            attachments=[attachment],
        )
        assert data.validate() == []


class TestBuildMessage:
    """Tests for build_message function."""

    def test_build_simple_message(self):
        """build_message creates message with basic headers."""
        data = EmailData(
            to=["to@example.com"],
            from_addr="from@example.com",
            subject="Test Subject",
            body="Test body",
        )
        msg = build_message(data)

        assert msg["From"] == "from@example.com"
        assert msg["To"] == "to@example.com"
        assert msg["Subject"] == "Test Subject"
        assert "Test body" in msg.get_content()

    def test_build_message_with_name(self):
        """build_message formats from with display name."""
        data = EmailData(
            to=["to@example.com"],
            from_addr="from@example.com",
            from_name="Test User",
            subject="Test",
            body="Test",
        )
        msg = build_message(data)

        assert "Test User" in msg["From"]
        assert "from@example.com" in msg["From"]

    def test_build_message_with_cc(self):
        """build_message includes Cc header."""
        data = EmailData(
            to=["to@example.com"],
            cc=["cc1@example.com", "cc2@example.com"],
            from_addr="from@example.com",
            subject="Test",
            body="Test",
        )
        msg = build_message(data)

        assert msg["Cc"] == "cc1@example.com, cc2@example.com"

    def test_build_message_no_bcc_header(self):
        """build_message does not include Bcc in headers."""
        data = EmailData(
            to=["to@example.com"],
            bcc=["bcc@example.com"],
            from_addr="from@example.com",
            subject="Test",
            body="Test",
        )
        msg = build_message(data)

        assert msg["Bcc"] is None

    def test_build_message_with_reply_to(self):
        """build_message includes Reply-To header."""
        data = EmailData(
            to=["to@example.com"],
            from_addr="from@example.com",
            reply_to="reply@example.com",
            subject="Test",
            body="Test",
        )
        msg = build_message(data)

        assert msg["Reply-To"] == "reply@example.com"

    def test_build_message_with_attachment(self, tmp_path: Path):
        """build_message attaches files."""
        attachment = tmp_path / "test.txt"
        attachment.write_text("attachment content")

        data = EmailData(
            to=["to@example.com"],
            from_addr="from@example.com",
            subject="Test",
            body="Test body",
            attachments=[attachment],
        )
        msg = build_message(data)

        # Message should be multipart
        assert msg.is_multipart()

        # Find attachment
        attachments = [part for part in msg.iter_attachments()]
        assert len(attachments) == 1
        assert attachments[0].get_filename() == "test.txt"

    def test_build_message_invalid(self):
        """build_message raises MessageError for invalid data."""
        data = EmailData(to=[], from_addr="")

        with pytest.raises(MessageError, match="Invalid email data"):
            build_message(data)


class TestFormatMessageSummary:
    """Tests for format_message_summary function."""

    def test_basic_summary(self):
        """format_message_summary includes basic fields."""
        data = EmailData(
            to=["to@example.com"],
            from_addr="from@example.com",
            subject="Test Subject",
            body="Test body",
        )
        summary = format_message_summary(data)

        assert "from@example.com" in summary
        assert "to@example.com" in summary
        assert "Test Subject" in summary
        assert "Test body" in summary

    def test_summary_with_attachments(self, tmp_path: Path):
        """format_message_summary shows attachment names."""
        attachment = tmp_path / "document.pdf"
        attachment.write_text("content")

        data = EmailData(
            to=["to@example.com"],
            from_addr="from@example.com",
            subject="Test",
            body="Test",
            attachments=[attachment],
        )
        summary = format_message_summary(data)

        assert "document.pdf" in summary

    def test_summary_truncates_long_body(self):
        """format_message_summary truncates long body."""
        long_body = "\n".join(f"Line {i}" for i in range(20))
        data = EmailData(
            to=["to@example.com"],
            from_addr="from@example.com",
            subject="Test",
            body=long_body,
        )
        summary = format_message_summary(data)

        assert "more lines" in summary

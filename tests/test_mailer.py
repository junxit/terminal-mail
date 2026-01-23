"""Tests for tmail.mailer module."""

from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest

from tmail.config import SmtpServer
from tmail.mailer import SendResult, send_email


@pytest.fixture
def sample_smtp_server() -> SmtpServer:
    """Create a sample SMTP server for testing."""
    return SmtpServer(
        name="test_smtp",
        host="smtp.example.com",
        ports=[587],
        user="sender@example.com",
        password_cmd="echo 'password123'",
    )


@pytest.fixture
def sample_message() -> EmailMessage:
    """Create a sample email message for testing."""
    msg = EmailMessage()
    msg["From"] = "sender@example.com"
    msg["To"] = "recipient@example.com"
    msg["Subject"] = "Test Subject"
    msg.set_content("Test body")
    return msg


class TestSendResult:
    """Tests for SendResult dataclass."""

    def test_success_result(self):
        """SendResult can indicate success."""
        result = SendResult(
            success=True,
            message="Email sent",
            attempts=1,
            smtp_response="250 OK",
        )
        assert result.success is True
        assert result.attempts == 1

    def test_failure_result(self):
        """SendResult can indicate failure."""
        result = SendResult(
            success=False,
            message="Connection refused",
            attempts=3,
        )
        assert result.success is False
        assert result.attempts == 3


class TestSendEmail:
    """Tests for send_email function."""

    @patch("tmail.mailer._send_via_smtp")
    def test_successful_send(
        self,
        mock_send: MagicMock,
        sample_message: EmailMessage,
        sample_smtp_server: SmtpServer,
    ):
        """send_email returns success on successful send."""
        mock_send.return_value = "250 OK"

        result = send_email(
            msg=sample_message,
            recipients=["recipient@example.com"],
            smtp_server=sample_smtp_server,
            retries=1,
        )

        assert result.success is True
        assert result.attempts == 1
        mock_send.assert_called_once()

    @patch("tmail.mailer._send_via_smtp")
    def test_retry_on_failure(
        self,
        mock_send: MagicMock,
        sample_message: EmailMessage,
        sample_smtp_server: SmtpServer,
    ):
        """send_email retries on failure."""
        # First call fails, second succeeds
        mock_send.side_effect = [
            OSError("Connection refused"),
            "250 OK",
        ]

        result = send_email(
            msg=sample_message,
            recipients=["recipient@example.com"],
            smtp_server=sample_smtp_server,
            retries=2,
        )

        assert result.success is True
        assert result.attempts == 2

    @patch("tmail.mailer._send_via_smtp")
    def test_all_retries_fail(
        self,
        mock_send: MagicMock,
        sample_message: EmailMessage,
        sample_smtp_server: SmtpServer,
    ):
        """send_email returns failure when all retries fail."""
        mock_send.side_effect = OSError("Connection refused")

        result = send_email(
            msg=sample_message,
            recipients=["recipient@example.com"],
            smtp_server=sample_smtp_server,
            retries=2,
        )

        assert result.success is False
        assert result.attempts == 3  # Initial + 2 retries
        assert "Connection refused" in result.message

    @patch("tmail.mailer._send_via_smtp")
    def test_tries_multiple_ports(
        self,
        mock_send: MagicMock,
        sample_message: EmailMessage,
    ):
        """send_email tries multiple ports."""
        smtp_server = SmtpServer(
            name="test",
            host="smtp.example.com",
            ports=[587, 465],  # Two ports
        )

        # First port fails, second succeeds
        mock_send.side_effect = [
            OSError("Port 587 refused"),
            "250 OK",
        ]

        result = send_email(
            msg=sample_message,
            recipients=["recipient@example.com"],
            smtp_server=smtp_server,
            retries=0,  # No retries
        )

        assert result.success is True
        assert mock_send.call_count == 2

    @patch("tmail.mailer._send_via_smtp")
    def test_verbose_output(
        self,
        mock_send: MagicMock,
        sample_message: EmailMessage,
        sample_smtp_server: SmtpServer,
        capsys,
    ):
        """send_email prints verbose output when enabled."""
        mock_send.return_value = "250 OK"

        send_email(
            msg=sample_message,
            recipients=["recipient@example.com"],
            smtp_server=sample_smtp_server,
            retries=0,
            verbose=True,
        )

        captured = capsys.readouterr()
        assert "smtp.example.com" in captured.out

"""SMTP email sending for Terminal Mail."""

from __future__ import annotations

import smtplib
import ssl
import time
from dataclasses import dataclass
from email.message import EmailMessage
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tmail.config import SmtpServer


class MailerError(Exception):
    """Raised when email sending fails."""


@dataclass
class SendResult:
    """Result of sending an email."""

    success: bool
    message: str
    attempts: int
    smtp_response: str | None = None


def send_email(
    msg: EmailMessage,
    recipients: list[str],
    smtp_server: "SmtpServer",
    retries: int = 1,
    verbose: bool = False,
) -> SendResult:
    """Send an email via SMTP.

    Args:
        msg: The email message to send.
        recipients: All recipient addresses (to + cc + bcc).
        smtp_server: SMTP server configuration.
        retries: Number of retry attempts on failure.
        verbose: Whether to print verbose output.

    Returns:
        SendResult with success status and details.
    """
    last_error: Exception | None = None
    attempts = 0

    # Get password if configured
    password = smtp_server.get_password()

    for attempt in range(retries + 1):
        attempts = attempt + 1

        for port in smtp_server.ports:
            try:
                if verbose:
                    print(f"Attempting to connect to {smtp_server.host}:{port} (attempt {attempts}/{retries + 1})")

                response = _send_via_smtp(
                    msg=msg,
                    recipients=recipients,
                    host=smtp_server.host,
                    port=port,
                    username=smtp_server.user,
                    password=password,
                    use_tls=smtp_server.use_tls,
                    verbose=verbose,
                )

                return SendResult(
                    success=True,
                    message=f"Email sent successfully via {smtp_server.host}:{port}",
                    attempts=attempts,
                    smtp_response=response,
                )

            except (smtplib.SMTPException, OSError) as e:
                last_error = e
                if verbose:
                    print(f"Failed on port {port}: {e}")
                continue

        # Wait before retry (exponential backoff)
        if attempt < retries:
            wait_time = 2 ** attempt
            if verbose:
                print(f"Waiting {wait_time}s before retry...")
            time.sleep(wait_time)

    error_msg = str(last_error) if last_error else "Unknown error"
    return SendResult(
        success=False,
        message=f"Failed to send email after {attempts} attempt(s): {error_msg}",
        attempts=attempts,
    )


def _send_via_smtp(
    msg: EmailMessage,
    recipients: list[str],
    host: str,
    port: int,
    username: str | None,
    password: str | None,
    use_tls: bool,
    verbose: bool,
) -> str:
    """Send email via SMTP connection.

    Args:
        msg: Email message to send.
        recipients: List of recipient addresses.
        host: SMTP server hostname.
        port: SMTP server port.
        username: SMTP authentication username.
        password: SMTP authentication password.
        use_tls: Whether to use TLS.
        verbose: Whether to print verbose output.

    Returns:
        SMTP server response string.

    Raises:
        smtplib.SMTPException: On SMTP errors.
        OSError: On connection errors.
    """
    # Create SSL context
    context = ssl.create_default_context()

    # Determine connection type based on port
    if port == 465:
        # SMTPS (implicit TLS)
        if verbose:
            print(f"Connecting via SMTPS to {host}:{port}")
        server = smtplib.SMTP_SSL(host, port, context=context)
    else:
        # SMTP with STARTTLS
        if verbose:
            print(f"Connecting via SMTP to {host}:{port}")
        server = smtplib.SMTP(host, port)

        if use_tls:
            if verbose:
                print("Starting TLS...")
            server.starttls(context=context)

    try:
        if verbose:
            server.set_debuglevel(1)

        # Authenticate if credentials provided
        if username and password:
            if verbose:
                print(f"Authenticating as {username}")
            server.login(username, password)

        # Get sender from message
        sender = msg["From"]
        if not sender:
            raise MailerError("Message has no From header")

        # Send the message
        if verbose:
            print(f"Sending message to {len(recipients)} recipient(s)")

        # sendmail returns a dict of failed recipients
        # Empty dict means all succeeded
        refused = server.sendmail(sender, recipients, msg.as_string())

        if refused:
            failed_addrs = ", ".join(refused.keys())
            raise MailerError(f"Some recipients were refused: {failed_addrs}")

        # Get server response
        response = server.noop()
        return f"250 OK (server response: {response})"

    finally:
        try:
            server.quit()
        except smtplib.SMTPException:
            pass  # Ignore errors on quit


def test_connection(smtp_server: "SmtpServer", verbose: bool = False) -> SendResult:
    """Test SMTP connection without sending.

    Args:
        smtp_server: SMTP server configuration to test.
        verbose: Whether to print verbose output.

    Returns:
        SendResult indicating connection success/failure.
    """
    password = smtp_server.get_password()

    for port in smtp_server.ports:
        try:
            context = ssl.create_default_context()

            if port == 465:
                server = smtplib.SMTP_SSL(smtp_server.host, port, context=context)
            else:
                server = smtplib.SMTP(smtp_server.host, port)
                if smtp_server.use_tls:
                    server.starttls(context=context)

            if verbose:
                server.set_debuglevel(1)

            if smtp_server.user and password:
                server.login(smtp_server.user, password)

            server.quit()

            return SendResult(
                success=True,
                message=f"Successfully connected to {smtp_server.host}:{port}",
                attempts=1,
            )

        except (smtplib.SMTPException, OSError) as e:
            if verbose:
                print(f"Connection failed on port {port}: {e}")
            continue

    return SendResult(
        success=False,
        message=f"Failed to connect to {smtp_server.host} on any port",
        attempts=1,
    )

"""Email message building for Terminal Mail."""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class MessageError(Exception):
    """Raised when message construction fails."""


@dataclass
class EmailData:
    """Data structure for composing an email."""

    to: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    from_addr: str = ""
    from_name: str | None = None
    reply_to: str | None = None
    subject: str = ""
    body: str = ""
    attachments: list[Path] = field(default_factory=list)

    def all_recipients(self) -> list[str]:
        """Return all recipients (to + cc + bcc)."""
        return self.to + self.cc + self.bcc

    def is_empty(self) -> bool:
        """Check if the message body is empty."""
        return not self.body.strip()

    def validate(self) -> list[str]:
        """Validate the email data and return list of errors."""
        errors = []

        if not self.to:
            errors.append("No recipients specified")

        if not self.from_addr:
            errors.append("No from address specified")

        for attachment in self.attachments:
            if not attachment.exists():
                errors.append(f"Attachment not found: {attachment}")
            elif not attachment.is_file():
                errors.append(f"Attachment is not a file: {attachment}")

        return errors


def build_message(data: EmailData) -> EmailMessage:
    """Build an EmailMessage from EmailData.

    Args:
        data: Email data to build message from.

    Returns:
        Constructed EmailMessage.

    Raises:
        MessageError: If message construction fails.
    """
    errors = data.validate()
    if errors:
        raise MessageError("Invalid email data:\n" + "\n".join(f"  - {e}" for e in errors))

    msg = EmailMessage()

    # Set headers
    if data.from_name:
        msg["From"] = formataddr((data.from_name, data.from_addr))
    else:
        msg["From"] = data.from_addr

    msg["To"] = ", ".join(data.to)

    if data.cc:
        msg["Cc"] = ", ".join(data.cc)

    # Note: BCC is not included in headers, only used for envelope

    if data.reply_to:
        msg["Reply-To"] = data.reply_to

    msg["Subject"] = data.subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=_extract_domain(data.from_addr))

    # Set body
    if data.attachments:
        # Multipart message with attachments
        msg.set_content(data.body)
        for attachment_path in data.attachments:
            _add_attachment(msg, attachment_path)
    else:
        # Simple text message
        msg.set_content(data.body)

    return msg


def _extract_domain(email: str) -> str:
    """Extract domain from email address."""
    if "@" in email:
        return email.split("@")[1]
    return "localhost"


def _add_attachment(msg: EmailMessage, path: Path) -> None:
    """Add an attachment to the message.

    Args:
        msg: Message to add attachment to.
        path: Path to the file to attach.
    """
    # Determine MIME type
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type is None:
        mime_type = "application/octet-stream"

    maintype, subtype = mime_type.split("/", 1)

    # Read file content
    with open(path, "rb") as f:
        content = f.read()

    # Add attachment
    msg.add_attachment(
        content,
        maintype=maintype,
        subtype=subtype,
        filename=path.name,
    )


def message_to_string(msg: EmailMessage) -> str:
    """Convert EmailMessage to string for display/debugging."""
    return msg.as_string()


def format_message_summary(data: EmailData) -> str:
    """Format a human-readable summary of the email.

    Args:
        data: Email data to summarize.

    Returns:
        Formatted summary string.
    """
    lines = []
    lines.append(f"From: {data.from_name + ' <' + data.from_addr + '>' if data.from_name else data.from_addr}")
    lines.append(f"To: {', '.join(data.to)}")

    if data.cc:
        lines.append(f"Cc: {', '.join(data.cc)}")

    if data.bcc:
        lines.append(f"Bcc: {', '.join(data.bcc)}")

    if data.reply_to:
        lines.append(f"Reply-To: {data.reply_to}")

    lines.append(f"Subject: {data.subject}")

    if data.attachments:
        lines.append(f"Attachments: {', '.join(p.name for p in data.attachments)}")

    lines.append("")
    lines.append("--- Body ---")

    # Show first few lines of body
    body_lines = data.body.strip().split("\n")
    if len(body_lines) > 10:
        lines.extend(body_lines[:10])
        lines.append(f"... ({len(body_lines) - 10} more lines)")
    else:
        lines.extend(body_lines)

    return "\n".join(lines)

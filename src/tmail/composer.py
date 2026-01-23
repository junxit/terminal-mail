"""Interactive email composition for Terminal Mail."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tmail.config import Config, Identity
    from tmail.message import EmailData


class ComposerError(Exception):
    """Raised when email composition fails."""


TEMPLATE_SEPARATOR = "---"
HEADER_INSTRUCTIONS = """# Terminal Mail - Email Composer
# Lines starting with '#' are comments and will be ignored.
# Edit the headers and body below, then save and exit.
#
# FROM IDENTITY: Uncomment ONE line to select your sending identity.
# DISPLAY NAME: Edit the name portion to customize (e.g., "Custom Name <email>").
# REPLY-TO: Uncomment ONE line to select the reply-to address."""


@dataclass
class ComposedEmail:
    """Result of interactive composition."""

    to: list[str]
    cc: list[str]
    bcc: list[str]
    from_addr: str
    from_name: str | None  # Editable display name
    reply_to: str | None
    subject: str
    body: str
    cancelled: bool = False


def get_editor() -> str:
    """Get the user's preferred editor.

    Returns:
        Editor command (from $VISUAL, $EDITOR, or fallback to 'vi').
    """
    return os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"


def generate_template(
    config: "Config",
    recipients: list[str] | None = None,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    identity_name: str | None = None,
    reply_to: str | None = None,
    subject: str | None = None,
    body: str | None = None,
    custom_display_name: str | None = None,
) -> str:
    """Generate an email template for editing.

    Args:
        config: Configuration with available identities.
        recipients: Pre-filled To addresses.
        cc: Pre-filled Cc addresses.
        bcc: Pre-filled Bcc addresses.
        identity_name: Pre-selected identity by friendly name.
        reply_to: Pre-selected Reply-To address.
        subject: Pre-filled subject.
        body: Pre-filled body.
        custom_display_name: Custom display name override.

    Returns:
        Template string for editing.
    """
    lines = [HEADER_INSTRUCTIONS, ""]

    # Determine selected identity
    identities = config.identities
    selected_identity: Identity | None = None

    if identity_name:
        selected_identity = config.get_identity(identity_name)
    if not selected_identity and identities:
        selected_identity = config.get_default_identity()

    # FROM IDENTITY section - dropdown style
    lines.append("# ┌─── FROM IDENTITY (select one) ───┐")
    for identity in identities:
        is_selected = identity == selected_identity
        prefix = "" if is_selected else "#"
        # Use custom display name if provided for selected identity
        if is_selected and custom_display_name:
            display_name = custom_display_name
        else:
            display_name = identity.display_name
        # Format: "Display Name <email>" with friendly name as comment
        from_value = f"{display_name} <{identity.email}>" if display_name else identity.email
        lines.append(f"{prefix}From: {from_value}  # [{identity.name}]")
    lines.append("# └────────────────────────────────────┘")
    lines.append("")

    # REPLY-TO section - dropdown style for selected identity
    if selected_identity and selected_identity.reply_to:
        lines.append(f"# ┌─── REPLY-TO for [{selected_identity.name}] (select one) ───┐")
        # Default reply-to is the first one if not specified
        effective_reply_to = reply_to or selected_identity.reply_to[0]
        for rt in selected_identity.reply_to:
            is_selected = rt == effective_reply_to
            prefix = "" if is_selected else "#"
            lines.append(f"{prefix}Reply-To: {rt}")
        lines.append("# └──────────────────────────────────────────────┘")
        lines.append("")

    # Standard headers
    lines.append(f"To: {', '.join(recipients or [])}")
    lines.append(f"Cc: {', '.join(cc or [])}")
    lines.append(f"Bcc: {', '.join(bcc or [])}")
    lines.append(f"Subject: {subject or ''}")
    lines.append("")
    lines.append(TEMPLATE_SEPARATOR)
    lines.append("")

    if body:
        lines.append(body)
    else:
        lines.append("")

    return "\n".join(lines)


def parse_template(content: str) -> ComposedEmail:
    """Parse an edited template back into email data.

    Args:
        content: Edited template content.

    Returns:
        Parsed email data.

    Raises:
        ComposerError: If template is invalid.
    """
    lines = content.split("\n")

    # Find the separator
    separator_idx = -1
    for i, line in enumerate(lines):
        if line.strip() == TEMPLATE_SEPARATOR:
            separator_idx = i
            break

    if separator_idx == -1:
        raise ComposerError(
            f"Template missing separator line ('{TEMPLATE_SEPARATOR}'). "
            "Please keep the separator between headers and body."
        )

    header_lines = lines[:separator_idx]
    body_lines = lines[separator_idx + 1:]

    # Parse headers
    headers: dict[str, str] = {}
    for line in header_lines:
        line = line.strip()

        # Skip comments and empty lines
        if not line or line.startswith("#"):
            continue

        # Parse header - strip trailing comments like "# [identity name]"
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            
            # Remove trailing comment (e.g., "# [Personal Email]")
            if "  #" in value:
                value = value.split("  #")[0].strip()

            # Handle multiple values for same header (append)
            if key in headers and headers[key]:
                headers[key] = f"{headers[key]}, {value}"
            else:
                headers[key] = value

    # Extract From field and parse name/email
    from_raw = headers.get("from", "")
    from_addr = ""
    from_name: str | None = None

    if "<" in from_raw and ">" in from_raw:
        # Format: "Name <email@example.com>"
        parts = from_raw.split("<")
        from_name = parts[0].strip() if parts[0].strip() else None
        from_addr = parts[1].split(">")[0].strip()
    else:
        from_addr = from_raw

    to_str = headers.get("to", "")
    to_list = [addr.strip() for addr in to_str.split(",") if addr.strip()]

    cc_str = headers.get("cc", "")
    cc_list = [addr.strip() for addr in cc_str.split(",") if addr.strip()]

    bcc_str = headers.get("bcc", "")
    bcc_list = [addr.strip() for addr in bcc_str.split(",") if addr.strip()]

    # Parse reply-to, also strip any trailing comment
    reply_to_raw = headers.get("reply-to", "")
    if "  #" in reply_to_raw:
        reply_to_raw = reply_to_raw.split("  #")[0].strip()
    reply_to = reply_to_raw if reply_to_raw else None

    subject = headers.get("subject", "")

    # Parse body
    body = "\n".join(body_lines).strip()

    return ComposedEmail(
        to=to_list,
        cc=cc_list,
        bcc=bcc_list,
        from_addr=from_addr,
        from_name=from_name,
        reply_to=reply_to,
        subject=subject,
        body=body,
    )


def compose_interactively(
    config: "Config",
    recipients: list[str] | None = None,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    identity_name: str | None = None,
    reply_to: str | None = None,
    subject: str | None = None,
    body: str | None = None,
    custom_display_name: str | None = None,
) -> ComposedEmail:
    """Open editor for interactive email composition.

    Args:
        config: Configuration with available identities.
        recipients: Pre-filled To addresses.
        cc: Pre-filled Cc addresses.
        bcc: Pre-filled Bcc addresses.
        identity_name: Pre-selected identity by friendly name.
        reply_to: Pre-selected Reply-To address.
        subject: Pre-filled subject.
        body: Pre-filled body.
        custom_display_name: Custom display name override.

    Returns:
        Composed email data.

    Raises:
        ComposerError: If composition fails or is cancelled.
    """
    # Generate template
    template = generate_template(
        config=config,
        recipients=recipients,
        cc=cc,
        bcc=bcc,
        identity_name=identity_name,
        reply_to=reply_to,
        subject=subject,
        body=body,
        custom_display_name=custom_display_name,
    )

    # Create temp file
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".tmail",
        delete=False,
    ) as f:
        f.write(template)
        temp_path = Path(f.name)

    try:
        # Get file modification time before editing
        mtime_before = temp_path.stat().st_mtime

        # Open editor
        editor = get_editor()
        result = subprocess.run([editor, str(temp_path)])

        if result.returncode != 0:
            raise ComposerError(f"Editor exited with code {result.returncode}")

        # Check if file was modified
        mtime_after = temp_path.stat().st_mtime
        if mtime_after == mtime_before:
            # File wasn't modified - treat as cancelled
            return ComposedEmail(
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

        # Read and parse the edited content
        content = temp_path.read_text()
        return parse_template(content)

    finally:
        # Clean up temp file
        try:
            temp_path.unlink()
        except OSError:
            pass


def confirm_send(email_data: "EmailData") -> bool:
    """Prompt user to confirm sending.

    Args:
        email_data: Email data to confirm.

    Returns:
        True if user confirms, False otherwise.
    """
    from tmail.message import format_message_summary

    print("\n" + "=" * 60)
    print("EMAIL SUMMARY")
    print("=" * 60)
    print(format_message_summary(email_data))
    print("=" * 60)

    while True:
        try:
            response = input("\nSend this email? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False

        if response in ("", "y", "yes"):
            return True
        if response in ("n", "no"):
            return False

        print("Please answer 'y' or 'n'")


def read_body_from_stdin() -> str:
    """Read email body from stdin.

    Returns:
        Body text read from stdin.
    """
    if sys.stdin.isatty():
        print("Enter message body (Ctrl+D to finish):")

    lines = []
    try:
        for line in sys.stdin:
            lines.append(line)
    except KeyboardInterrupt:
        pass

    return "".join(lines)

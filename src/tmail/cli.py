"""Command-line interface for Terminal Mail."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from tmail import __version__
from tmail.config import DEFAULT_CONFIG_PATH, DEFAULT_RETRIES

if TYPE_CHECKING:
    from typing import Sequence


@dataclass
class Args:
    """Parsed command-line arguments."""

    # Recipients
    recipients: list[str] = field(default_factory=list)

    # mail-compatible options
    subject: str | None = None
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    from_addr: str | None = None
    attachments: list[Path] = field(default_factory=list)
    ignore_interrupts: bool = False
    verbose: bool = False
    no_config: bool = False
    discard_empty: bool = False

    # tmail-specific options
    config_path: Path = field(default_factory=lambda: DEFAULT_CONFIG_PATH)
    identity: str | None = None  # Friendly name of identity to use
    display_name: str | None = None  # Custom display name for this email
    reply_to: str | None = None
    interactive: bool | None = None  # None = use config default
    skip_confirmation: bool = False
    retries: int | None = None  # None = use config default
    dry_run: bool = False
    list_accounts: bool = False


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="tmail",
        description="Terminal Mail - Send email from the command line with SMTP configuration support.",
        epilog="For more information, see: https://github.com/junxit/terminal-mail",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    # Recipients (positional)
    parser.add_argument(
        "recipients",
        nargs="*",
        metavar="recipient",
        help="Email recipient address(es)",
    )

    # mail-compatible options
    mail_group = parser.add_argument_group("mail-compatible options")

    mail_group.add_argument(
        "-s",
        dest="subject",
        metavar="subject",
        help="Subject line of the message",
    )

    mail_group.add_argument(
        "-c",
        dest="cc",
        action="append",
        default=[],
        metavar="addr",
        help="Carbon copy recipient (can be specified multiple times)",
    )

    mail_group.add_argument(
        "-b",
        dest="bcc",
        action="append",
        default=[],
        metavar="addr",
        help="Blind carbon copy recipient (can be specified multiple times)",
    )

    mail_group.add_argument(
        "-r",
        dest="from_addr",
        metavar="addr",
        help="From/envelope sender address",
    )

    mail_group.add_argument(
        "-a",
        dest="attachments",
        action="append",
        default=[],
        metavar="file",
        type=Path,
        help="Attach file (can be specified multiple times)",
    )

    mail_group.add_argument(
        "-i",
        dest="ignore_interrupts",
        action="store_true",
        help="Ignore terminal interrupt signals",
    )

    mail_group.add_argument(
        "-v",
        dest="verbose",
        action="store_true",
        help="Verbose mode - show SMTP transaction details",
    )

    mail_group.add_argument(
        "-n",
        dest="no_config",
        action="store_true",
        help="Do not read the config file",
    )

    mail_group.add_argument(
        "-E",
        dest="discard_empty",
        action="store_true",
        help="Discard messages with empty body",
    )

    # tmail-specific options
    tmail_group = parser.add_argument_group("tmail-specific options")

    tmail_group.add_argument(
        "--config-path",
        dest="config_path",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        metavar="PATH",
        help=f"Path to config file (default: {DEFAULT_CONFIG_PATH})",
    )

    tmail_group.add_argument(
        "--identity",
        dest="identity",
        metavar="NAME",
        help="Identity to use by friendly name (e.g., 'Work Email')",
    )

    tmail_group.add_argument(
        "--from",
        dest="from_addr_long",
        metavar="addr",
        help="From address (can also use --identity for friendly name)",
    )

    tmail_group.add_argument(
        "--display-name",
        dest="display_name",
        metavar="NAME",
        help="Custom display name for this email (overrides identity default)",
    )

    tmail_group.add_argument(
        "--reply-to",
        dest="reply_to",
        metavar="addr",
        help="Reply-To address",
    )

    tmail_group.add_argument(
        "--interactive",
        dest="interactive",
        type=_parse_bool,
        metavar="BOOL",
        default=None,
        help="Enable/disable interactive mode (default: true)",
    )

    tmail_group.add_argument(
        "--skip-confirmation",
        dest="skip_confirmation",
        action="store_true",
        help="Skip the final send confirmation prompt",
    )

    tmail_group.add_argument(
        "--retries",
        dest="retries",
        type=int,
        metavar="N",
        default=None,
        help=f"Number of retry attempts (default: {DEFAULT_RETRIES})",
    )

    tmail_group.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Show what would be sent without actually sending",
    )

    tmail_group.add_argument(
        "--list-accounts",
        dest="list_accounts",
        action="store_true",
        help="List configured accounts and exit",
    )

    return parser


def _parse_bool(value: str) -> bool:
    """Parse a boolean string value."""
    if value.lower() in ("true", "1", "yes", "on"):
        return True
    if value.lower() in ("false", "0", "no", "off"):
        return False
    raise argparse.ArgumentTypeError(
        f"Invalid boolean value: {value}. Use true/false, yes/no, 1/0, or on/off."
    )


def parse_args(argv: Sequence[str] | None = None) -> Args:
    """Parse command-line arguments.

    Args:
        argv: Command-line arguments. Uses sys.argv[1:] if not specified.

    Returns:
        Parsed arguments as Args dataclass.
    """
    parser = create_parser()
    ns = parser.parse_args(argv)

    # Handle --from alias
    from_addr = ns.from_addr or ns.from_addr_long

    return Args(
        recipients=ns.recipients,
        subject=ns.subject,
        cc=ns.cc,
        bcc=ns.bcc,
        from_addr=from_addr,
        attachments=ns.attachments,
        ignore_interrupts=ns.ignore_interrupts,
        verbose=ns.verbose,
        no_config=ns.no_config,
        discard_empty=ns.discard_empty,
        config_path=ns.config_path,
        identity=ns.identity,
        display_name=ns.display_name,
        reply_to=ns.reply_to,
        interactive=ns.interactive,
        skip_confirmation=ns.skip_confirmation,
        retries=ns.retries,
        dry_run=ns.dry_run,
        list_accounts=ns.list_accounts,
    )


def print_help() -> None:
    """Print help message."""
    create_parser().print_help()

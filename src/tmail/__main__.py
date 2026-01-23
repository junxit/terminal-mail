"""Main entry point for Terminal Mail."""

from __future__ import annotations

import signal
import sys
from pathlib import Path

from tmail.cli import Args, parse_args
from tmail.composer import (
    ComposerError,
    compose_interactively,
    confirm_send,
    read_body_from_stdin,
)
from tmail.config import Config, ConfigError, Identity, SmtpServer, create_empty_config, load_config
from tmail.mailer import MailerError, send_email
from tmail.message import EmailData, MessageError, build_message, format_message_summary


def main(argv: list[str] | None = None) -> int:
    """Main entry point.

    Args:
        argv: Command-line arguments. Uses sys.argv[1:] if not specified.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    args = parse_args(argv)

    # Set up signal handling
    if args.ignore_interrupts:
        signal.signal(signal.SIGINT, signal.SIG_IGN)

    try:
        return _run(args)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except (ConfigError, ComposerError, MessageError, MailerError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _run(args: Args) -> int:
    """Run the main logic.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code.
    """
    # Load configuration
    if args.no_config:
        config = create_empty_config()
    else:
        try:
            config = load_config(args.config_path)
        except ConfigError as e:
            # If config file doesn't exist and we have required args, proceed without it
            if "not found" in str(e) and args.from_addr:
                print(f"Warning: {e}", file=sys.stderr)
                config = create_empty_config()
            else:
                raise

    # Handle --list-accounts
    if args.list_accounts:
        return _list_accounts(config)

    # Determine effective settings (CLI overrides config)
    interactive = args.interactive if args.interactive is not None else config.defaults.interactive
    skip_confirmation = args.skip_confirmation or config.defaults.skip_confirmation
    retries = args.retries if args.retries is not None else config.defaults.retries

    # Resolve identity
    identity: Identity | None = None
    if args.identity:
        identity = config.get_identity(args.identity)
        if not identity:
            print(f"Error: Identity '{args.identity}' not found.", file=sys.stderr)
            print(f"Available identities: {', '.join(name for name, _ in config.list_identities())}", file=sys.stderr)
            return 1
    elif args.from_addr:
        identity = config.get_identity_by_email(args.from_addr)
        if not identity and not args.no_config:
            print(f"Error: No identity configured for '{args.from_addr}'", file=sys.stderr)
            print(f"Available identities: {', '.join(f'{name} ({email})' for name, email in config.list_identities())}", file=sys.stderr)
            return 1
    elif config.identities:
        identity = config.get_default_identity()

    if not identity and not args.no_config:
        print("Error: No identity available. Configure an identity in ~/.tmail.conf or use --identity.", file=sys.stderr)
        return 1

    # Get SMTP server for identity
    smtp_server: SmtpServer | None = None
    if identity:
        smtp_server = config.get_smtp_for_identity(identity)
        if not smtp_server:
            print(f"Error: SMTP server '{identity.smtp_server}' not found for identity '{identity.name}'.", file=sys.stderr)
            return 1

    # Validate reply-to against identity's allowed addresses
    if args.reply_to and identity and args.reply_to not in identity.reply_to:
        print(f"Warning: Reply-To '{args.reply_to}' not in allowed list for '{identity.name}'.", file=sys.stderr)
        print(f"Allowed: {', '.join(identity.reply_to)}", file=sys.stderr)

    # Compose email
    if interactive and sys.stdin.isatty():
        # Interactive mode - open editor
        composed = compose_interactively(
            config=config,
            recipients=args.recipients,
            cc=args.cc,
            bcc=args.bcc,
            identity_name=identity.name if identity else None,
            reply_to=args.reply_to,
            subject=args.subject,
            body=None,
            custom_display_name=args.display_name,
        )

        if composed.cancelled:
            print("Email composition cancelled.")
            return 0

        # Update identity if from address changed
        if composed.from_addr:
            new_identity = config.get_identity_by_email(composed.from_addr)
            if new_identity:
                identity = new_identity
                smtp_server = config.get_smtp_for_identity(identity)

        # Use composed display name or the one from args/identity
        effective_display_name = composed.from_name or args.display_name or (identity.display_name if identity else None)

        email_data = EmailData(
            to=composed.to,
            cc=composed.cc,
            bcc=composed.bcc,
            from_addr=composed.from_addr,
            from_name=effective_display_name,
            reply_to=composed.reply_to,
            subject=composed.subject,
            body=composed.body,
            attachments=args.attachments,
        )
    else:
        # Non-interactive mode - read body from stdin
        body = read_body_from_stdin()

        # Use display name from args or identity default
        effective_display_name = args.display_name or (identity.display_name if identity else None)

        email_data = EmailData(
            to=args.recipients,
            cc=args.cc,
            bcc=args.bcc,
            from_addr=args.from_addr or (identity.email if identity else ""),
            from_name=effective_display_name,
            reply_to=args.reply_to,
            subject=args.subject or "",
            body=body,
            attachments=args.attachments,
        )

    # Handle empty body
    if email_data.is_empty():
        if args.discard_empty:
            if args.verbose:
                print("Message body is empty, discarding.")
            return 0
        print("Warning: Message body is empty.", file=sys.stderr)

    # Validate email data
    errors = email_data.validate()
    if errors:
        for error in errors:
            print(f"Error: {error}", file=sys.stderr)
        return 1

    # Dry run - just show what would be sent
    if args.dry_run:
        print("DRY RUN - Email would be sent:")
        print(format_message_summary(email_data))
        if smtp_server:
            print(f"\nUsing SMTP: {smtp_server.name} ({smtp_server.host})")
        return 0

    # Confirm before sending (unless skipped)
    if not skip_confirmation and sys.stdin.isatty():
        if not confirm_send(email_data):
            print("Email not sent.")
            return 0

    # Build and send the message
    if not smtp_server:
        print("Error: No SMTP server available for sending.", file=sys.stderr)
        return 1

    msg = build_message(email_data)
    recipients = email_data.all_recipients()

    if args.verbose:
        print(f"Sending email via {smtp_server.name} ({smtp_server.host})...")

    result = send_email(
        msg=msg,
        recipients=recipients,
        smtp_server=smtp_server,
        retries=retries,
        verbose=args.verbose,
    )

    if result.success:
        print(result.message)
        return 0
    else:
        print(f"Error: {result.message}", file=sys.stderr)
        return 1


def _list_accounts(config: Config) -> int:
    """List configured identities and SMTP servers.

    Args:
        config: Configuration.

    Returns:
        Exit code.
    """
    if not config.identities:
        print("No identities configured.")
        return 0

    print("SMTP Servers:")
    for server in config.smtp_servers:
        print(f"  [{server.name}]")
        print(f"    Host: {server.host}")
        print(f"    Ports: {server.ports}")

    print("\nIdentities:")
    for identity in config.identities:
        smtp = config.get_smtp_for_identity(identity)
        smtp_info = f" via [{identity.smtp_server}]" if smtp else ""
        default_marker = " (default)" if identity.name == config.defaults.default_identity else ""
        print(f"  [{identity.name}]{default_marker}")
        print(f"    Email: {identity.email}")
        print(f"    Display Name: {identity.display_name or '(none)'}")
        print(f"    SMTP Server: {identity.smtp_server}")
        print(f"    Reply-To options: {', '.join(identity.reply_to)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

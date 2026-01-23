"""Tests for tmail.cli module."""

from pathlib import Path

import pytest

from tmail.cli import Args, parse_args


class TestParseArgs:
    """Tests for parse_args function."""

    def test_empty_args(self):
        """Empty args uses defaults."""
        args = parse_args([])
        assert args.recipients == []
        assert args.subject is None
        assert args.interactive is None
        assert args.verbose is False

    def test_recipients(self):
        """Positional arguments are recipients."""
        args = parse_args(["user1@example.com", "user2@example.com"])
        assert args.recipients == ["user1@example.com", "user2@example.com"]

    def test_subject(self):
        """-s sets subject."""
        args = parse_args(["-s", "Test Subject", "user@example.com"])
        assert args.subject == "Test Subject"

    def test_cc_single(self):
        """-c sets carbon copy."""
        args = parse_args(["-c", "cc@example.com", "user@example.com"])
        assert args.cc == ["cc@example.com"]

    def test_cc_multiple(self):
        """-c can be specified multiple times."""
        args = parse_args([
            "-c", "cc1@example.com",
            "-c", "cc2@example.com",
            "user@example.com",
        ])
        assert args.cc == ["cc1@example.com", "cc2@example.com"]

    def test_bcc(self):
        """-b sets blind carbon copy."""
        args = parse_args(["-b", "bcc@example.com", "user@example.com"])
        assert args.bcc == ["bcc@example.com"]

    def test_from_short(self):
        """-r sets from address."""
        args = parse_args(["-r", "sender@example.com", "user@example.com"])
        assert args.from_addr == "sender@example.com"

    def test_from_long(self):
        """--from sets from address."""
        args = parse_args(["--from", "sender@example.com", "user@example.com"])
        assert args.from_addr == "sender@example.com"

    def test_attachments(self):
        """-a adds attachments."""
        args = parse_args([
            "-a", "/path/to/file1.txt",
            "-a", "/path/to/file2.pdf",
            "user@example.com",
        ])
        assert args.attachments == [Path("/path/to/file1.txt"), Path("/path/to/file2.pdf")]

    def test_ignore_interrupts(self):
        """-i sets ignore_interrupts."""
        args = parse_args(["-i", "user@example.com"])
        assert args.ignore_interrupts is True

    def test_verbose(self):
        """-v sets verbose."""
        args = parse_args(["-v", "user@example.com"])
        assert args.verbose is True

    def test_no_config(self):
        """-n sets no_config."""
        args = parse_args(["-n", "user@example.com"])
        assert args.no_config is True

    def test_discard_empty(self):
        """-E sets discard_empty."""
        args = parse_args(["-E", "user@example.com"])
        assert args.discard_empty is True

    def test_config_path(self):
        """--config-path sets custom config path."""
        args = parse_args(["--config-path", "/custom/path.conf", "user@example.com"])
        assert args.config_path == Path("/custom/path.conf")

    def test_reply_to(self):
        """--reply-to sets reply-to address."""
        args = parse_args(["--reply-to", "reply@example.com", "user@example.com"])
        assert args.reply_to == "reply@example.com"

    def test_interactive_true(self):
        """--interactive true enables interactive mode."""
        args = parse_args(["--interactive", "true", "user@example.com"])
        assert args.interactive is True

    def test_interactive_false(self):
        """--interactive false disables interactive mode."""
        args = parse_args(["--interactive", "false", "user@example.com"])
        assert args.interactive is False

    def test_interactive_yes_no(self):
        """--interactive accepts yes/no values."""
        args = parse_args(["--interactive", "yes", "user@example.com"])
        assert args.interactive is True

        args = parse_args(["--interactive", "no", "user@example.com"])
        assert args.interactive is False

    def test_skip_confirmation(self):
        """--skip-confirmation sets skip_confirmation."""
        args = parse_args(["--skip-confirmation", "user@example.com"])
        assert args.skip_confirmation is True

    def test_retries(self):
        """--retries sets retry count."""
        args = parse_args(["--retries", "5", "user@example.com"])
        assert args.retries == 5

    def test_dry_run(self):
        """--dry-run sets dry_run."""
        args = parse_args(["--dry-run", "user@example.com"])
        assert args.dry_run is True

    def test_list_accounts(self):
        """--list-accounts sets list_accounts."""
        args = parse_args(["--list-accounts"])
        assert args.list_accounts is True

    def test_combined_options(self):
        """Multiple options can be combined."""
        args = parse_args([
            "-s", "Test Subject",
            "-r", "sender@example.com",
            "-c", "cc@example.com",
            "-b", "bcc@example.com",
            "--reply-to", "reply@example.com",
            "-v",
            "--retries", "3",
            "recipient@example.com",
        ])
        assert args.subject == "Test Subject"
        assert args.from_addr == "sender@example.com"
        assert args.cc == ["cc@example.com"]
        assert args.bcc == ["bcc@example.com"]
        assert args.reply_to == "reply@example.com"
        assert args.verbose is True
        assert args.retries == 3
        assert args.recipients == ["recipient@example.com"]

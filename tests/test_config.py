"""Tests for tmail.config module."""

import base64
import tempfile
from pathlib import Path

import pytest

from tmail.config import (
    Config,
    ConfigError,
    Defaults,
    Identity,
    SmtpServer,
    create_empty_config,
    load_config,
)


class TestSmtpServer:
    """Tests for SmtpServer dataclass."""

    def test_get_password_none(self):
        """get_password returns None when no password configured."""
        server = SmtpServer(name="test", host="smtp.example.com")
        assert server.get_password() is None

    def test_get_password_plain(self):
        """get_password returns plain password."""
        server = SmtpServer(
            name="test",
            host="smtp.example.com",
            password="secret123",
            password_encoding="plain",
        )
        assert server.get_password() == "secret123"

    def test_get_password_base64(self):
        """get_password decodes base64 password."""
        encoded = base64.b64encode(b"secret123").decode()
        server = SmtpServer(
            name="test",
            host="smtp.example.com",
            password=encoded,
            password_encoding="base64",
        )
        assert server.get_password() == "secret123"

    def test_get_password_command(self):
        """get_password executes command."""
        server = SmtpServer(
            name="test",
            host="smtp.example.com",
            password_cmd="echo 'secret123'",
        )
        assert server.get_password() == "secret123"

    def test_get_password_command_takes_precedence(self):
        """password_cmd takes precedence over static password."""
        server = SmtpServer(
            name="test",
            host="smtp.example.com",
            password="static_password",
            password_cmd="echo 'from_command'",
        )
        assert server.get_password() == "from_command"

    def test_get_password_command_failure(self):
        """get_password raises ConfigError on command failure."""
        server = SmtpServer(
            name="test",
            host="smtp.example.com",
            password_cmd="exit 1",
        )
        with pytest.raises(ConfigError, match="Password command failed"):
            server.get_password()

    def test_get_password_invalid_base64(self):
        """get_password raises ConfigError on invalid base64."""
        server = SmtpServer(
            name="test",
            host="smtp.example.com",
            password="not-valid-base64!!!",
            password_encoding="base64",
        )
        with pytest.raises(ConfigError, match="Failed to decode base64"):
            server.get_password()


class TestIdentity:
    """Tests for Identity dataclass."""

    def test_default_reply_to(self):
        """Reply-to defaults to email address."""
        identity = Identity(
            name="test",
            email="user@example.com",
            display_name="Test User",
            smtp_server="test_smtp",
        )
        assert identity.reply_to == ["user@example.com"]

    def test_format_from_with_name(self):
        """format_from includes display name."""
        identity = Identity(
            name="test",
            email="user@example.com",
            display_name="Test User",
            smtp_server="test_smtp",
        )
        assert identity.format_from() == "Test User <user@example.com>"

    def test_format_from_custom_name(self):
        """format_from uses custom name when provided."""
        identity = Identity(
            name="test",
            email="user@example.com",
            display_name="Default Name",
            smtp_server="test_smtp",
        )
        assert identity.format_from("Custom Name") == "Custom Name <user@example.com>"

    def test_format_from_no_name(self):
        """format_from returns just email when no name."""
        identity = Identity(
            name="test",
            email="user@example.com",
            display_name="",
            smtp_server="test_smtp",
        )
        assert identity.format_from() == "user@example.com"


class TestConfig:
    """Tests for Config dataclass."""

    def _make_config(self) -> Config:
        """Create a test config."""
        smtp = SmtpServer(name="test_smtp", host="smtp.example.com")
        identity1 = Identity(
            name="personal",
            email="user@example.com",
            display_name="User",
            smtp_server="test_smtp",
        )
        identity2 = Identity(
            name="work",
            email="work@company.com",
            display_name="Work User",
            smtp_server="test_smtp",
        )
        return Config(
            defaults=Defaults(default_identity="personal"),
            smtp_servers=[smtp],
            identities=[identity1, identity2],
        )

    def test_get_smtp_server(self):
        """get_smtp_server finds by name."""
        config = self._make_config()
        server = config.get_smtp_server("test_smtp")
        assert server is not None
        assert server.host == "smtp.example.com"

    def test_get_identity(self):
        """get_identity finds by friendly name."""
        config = self._make_config()
        identity = config.get_identity("personal")
        assert identity is not None
        assert identity.email == "user@example.com"

    def test_get_identity_case_insensitive(self):
        """get_identity is case insensitive."""
        config = self._make_config()
        assert config.get_identity("PERSONAL") is not None

    def test_get_identity_by_email(self):
        """get_identity_by_email finds by email address."""
        config = self._make_config()
        identity = config.get_identity_by_email("work@company.com")
        assert identity is not None
        assert identity.name == "work"

    def test_get_default_identity(self):
        """get_default_identity returns configured default."""
        config = self._make_config()
        identity = config.get_default_identity()
        assert identity is not None
        assert identity.name == "personal"

    def test_get_smtp_for_identity(self):
        """get_smtp_for_identity returns correct server."""
        config = self._make_config()
        identity = config.get_identity("personal")
        assert identity is not None
        server = config.get_smtp_for_identity(identity)
        assert server is not None
        assert server.name == "test_smtp"

    def test_list_identities(self):
        """list_identities returns tuples of name and email."""
        config = self._make_config()
        identities = config.list_identities()
        assert ("personal", "user@example.com") in identities
        assert ("work", "work@company.com") in identities

    # Legacy compatibility tests
    def test_get_account_legacy(self):
        """get_account (legacy) works via get_identity_by_email."""
        config = self._make_config()
        account = config.get_account("user@example.com")
        assert account is not None
        assert account.name == "personal"

    def test_accounts_property(self):
        """accounts property returns identities."""
        config = self._make_config()
        assert config.accounts == config.identities


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_valid_config(self, tmp_path: Path):
        """load_config parses valid TOML config."""
        config_content = """
[defaults]
retries = 3
interactive = false
skip_confirmation = true
default_identity = "personal"

[[smtp_servers]]
name = "gmail"
host = "smtp.gmail.com"
ports = [587, 465]
user = "user@gmail.com"
password = "secret"
password_encoding = "plain"

[[identities]]
name = "personal"
email = "user@example.com"
display_name = "Test User"
smtp_server = "gmail"
reply_to = ["user@example.com", "alias@example.com"]
"""
        config_file = tmp_path / "tmail.conf"
        config_file.write_text(config_content)

        config = load_config(config_file)

        assert config.defaults.retries == 3
        assert config.defaults.interactive is False
        assert config.defaults.skip_confirmation is True
        assert config.defaults.default_identity == "personal"

        assert len(config.smtp_servers) == 1
        server = config.smtp_servers[0]
        assert server.name == "gmail"
        assert server.host == "smtp.gmail.com"
        assert server.ports == [587, 465]

        assert len(config.identities) == 1
        identity = config.identities[0]
        assert identity.name == "personal"
        assert identity.email == "user@example.com"
        assert identity.display_name == "Test User"
        assert identity.smtp_server == "gmail"
        assert identity.reply_to == ["user@example.com", "alias@example.com"]

    def test_load_config_not_found(self, tmp_path: Path):
        """load_config raises ConfigError when file not found."""
        with pytest.raises(ConfigError, match="not found"):
            load_config(tmp_path / "nonexistent.conf")

    def test_load_config_invalid_toml(self, tmp_path: Path):
        """load_config raises ConfigError for invalid TOML."""
        config_file = tmp_path / "tmail.conf"
        config_file.write_text("this is not valid toml [[[")

        with pytest.raises(ConfigError, match="Invalid TOML"):
            load_config(config_file)

    def test_load_config_no_smtp_servers(self, tmp_path: Path):
        """load_config raises ConfigError when no SMTP servers configured."""
        config_file = tmp_path / "tmail.conf"
        config_file.write_text("[defaults]\nretries = 1\n")

        with pytest.raises(ConfigError, match="No SMTP servers configured"):
            load_config(config_file)

    def test_load_config_no_identities(self, tmp_path: Path):
        """load_config raises ConfigError when no identities configured."""
        config_content = """
[[smtp_servers]]
name = "test"
host = "smtp.example.com"
"""
        config_file = tmp_path / "tmail.conf"
        config_file.write_text(config_content)

        with pytest.raises(ConfigError, match="No identities configured"):
            load_config(config_file)

    def test_load_config_invalid_smtp_reference(self, tmp_path: Path):
        """load_config raises ConfigError for invalid SMTP reference."""
        config_content = """
[[smtp_servers]]
name = "test"
host = "smtp.example.com"

[[identities]]
name = "personal"
email = "user@example.com"
smtp_server = "nonexistent"
"""
        config_file = tmp_path / "tmail.conf"
        config_file.write_text(config_content)

        with pytest.raises(ConfigError, match="unknown SMTP server"):
            load_config(config_file)

    def test_load_config_invalid_password_encoding(self, tmp_path: Path):
        """load_config raises ConfigError for invalid password encoding."""
        config_content = """
[[smtp_servers]]
name = "test"
host = "smtp.example.com"
password = "secret"
password_encoding = "invalid"

[[identities]]
name = "personal"
email = "user@example.com"
smtp_server = "test"
"""
        config_file = tmp_path / "tmail.conf"
        config_file.write_text(config_content)

        with pytest.raises(ConfigError, match="invalid password_encoding"):
            load_config(config_file)


class TestCreateEmptyConfig:
    """Tests for create_empty_config function."""

    def test_creates_empty_config(self):
        """create_empty_config returns config with no identities."""
        config = create_empty_config()
        assert config.identities == []
        assert config.smtp_servers == []
        assert config.defaults.retries == 1

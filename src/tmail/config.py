"""Configuration file handling for Terminal Mail."""

from __future__ import annotations

import base64
import os
import stat
import subprocess
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[import-not-found]

if TYPE_CHECKING:
    from typing import Any

DEFAULT_CONFIG_PATH = Path.home() / ".tmail.conf"
DEFAULT_SMTP_PORT = 587
DEFAULT_RETRIES = 1


class ConfigError(Exception):
    """Raised when configuration is invalid or cannot be loaded."""


@dataclass
class SmtpServer:
    """SMTP server configuration."""

    name: str  # Friendly name for selection
    host: str
    ports: list[int] = field(default_factory=lambda: [DEFAULT_SMTP_PORT])
    user: str | None = None
    password: str | None = None  # Plain or encoded password
    password_cmd: str | None = None  # Command to retrieve password
    password_encoding: str = "plain"  # "plain" or "base64"
    use_tls: bool = True

    def get_password(self) -> str | None:
        """Get the password, decoding if necessary."""
        # Try command first
        if self.password_cmd:
            try:
                result = subprocess.run(
                    self.password_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode != 0:
                    raise ConfigError(
                        f"Password command failed for SMTP '{self.name}': {result.stderr.strip()}"
                    )
                return result.stdout.strip()
            except subprocess.TimeoutExpired:
                raise ConfigError(
                    f"Password command timed out for SMTP '{self.name}'"
                ) from None

        # Use static password
        if not self.password:
            return None

        if self.password_encoding.lower() == "base64":
            try:
                return base64.b64decode(self.password).decode("utf-8")
            except Exception as e:
                raise ConfigError(
                    f"Failed to decode base64 password for SMTP '{self.name}': {e}"
                ) from e

        return self.password


@dataclass
class Identity:
    """Email identity (FROM address) configuration."""

    name: str  # Friendly name for selection (e.g., "John's Work Email")
    email: str  # Email address
    display_name: str  # Default display name (editable per email)
    smtp_server: str  # Reference to SmtpServer.name
    reply_to: list[str] = field(default_factory=list)  # Allowed reply-to addresses

    def __post_init__(self) -> None:
        """Set defaults after initialization."""
        if not self.reply_to:
            self.reply_to = [self.email]

    def format_from(self, custom_display_name: str | None = None) -> str:
        """Format the From header with display name."""
        name = custom_display_name or self.display_name
        if name:
            return f"{name} <{self.email}>"
        return self.email


@dataclass
class Defaults:
    """Default configuration values."""

    retries: int = DEFAULT_RETRIES
    interactive: bool = True
    skip_confirmation: bool = False
    default_identity: str | None = None  # Friendly name of default identity


@dataclass
class Config:
    """Complete configuration."""

    defaults: Defaults
    smtp_servers: list[SmtpServer]
    identities: list[Identity]

    def get_smtp_server(self, name: str) -> SmtpServer | None:
        """Find SMTP server by friendly name."""
        for server in self.smtp_servers:
            if server.name.lower() == name.lower():
                return server
        return None

    def get_identity(self, name: str) -> Identity | None:
        """Find identity by friendly name."""
        for identity in self.identities:
            if identity.name.lower() == name.lower():
                return identity
        return None

    def get_identity_by_email(self, email: str) -> Identity | None:
        """Find identity by email address."""
        for identity in self.identities:
            if identity.email.lower() == email.lower():
                return identity
        return None

    def get_default_identity(self) -> Identity | None:
        """Return the default identity."""
        if self.defaults.default_identity:
            identity = self.get_identity(self.defaults.default_identity)
            if identity:
                return identity
        return self.identities[0] if self.identities else None

    def get_smtp_for_identity(self, identity: Identity) -> SmtpServer | None:
        """Get the SMTP server for an identity."""
        return self.get_smtp_server(identity.smtp_server)

    def list_identities(self) -> list[tuple[str, str]]:
        """Return list of (friendly_name, email) tuples."""
        return [(i.name, i.email) for i in self.identities]

    def list_smtp_servers(self) -> list[str]:
        """Return list of SMTP server friendly names."""
        return [s.name for s in self.smtp_servers]

    # Legacy compatibility methods
    def get_account(self, email: str) -> Identity | None:
        """Find identity by email (legacy compatibility)."""
        return self.get_identity_by_email(email)

    def get_default_account(self) -> Identity | None:
        """Return the default identity (legacy compatibility)."""
        return self.get_default_identity()

    def list_accounts(self) -> list[str]:
        """Return list of configured email addresses (legacy compatibility)."""
        return [i.email for i in self.identities]

    @property
    def accounts(self) -> list[Identity]:
        """Legacy compatibility: return identities as accounts."""
        return self.identities


def _parse_smtp_server(data: dict[str, Any]) -> SmtpServer:
    """Parse SMTP server configuration from dict."""
    name = data.get("name")
    if not name:
        raise ConfigError("SMTP server missing required 'name' field")

    host = data.get("host")
    if not host:
        raise ConfigError(f"SMTP server '{name}' missing required 'host' field")

    ports = data.get("ports", [DEFAULT_SMTP_PORT])
    if isinstance(ports, int):
        ports = [ports]

    password_encoding = data.get("password_encoding", "plain")
    if password_encoding.lower() not in ("plain", "base64"):
        raise ConfigError(
            f"SMTP server '{name}' has invalid password_encoding: {password_encoding}. "
            "Must be 'plain' or 'base64'"
        )

    return SmtpServer(
        name=name,
        host=host,
        ports=ports,
        user=data.get("user"),
        password=data.get("password"),
        password_cmd=data.get("password_cmd"),
        password_encoding=password_encoding,
        use_tls=data.get("use_tls", True),
    )


def _parse_identity(data: dict[str, Any], smtp_servers: list[SmtpServer]) -> Identity:
    """Parse identity configuration from dict."""
    name = data.get("name")
    if not name:
        raise ConfigError("Identity missing required 'name' field")

    email = data.get("email")
    if not email:
        raise ConfigError(f"Identity '{name}' missing required 'email' field")

    smtp_server = data.get("smtp_server")
    if not smtp_server:
        raise ConfigError(f"Identity '{name}' missing required 'smtp_server' field")

    # Validate smtp_server reference
    server_names = [s.name.lower() for s in smtp_servers]
    if smtp_server.lower() not in server_names:
        raise ConfigError(
            f"Identity '{name}' references unknown SMTP server '{smtp_server}'. "
            f"Available: {', '.join(s.name for s in smtp_servers)}"
        )

    return Identity(
        name=name,
        email=email,
        display_name=data.get("display_name", ""),
        smtp_server=smtp_server,
        reply_to=data.get("reply_to", []),
    )


def _parse_defaults(data: dict[str, Any]) -> Defaults:
    """Parse defaults configuration from dict."""
    return Defaults(
        retries=data.get("retries", DEFAULT_RETRIES),
        interactive=data.get("interactive", True),
        skip_confirmation=data.get("skip_confirmation", False),
        default_identity=data.get("default_identity"),
    )


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from TOML file.

    Args:
        config_path: Path to config file. Uses ~/.tmail.conf if not specified.

    Returns:
        Parsed configuration.

    Raises:
        ConfigError: If config file is invalid or cannot be read.
    """
    path = config_path or DEFAULT_CONFIG_PATH
    path = Path(path).expanduser()

    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    
    # Check file permissions for security
    _check_config_permissions(path)

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Invalid TOML in config file: {e}") from e

    defaults = _parse_defaults(data.get("defaults", {}))

    # Parse SMTP servers first (identities reference them)
    smtp_servers_data = data.get("smtp_servers", [])
    if not smtp_servers_data:
        raise ConfigError("No SMTP servers configured in config file")
    smtp_servers = [_parse_smtp_server(s) for s in smtp_servers_data]

    # Parse identities
    identities_data = data.get("identities", [])
    if not identities_data:
        raise ConfigError("No identities configured in config file")
    identities = [_parse_identity(i, smtp_servers) for i in identities_data]

    # Validate default_identity if set
    if defaults.default_identity:
        identity_names = [i.name.lower() for i in identities]
        if defaults.default_identity.lower() not in identity_names:
            raise ConfigError(
                f"Default identity '{defaults.default_identity}' not found. "
                f"Available: {', '.join(i.name for i in identities)}"
            )

    return Config(defaults=defaults, smtp_servers=smtp_servers, identities=identities)


def _check_config_permissions(config_path: Path) -> None:
    """Check config file permissions and warn if insecure.
    
    Args:
        config_path: Path to the config file.
    """
    try:
        file_stat = os.stat(config_path)
        mode = file_stat.st_mode
        
        # Check if file is readable by group or others
        is_group_readable = bool(mode & stat.S_IRGRP)
        is_other_readable = bool(mode & stat.S_IROTH)
        is_group_writable = bool(mode & stat.S_IWGRP)
        is_other_writable = bool(mode & stat.S_IWOTH)
        
        if is_other_readable or is_other_writable:
            warnings.warn(
                f"\n⚠️  WARNING: Config file {config_path} is readable or writable by others!\n"
                f"   This may expose passwords and sensitive information.\n"
                f"   Recommended: chmod 600 {config_path}",
                UserWarning,
                stacklevel=3,
            )
        elif is_group_readable or is_group_writable:
            warnings.warn(
                f"\n⚠️  WARNING: Config file {config_path} is readable or writable by group!\n"
                f"   Consider restricting permissions if it contains sensitive data.\n"
                f"   Recommended: chmod 600 {config_path}",
                UserWarning,
                stacklevel=3,
            )
    except (OSError, AttributeError):
        # On Windows or if we can't check permissions, skip the check
        pass


def create_empty_config() -> Config:
    """Create an empty configuration (used when -n flag is passed)."""
    return Config(defaults=Defaults(), smtp_servers=[], identities=[])

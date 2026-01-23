# Terminal Mail (tmail)

A command-line email tool that mimics `mail`/`mailx` parameters while adding configuration-based SMTP support, interactive editing, and retry logic.

## Features

- **mail/mailx compatible** - Familiar CLI flags (`-s`, `-c`, `-b`, `-r`, `-a`, etc.)
- **Configuration-based SMTP** - Define multiple email accounts with SMTP settings
- **Secure password handling** - Passwords retrieved via command (e.g., macOS Keychain, `pass`, etc.)
- **Interactive mode** - Compose emails in your preferred editor (`$EDITOR`)
- **Retry support** - Configurable retry attempts with exponential backoff
- **Multiple accounts** - Switch between configured from/reply-to addresses

## Installation

### Using pip

```bash
# Install from source
pip install .

# Install with development dependencies
pip install ".[dev]"

# Install in editable mode for development
pip install -e ".[dev]"
```

### Using uv

```bash
# Install from source
uv pip install .

# Install with development dependencies
uv pip install ".[dev]"

# Install in editable mode for development
uv pip install -e ".[dev]"
```

### Using uvx (run without installing)

```bash
# Run directly from the project directory
uvx --from . tmail --help

# Run with specific Python version
uvx --python 3.12 --from . tmail --help
```

## Running

### After Installation (pip or uv)

```bash
# Using the installed command
tmail -s "Subject" recipient@example.com

# List configured accounts
tmail --list-accounts

# Send with specific from address
tmail -r sender@example.com -s "Subject" recipient@example.com

# Dry run (show what would be sent)
tmail --dry-run -s "Test" recipient@example.com
```

### Using Python directly

```bash
# Run as module
python -m tmail --help

# Run as module with specific Python
python3.12 -m tmail --help
```

### Using uv run (without installing)

```bash
# Run from project directory
uv run tmail --help

# Run with arguments
uv run tmail -s "Subject" recipient@example.com

# Run with specific Python version
uv run --python 3.12 tmail --help
```

### Using uvx (ephemeral environment)

```bash
# Run from project directory
uvx --from . tmail --help

# Run with full command
uvx --from . tmail -s "Hello" -r me@example.com recipient@example.com
```

## Configuration

Create a configuration file at `~/.tmail.conf` (or specify with `--config-path`).

The configuration has three sections:
1. **`[defaults]`** - Global defaults
2. **`[[smtp_servers]]`** - SMTP server configurations (can be shared by multiple identities)
3. **`[[identities]]`** - FROM address identities with friendly names

```toml
[defaults]
retries = 1
interactive = true
skip_confirmation = false
default_identity = "Personal Gmail"    # Friendly name of default identity

# SMTP Servers - define separately, reference by name in identities
[[smtp_servers]]
name = "gmail"                         # Friendly name for this server
host = "smtp.gmail.com"
ports = [587, 465]
user = "user@gmail.com"
password_cmd = "security find-generic-password -s 'gmail-tmail' -w"
use_tls = true

[[smtp_servers]]
name = "company"
host = "smtp.company.com"
ports = [587]
user = "user@company.com"
password = "c2VjcmV0MTIz"              # Base64 encoded password
password_encoding = "base64"            # "plain" (default) or "base64"
use_tls = true

# Identities - FROM addresses with friendly names
[[identities]]
name = "Personal Gmail"                 # Friendly name for selection
email = "user@gmail.com"
display_name = "Your Name"              # Editable per-email in composer
smtp_server = "gmail"                   # References smtp_servers.name
reply_to = ["user@gmail.com", "alias@gmail.com"]

[[identities]]
name = "Work Email"
email = "user@company.com"
display_name = "Your Name - Company"
smtp_server = "company"
reply_to = ["user@company.com", "team@company.com"]

[[identities]]
name = "Work Support"                   # Different identity, same SMTP
email = "support@company.com"
display_name = "Support Team"
smtp_server = "company"                 # Can reuse same SMTP server
reply_to = ["support@company.com"]
```

### Password Options

Passwords can be configured in three ways:

**1. Command (most secure, recommended):**
```toml
password_cmd = "security find-generic-password -s 'gmail-tmail' -w"  # macOS Keychain
password_cmd = "pass show email/gmail"                               # pass
password_cmd = "op item get 'Gmail' --fields password"               # 1Password
password_cmd = "echo $GMAIL_APP_PASSWORD"                            # Environment variable
```

**2. Plain text password:**
```toml
password = "your-password-here"
password_encoding = "plain"  # This is the default
```

**3. Base64 encoded password:**
```toml
# Encode with: echo -n 'your-password' | base64
password = "eW91ci1wYXNzd29yZA=="
password_encoding = "base64"
```

## Usage Examples

### Basic Usage

```bash
# Send a simple email (opens editor)
tmail recipient@example.com

# Send with subject
tmail -s "Meeting Tomorrow" recipient@example.com

# Send with CC and BCC
tmail -s "Update" -c cc@example.com -b bcc@example.com recipient@example.com

# Attach files
tmail -s "Report" -a report.pdf -a data.csv recipient@example.com
```

### Non-Interactive Mode

```bash
# Pipe body from stdin
echo "Hello, World!" | tmail -s "Greeting" --interactive false recipient@example.com

# Use here-doc
tmail -s "Status Report" --interactive false recipient@example.com << EOF
Here is the status report.

Best regards
EOF

# Skip confirmation prompt
echo "Message" | tmail -s "Subject" --interactive false --skip-confirmation recipient@example.com
```

### Scripting

```bash
# Fully non-interactive with all options
echo "Automated message" | tmail \
  -s "Automated Report" \
  -r sender@example.com \
  --reply-to noreply@example.com \
  --interactive false \
  --skip-confirmation \
  -E \
  recipient@example.com
```

### Identity Management

```bash
# List configured identities and SMTP servers
tmail --list-accounts

# Use specific identity by friendly name
tmail --identity "Work Email" -s "Work Update" recipient@example.com

# Use specific from address (looks up identity by email)
tmail -r work@company.com -s "Work Update" recipient@example.com

# Customize display name for this email only
tmail --identity "Work Email" --display-name "John (Sales)" -s "Sales Inquiry" recipient@example.com

# Specify reply-to
tmail --reply-to support@company.com -s "Support" recipient@example.com
```

## CLI Reference

### mail-compatible options

| Option | Description |
|--------|-------------|
| `-s subject` | Subject line |
| `-c addr` | Carbon copy (can repeat) |
| `-b addr` | Blind carbon copy (can repeat) |
| `-r addr` | From/sender address |
| `-a file` | Attach file (can repeat) |
| `-i` | Ignore interrupts |
| `-v` | Verbose output |
| `-n` | Do not read config file |
| `-E` | Discard empty messages |

### tmail-specific options

| Option | Description |
|--------|-------------|
| `--config-path PATH` | Custom config file location |
| `--identity NAME` | Identity to use by friendly name |
| `--from addr` | From address (looks up identity by email) |
| `--display-name NAME` | Custom display name for this email |
| `--reply-to addr` | Reply-To address |
| `--interactive BOOL` | Enable/disable interactive mode |
| `--skip-confirmation` | Skip send confirmation prompt |
| `--retries N` | Number of retry attempts |
| `--dry-run` | Show what would be sent |
| `--list-accounts` | List configured identities and SMTP servers |
| `--version` | Show version |
| `--help` | Show help |

## Testing

### Using pytest directly

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=tmail --cov-report=term-missing

# Run specific test file
python -m pytest tests/test_config.py

# Run with verbose output
python -m pytest -v
```

### Using uv

```bash
# Install dev dependencies and run tests
uv pip install -e ".[dev]"
uv run pytest

# Run with coverage
uv run pytest --cov=tmail --cov-report=term-missing

# Run specific tests
uv run pytest tests/test_cli.py -v
```

### Using uvx

```bash
# Run tests without installing
uvx --from ".[dev]" pytest

# Run with coverage
uvx --from ".[dev]" pytest --cov=tmail
```

## Development

### Setup Development Environment

**Using pip:**
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

**Using uv:**
```bash
# Create virtual environment and install
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Or use uv run directly (manages venv automatically)
uv run pytest
```

### Running Tests During Development

```bash
# Quick test run
uv run pytest

# Watch mode (requires pytest-watch)
uv pip install pytest-watch
uv run ptw

# Run specific test
uv run pytest tests/test_config.py::TestAccount -v
```

### Code Quality

```bash
# Type checking (if mypy installed)
uv run mypy src/tmail

# Format code (if black installed)
uv run black src tests

# Lint (if ruff installed)
uv run ruff check src tests
```

## Project Structure

```
terminal-mail/
├── README.md
├── LICENSE
├── pyproject.toml
├── src/
│   └── tmail/
│       ├── __init__.py      # Package version
│       ├── __main__.py      # Entry point
│       ├── cli.py           # Argument parsing
│       ├── config.py        # Config file handling
│       ├── composer.py      # Interactive editor
│       ├── mailer.py        # SMTP sending
│       └── message.py       # Email building
├── tests/
│   ├── test_cli.py
│   ├── test_config.py
│   ├── test_composer.py
│   ├── test_mailer.py
│   └── test_message.py
└── examples/
    └── tmail.conf.example
```

## License

MIT License - see [LICENSE](LICENSE) for details.

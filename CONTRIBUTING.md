# Contributing to Terminal Mail

Thank you for considering contributing to Terminal Mail! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on what's best for the community and the project

## Getting Started

### Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/terminal-mail.git
cd terminal-mail
```

### Development Setup

**Using uv (preferred):**
```bash
# Install in editable mode with dev dependencies
uv pip install -e ".[dev]"

# Or use uv run directly (auto-manages virtual environment)
uv run pytest
```

## Development Workflow

### 1. Create a Branch

```bash
# Create a feature branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/bug-description
```

### 2. Make Changes

- Write clean, readable code
- Follow existing code style and patterns
- Add Google-style docstrings for public functions and classes
- Keep functions focused and single-purpose

### 3. Write Tests

- Add tests for new features in the `tests/` directory
- Ensure existing tests still pass
- Aim for high test coverage

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=tmail --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_config.py -v
```

### 4. Update Documentation

- Update `README.md` if adding features or changing behavior
- Update `changelog.txt` with your changes

### 5. Commit Your Changes

Use clear, descriptive commit messages following this format:

```
<type>: <short summary> (50 chars or less)

<optional body>
- Bullet points summarizing key changes
- Reference changelog entries where applicable
- Explain *why* the change was made, not just *what*

<optional footer>
Closes #<issue> | Refs #<issue>
```

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation only
- `refactor:` - Code restructure without behavior change
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks (deps, configs, builds)

**Example:**
```bash
git commit -m "feat: add HTML email support

- Added multipart/alternative message builder
- Updated composer to support HTML templates
- Added tests for HTML email generation

Closes #45"
```

### 6. Push and Create Pull Request

```bash
# Push to your fork
git push origin feature/your-feature-name
```

Then create a pull request on GitHub with:
- Clear title describing the change
- Description of what changed and why
- Reference any related issues (e.g., "Fixes #123")
- Note any breaking changes

## Testing Guidelines

### Test Requirements

- All new features must include tests
- Bug fixes should include regression tests
- Tests should be independent and repeatable
- Use descriptive test names that explain what is being tested

### Test Structure

Use Google-style docstrings in tests:

```python
def test_feature_description():
    """Test that feature behaves correctly under normal conditions."""
    # Arrange
    setup_code()
    
    # Act
    result = function_under_test()
    
    # Assert
    assert result == expected_value
```

### Running Tests

Tests are automatically run after code changes if they complete in < 30 seconds.

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_config.py

# Run tests matching a pattern
uv run pytest -k "test_smtp"

# Run with verbose output
uv run pytest -v

# Stop on first failure
uv run pytest -x

# Run with coverage report
uv run pytest --cov=tmail --cov-report=term-missing
```

## Code Style

### Python Style

- Follow PEP 8 guidelines
- Use type hints where appropriate
- Maximum line length: 100 characters (flexible)
- Use descriptive variable names

### Imports

```python
# Standard library imports
import os
import sys
from pathlib import Path

# Third-party imports
# (if any)

# Local imports
from tmail.config import Config
from tmail.mailer import send_email
```

### Docstrings

Use Google-style docstrings:

```python
def send_email(recipient: str, subject: str, body: str) -> bool:
    """Send an email to the specified recipient.
    
    Args:
        recipient: Email address of the recipient.
        subject: Subject line of the email.
        body: Body content of the email.
        
    Returns:
        True if email was sent successfully, False otherwise.
        
    Raises:
        SMTPException: If SMTP connection fails.
        
    Example:
        >>> send_email("user@example.com", "Hello", "Test message")
        True
    """
    pass
```

## Code Quality Tools

```bash
# Format code with ruff
uvx ruff format src tests

# Lint with ruff
uvx ruff check src tests

# Type check with mypy
uvx mypy src/tmail
```

## Adding New Features

### Before Starting

1. Check if an issue exists; if not, create one to discuss the feature
2. Wait for maintainer feedback before investing significant time
3. Keep features focused and atomic

### Implementation Checklist

- [ ] Feature implemented and working
- [ ] Tests added with good coverage
- [ ] Documentation updated (README, changelog.txt, docstrings)
- [ ] Code follows project style
- [ ] All tests pass
- [ ] No breaking changes (or documented if necessary)

## Reporting Bugs

### Before Reporting

1. Check existing issues to avoid duplicates
2. Test with the latest version
3. Verify it's not a configuration issue

### Bug Report Template

```markdown
**Description:**
Clear description of the bug

**To Reproduce:**
Steps to reproduce:
1. Run command: `tmail ...`
2. See error

**Expected Behavior:**
What you expected to happen

**Environment:**
- OS: [e.g., macOS 14, Ubuntu 22.04]
- Python version: [e.g., 3.12.1]
- tmail version: [e.g., 0.1.0]
- Installation method: [uv, pip, uvx]

**Configuration:**
```toml
# Relevant parts of your .tmail.conf (redact sensitive info)
```

**Error Output:**
```
Paste error messages here
```
```

## Security Issues

**Do not** report security vulnerabilities publicly. Instead:
- Email the maintainers directly
- Provide detailed information about the vulnerability
- Allow time for a fix before public disclosure

## Questions?

- Open a GitHub issue for questions
- Check existing documentation first
- Be patient and respectful

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

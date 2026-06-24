# Contributing to RepoMapper

Thanks for your interest in contributing! This document outlines how to set up,
test, and submit changes.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/amurlaniakea/repomapper.git
cd repomapper

# Create and activate a virtual environment (REQUIRED — never use --break-system-packages)
python3 -m venv venv
source venv/bin/activate

# Install in editable mode with dev dependencies
make install
# Or manually: pip install -e ".[dev]"
```

## Running Tests

All changes must pass the full test suite before submitting:

```bash
make test
```

Currently 35 tests covering:
- Repository scanning (structure, entry points, dependencies, conventions)
- Probe generation (5 distinct injection vectors, framework detection)
- Probe execution (shell=False safety, timeout handling)
- Guidance generation (section assembly, char limit)
- CLI interface (subprocess invocation, JSON output)
- **Adversarial tests** (command injection via malicious paths/filenames)

### Test Policy

- **All 35 tests must pass** before a PR is merged.
- New features require corresponding tests.
- Security fixes require adversarial tests demonstrating the vulnerability (RED)
  and the fix (GREEN).

## Code Quality

```bash
make lint    # Runs ruff + mypy
make format  # Auto-format with ruff
```

Style rules:
- Python 3.10+ compatible
- Type hints on public functions
- `shell=False` for all subprocess calls (no exceptions)
- Line length: 100 characters max

## Project Structure

```
repomapper/
├── __init__.py     # Public API facade + RepoMapper + CLI
├── models.py       # Data classes (RepoMap, ProbeResult, Guidance)
├── scanner.py      # RepoScanner — repository structure analysis
├── probes.py       # ProbeGenerator + run_probe() — synthetic probe execution
└── guidance.py     # GuidanceGenerator — AGENTS.md output generation
```

## Submitting Changes

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-change`
3. Make your changes, add tests, run `make test`
4. Push and open a Pull Request
5. Ensure CI passes (tests on Python 3.10, 3.11, 3.12)

## Code of Conduct

- Be respectful and constructive
- Focus on code and ideas, not individuals
- Security issues: see SECURITY.md for responsible disclosure

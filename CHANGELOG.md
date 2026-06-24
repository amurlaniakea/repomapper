# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-24

### Added

- **Repository scanning:** Multi-language structure detection (Python, JS, TS, Go,
  Rust, Java, Ruby, C/C++, C#, PHP, Swift, Kotlin) with entry point identification,
  test file detection, config file detection, and dependency extraction.
- **Probe generation:** Synthetic probes for test runner, import check, config
  validation, syntax check, and subsystem structure verification.
- **Guidance generation:** Compact AGENTS.md-style operational guide (< 3000 chars)
  with sections for overview, structure, entry points, testing, dependencies,
  conventions, subsystems, and probe findings.
- **CLI interface:** `python3 -m repomapper <path>` with options for `--output`,
  `--json`, `--probe-count`, `--max-depth`, `--max-files`, `--no-probes`.

### Security

- **Eliminated RCE vector:** Replaced `subprocess.run(shell=True)` with
  `shlex.split()` + `shell=False` across all probe execution paths. Repository
  paths and filenames are never interpolated into shell command strings.
- **Added adversarial test suite:** 6 tests covering command injection via
  malicious directory names, config filenames, entry point names, and subsystem
  names. Tests use `$(touch <witness>)` as witness files to verify no execution.
- **Added SECURITY.md:** Documents the security model, threat model, and
  responsible disclosure process.

### Changed

- **Modularized codebase:** Split 800-line monolith into 5 focused modules
  (models, scanner, probes, guidance, __init__) with clean dependency hierarchy.
- **Improved test file detection:** Path-component-aware matching prevents false
  positives like `src/test_utils.py` being classified as test files.
- **Improved subsystem detection:** Now explores 2 levels deep instead of 1,
  producing separate subsystems for `src/auth`, `src/api`, etc.
- **Improved dependency parsing:** Uses `tomllib` for pyproject.toml instead of
  fragile regex parsing.

### Development

- **CI pipeline:** GitHub Actions workflow testing on Python 3.10, 3.11, 3.12
  with linting (ruff + mypy) and coverage reporting.
- **Makefile:** Targets for install, test, lint, format, and clean.
- **pyproject.toml:** Added `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest]`
  configuration sections.
- **CONTRIBUTING.md:** Development setup, test policy, project structure.

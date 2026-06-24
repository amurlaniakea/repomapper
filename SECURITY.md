# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Security Model

RepoMapper is a static analysis tool that scans repository structure and executes
synthetic probes to generate operational guidance. Its security model relies on
three core principles:

### 1. No Shell Interpretation

All external commands are executed via `subprocess.run()` with `shell=False`.
Paths, filenames, and configuration values are never interpolated into shell
strings. This eliminates command injection as an attack vector regardless of
malicious content in repository paths or filenames.

### 2. Argument List Isolation

User-controlled values (repo paths, config filenames, entry point names) are
passed to subprocesses as positional arguments or via `sys.argv` in inline
Python scripts. No value ever reaches a shell context where metacharacters could
be interpreted.

### 3. Bounded Execution

All probes have a 30-second timeout. Directory scanning is bounded by configurable
`max_depth` (default 3) and `max_files` (default 500) limits to prevent resource
exhaustion on very large repositories.

## Threat Model

### Out of Scope

- **Malicious repos cloned from untrusted sources:** RepoMapper treats all
  repository content as untrusted. The tool never executes repository code
  directly — it only scans file structure and runs validation probes against
  well-known commands (pytest, py_compile, etc.).
- **Compromised dependencies:** RepoMapper does not install or import any
  dependencies from the scanned repository.

### In Scope

- **Path traversal via repo argument:** Mitigated by `Path.resolve()` and
  `shell=False`.
- **Command injection via filenames:** Mitigated by `shell=False` and
  `shlex.split()`.
- **Resource exhaustion:** Mitigated by timeouts and scan limits.

## Reporting Vulnerabilities

If you discover a security vulnerability in RepoMapper, please report it
responsibly:

1. **Do not** open a public GitHub issue.
2. Email the maintainer at: **amurlaniakea@gmail.com**
3. Include: description, reproduction steps, affected version, and suggested fix.
4. You will receive acknowledgment within 48 hours and a fix within 7 days.

## Security Changelog

- **v0.1.0:** Eliminated `shell=True` from all subprocess calls. Added
  adversarial test suite covering command injection vectors.

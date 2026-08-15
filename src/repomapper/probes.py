# SPDX-FileCopyrightText: 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Probe generation and execution for RepoMapper."""

from __future__ import annotations

import py_compile
import shlex
import subprocess
from pathlib import Path
from typing import Any

from .models import RepoMap

# Directories/generated artifacts that must never count as project source.
# Path.rglob() ignores .gitignore, so these would otherwise leak into
# probes that enumerate Python files (e.g. the syntax_check probe).
EXCLUDE_DIRS = {
    "venv",
    ".venv",
    "node_modules",
    "__pycache__",
    ".git",
    "build",
    "dist",
    "*.egg-info",
}


class ProbeGenerator:
    """Generates synthetic bug-fix probes for a repository."""

    def __init__(self, repo_map: RepoMap):
        self.repo_map = repo_map

    def generate_probes(self, count: int = 5) -> list[dict[str, Any]]:
        """Generate synthetic probe tasks.

        SECURITY NOTE: All commands use shlex.quote() on interpolated values.
        No shell=True is used in _run_probe for commands with user-controlled
        interpolation. Shell operators (||, &&, |) are safe because they
        come from static template strings, not from interpolated values.
        """
        probes = []

        # SECURITY: test_runner no longer invokes pytest against the scanned
        # repo (which would execute conftest.py). It uses static analysis
        # (ast.parse) to validate test file syntax without execution,
        # plus shutil.which to detect pytest installation.
        probes.append({
            "id": "test_runner",
            "description": "Validate test suite structure",
            "type": "static_analysis",
            "expected": "Test files detected and syntactically valid",
        })

        if self.repo_map.language == "Python" and self.repo_map.entry_points:
            # SECURITY: entry_mod is derived from user-controlled path.
            # Pass it as sys.argv instead of interpolating into the -c string.
            entry_mod = self.repo_map.entry_points[0].replace(".py", "").replace("/", ".")
            quoted_mod = shlex.quote(entry_mod)
            cmd = f"python3 -c 'import importlib,sys; importlib.import_module(sys.argv[1])' {quoted_mod}"
            probes.append(
                {
                    "id": "import_check",
                    "description": "Import the main module",
                    "type": "command",
                    "command": cmd,
                    "expected": "Module imports successfully",
                }
            )

        for config in self.repo_map.config_files[:2]:
            # SECURITY: config filename is user-controlled.
            # Use a Python script file approach to avoid shell injection entirely.
            config_path = Path(self.repo_map.root) / config
            if config.endswith(".json"):
                probes.append(
                    {
                        "id": f"config_valid_{config.replace('/', '_')}",
                        "description": f"Validate {config}",
                        "type": "command",
                        "command": f"python3 -c 'import json,sys; json.load(open(sys.argv[1]))' {shlex.quote(str(config_path))}",
                        "expected": "Valid JSON",
                    }
                )
            elif config.endswith(".toml"):
                probes.append(
                    {
                        "id": f"config_valid_{config.replace('/', '_')}",
                        "description": f"Validate {config}",
                        "type": "command",
                        "command": f"python3 -c 'import tomllib,sys; tomllib.load(open(sys.argv[1],\"rb\"))' {shlex.quote(str(config_path))}",
                        "expected": "Valid TOML",
                    }
                )

        # SECURITY: syntax_check uses py_compile.compile() natively in run_probe()
        # (type="syntax"), not subprocess.
        probes.append({
            "id": "syntax_check",
            "description": "Check Python syntax via static analysis",
            "type": "syntax",
            "expected": "All Python files compile cleanly",
        })
        if self.repo_map.subsystems:
            top_subsystem = self.repo_map.subsystems[0]
            # SECURITY: subsystem name is user-controlled path component.
            quoted_subsystem = shlex.quote(str(Path(self.repo_map.root) / top_subsystem["name"]))
            probes.append(
                {
                    "id": "subsystem_structure",
                    "description": f"Check {top_subsystem['name']} subsystem structure",
                    "type": "command",
                    "command": f"ls -d {quoted_subsystem}",
                    "expected": "Subsystem directory exists and has files",
                }
            )

        return probes[:count]

    def _detect_test_command(self) -> str:
        """Return a static analysis command for test validation.

        SECURITY: Does NOT invoke pytest or execute any code from the
        scanned repo. Uses ast.parse() to validate test file syntax and
        inspect imports to detect pytest vs unittest frameworks.
        """
        if self.repo_map.language == "Python":
            return "static_analysis"
        elif self.repo_map.language in ("JavaScript", "TypeScript"):
            return "npm test -- --listTests"
        elif self.repo_map.language == "Go":
            return "go test -list . ./..."
        elif self.repo_map.language == "Rust":
            return "cargo test -- --list"
        return "echo 'No test command detected'"


def run_probe(repo_path: str, probe: dict[str, Any]) -> dict[str, Any]:
    """Run a single probe and return results.

    SECURITY: Always uses shell=False with shlex.split(). No shell expansion
    occurs, so shell metacharacters in paths/filenames are inert.
    """
    result = {
        "id": probe["id"],
        "description": probe["description"],
        "type": probe["type"],
        "command": probe.get("command", ""),
        "expected": probe.get("expected", ""),
        "passed": False,
        "output": "",
        "findings": [],
    }

    if probe["type"] == "command":
        try:
            args = shlex.split(probe["command"])
            proc = subprocess.run(
                args,
                shell=False,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=repo_path,
            )
            output = proc.stdout + proc.stderr
            result["output"] = output[:500]

            if "IMPORT_FAILED" in output or "SYNTAX_ERROR" in output or "Traceback" in output:
                if _is_missing_tool_error(output):
                    result["findings"].append("Test tool not installed in environment")
                else:
                    result["findings"].append("Error detected in output")
            elif (
                proc.returncode != 0
                and "No test command" not in output
                and "SYNTAX_ERROR" not in output
            ):
                if _is_missing_tool_error(output):
                    result["findings"].append("Test tool not installed in environment")
                else:
                    result["findings"].append(f"Non-zero exit code: {proc.returncode}")
            else:
                result["passed"] = True
                result["findings"].append("Command executed successfully")

        except subprocess.TimeoutExpired:
            result["findings"].append("Probe timed out after 30s")
        except Exception as e:
            result["findings"].append(f"Probe error: {str(e)}")

    elif probe["type"] == "static_analysis":
        # SECURITY: Static test analysis using ast.parse().
        # No subprocess, no pytest invocation, no conftest.py execution.
        import ast as _ast
        from pathlib import Path as _Path
        repo_dir = _Path(repo_path)
        errors = []
        fw = "unknown"
        try:
            py_files = list(repo_dir.rglob("test_*.py"))[:20]
            if not py_files:
                result["passed"] = True
                result["findings"].append("No test files found (*.py)")
            else:
                for f in py_files:
                    try:
                        tree = _ast.parse(f.read_text())
                        for n in _ast.walk(tree):
                            if isinstance(n, _ast.Import):
                                for a in n.names:
                                    if a.name == "pytest":
                                        fw = "pytest"
                                    elif a.name == "unittest":
                                        fw = "unittest"
                            elif isinstance(n, _ast.ImportFrom) and n.module:
                                if "pytest" in n.module:
                                    fw = "pytest"
                                elif "unittest" in n.module:
                                    fw = "unittest"
                    except SyntaxError as e:
                        errors.append(f"{f.name}: {e.msg}")
                if errors:
                    result["output"] = "\n".join(errors[:5])
                    result["findings"].append(f"Syntax errors in {len(errors)} file(s)")
                else:
                    result["passed"] = True
                    result["findings"].append(
                        f"Validated {len(py_files)} test file(s), framework: {fw}"
                    )
        except Exception as e:
            result["findings"].append(f"Static analysis error: {str(e)}")

    elif probe["type"] == "syntax":
        # SECURITY: Static syntax analysis using py_compile.compile().
        # No subprocess execution — safe for untrusted repos.
        repo_dir = Path(repo_path)
        errors = []
        all_py_files = [
            p
            for p in repo_dir.rglob("*.py")
            if not any(
                part in EXCLUDE_DIRS or part.endswith(".egg-info") for part in p.parts
            )
        ]
        py_files = all_py_files[:50]
        for py_file in py_files:
            try:
                py_compile.compile(str(py_file), doraise=True)
            except py_compile.PyCompileError as e:
                errors.append(f"{py_file.name}: {e.msg}")

        if not errors:
            result["passed"] = True
            total = len(all_py_files)
            if total > len(py_files):
                result["findings"].append(
                    f"Sampled {len(py_files)} of {total} Python files — all compiled cleanly"
                )
            else:
                result["findings"].append(
                    f"All {len(py_files)} Python files compile cleanly"
                )
        else:
            result["output"] = "\n".join(errors[:5])
            result["findings"].append(f"Syntax errors in {len(errors)} file(s)")

    return result


def _is_missing_tool_error(output: str) -> bool:
    """Check if probe output indicates a missing tool (not a real repo error).

    KNOWN LIMITATION (Claude audit, not fixed yet): the patterns below are
    intentionally broad, but \"ModuleNotFoundError\" / \"No module named\" also
    match GENUINE import failures inside the scanned repo (e.g. import_check
    on a module whose relative imports are broken). Those are real repo
    defects, not missing tools, yet they get mislabeled as
    \"Test tool not installed in environment\". Fixing this requires
    distinguishing \"the probe's own toolchain is missing\" from \"the
    scanned repo cannot import its own module\" — deferred, tracked in the
    audit report.
    """
    missing_patterns = [
        "No module named",
        "ModuleNotFoundError",
        "command not found",
        "not recognized as an internal or external command",
        "executable not found",
    ]
    return any(p in output for p in missing_patterns)

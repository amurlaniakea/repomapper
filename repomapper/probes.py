"""Probe generation and execution for RepoMapper."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Any

from .models import RepoMap, ProbeResult


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

        probes.append({
            "id": "test_runner",
            "description": "Run the test suite",
            "type": "command",
            "command": self._detect_test_command(),
            "expected": "Tests run without import errors",
        })

        if self.repo_map.language == "Python" and self.repo_map.entry_points:
            # SECURITY: entry_mod is derived from user-controlled path.
            # Pass it as sys.argv instead of interpolating into the -c string.
            entry_mod = self.repo_map.entry_points[0].replace(".py", "").replace("/", ".")
            quoted_mod = shlex.quote(entry_mod)
            cmd = f"python3 -c 'import importlib,sys; importlib.import_module(sys.argv[1])' {quoted_mod} 2>&1"
            probes.append({
                "id": "import_check",
                "description": "Import the main module",
                "type": "command",
                "command": cmd,
                "expected": "Module imports successfully",
            })

        for config in self.repo_map.config_files[:2]:
            # SECURITY: config filename is user-controlled.
            # Use a Python script file approach to avoid shell injection entirely.
            config_path = Path(self.repo_map.root) / config
            if config.endswith(".json"):
                probes.append({
                    "id": f"config_valid_{config.replace('/', '_')}",
                    "description": f"Validate {config}",
                    "type": "command",
                    "command": f"python3 -c 'import json,sys; json.load(open(sys.argv[1]))' {shlex.quote(str(config_path))} 2>&1",
                    "expected": "Valid JSON",
                })
            elif config.endswith(".toml"):
                probes.append({
                    "id": f"config_valid_{config.replace('/', '_')}",
                    "description": f"Validate {config}",
                    "type": "command",
                    "command": f"python3 -c 'import tomllib,sys; tomllib.load(open(sys.argv[1],\"rb\"))' {shlex.quote(str(config_path))} 2>&1",
                    "expected": "Valid TOML",
                })

        probes.append({
            "id": "syntax_check",
            "description": "Check Python syntax",
            "type": "command",
            "command": "python3 -m py_compile . 2>&1",
            "expected": "No syntax errors",
        })

        if self.repo_map.subsystems:
            top_subsystem = self.repo_map.subsystems[0]
            # SECURITY: subsystem name is user-controlled path component.
            quoted_subsystem = shlex.quote(str(Path(self.repo_map.root) / top_subsystem["name"]))
            probes.append({
                "id": "subsystem_structure",
                "description": f"Check {top_subsystem['name']} subsystem structure",
                "type": "command",
                "command": f"ls -d {quoted_subsystem} 2>&1",
                "expected": "Subsystem directory exists and has files",
            })

        return probes[:count]

    def _detect_test_command(self) -> str:
        """Return a safe test command without shell metacharacters.

        SECURITY: Does not use && or cd. Uses only the base command
        since _run_probe sets cwd=self.repo_path already.
        """
        if self.repo_map.language == "Python":
            framework = self.repo_map.conventions.get("test_framework", "pytest")
            if framework == "unittest":
                return "python3 -m unittest discover -s . -p 'test_*.py' 2>&1"
            else:
                return "python3 -m pytest --co -q 2>&1"
        elif self.repo_map.language in ("JavaScript", "TypeScript"):
            return "npm test -- --listTests 2>&1"
        elif self.repo_map.language == "Go":
            return "go test -list . ./... 2>&1"
        elif self.repo_map.language == "Rust":
            return "cargo test -- --list 2>&1"
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
            elif proc.returncode != 0 and "No test command" not in output and "SYNTAX_ERROR" not in output:
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

    return result


def _is_missing_tool_error(output: str) -> bool:
    """Check if probe output indicates a missing tool (not a real repo error)."""
    missing_patterns = [
        "No module named",
        "ModuleNotFoundError",
        "command not found",
        "not recognized as an internal or external command",
        "executable not found",
    ]
    return any(p in output for p in missing_patterns)

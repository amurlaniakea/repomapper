"""
RepoMapper: Repository Understanding for Coding Agents.

Based on: "Probe-and-Refine Tuning of Repository Guidance for Coding Agents"
          (arXiv:2606.20512, Jun 2026)

Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
License: AGPL-3.0
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ==========================================
# Data Models
# ==========================================

@dataclass
class RepoMap:
    """Structured representation of a repository."""
    root: str
    name: str
    language: str
    total_files: int
    total_lines: int
    directories: list[str]
    entry_points: list[str]
    test_files: list[str]
    config_files: list[str]
    doc_files: list[str]
    subsystems: list[dict[str, Any]]
    dependencies: list[str]
    conventions: dict[str, Any]


@dataclass
class ProbeResult:
    """Result of a synthetic probe task."""
    probe_id: str
    description: str
    command: str
    expected: str
    passed: bool
    output: str
    findings: list[str]


@dataclass
class Guidance:
    """Operational guidance for a repository."""
    content: str
    version: int
    probes_run: int
    probes_passed: int
    char_count: int
    sections: dict[str, str]


# ==========================================
# Repo Scanner
# ==========================================

class RepoScanner:
    """Scans a repository and builds a structured map."""

    ENTRY_POINT_PATTERNS = [
        "main.py", "app.py", "server.py", "cli.py", "__main__.py",
        "index.js", "index.ts", "server.ts", "app.ts",
        "main.go", "cmd/main.go",
        "src/main/java", "Main.java",
        "lib.rs", "main.rs",
    ]

    TEST_PATTERNS = [
        "test_", "_test.", "tests/", "/test/", "spec/", "_spec.",
        "conftest.py", "pytest.ini", "setup.cfg", "tox.ini",
        "jest.config", "vitest.config",
    ]

    CONFIG_PATTERNS = [
        "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
        "package.json", "tsconfig.json", "Cargo.toml", "go.mod",
        "Makefile", "Dockerfile", "docker-compose", ".github/",
        "CMakeLists.txt", "pom.xml", "build.gradle",
    ]

    DOC_PATTERNS = [
        "README", "CONTRIBUTING", "CHANGELOG", "LICENSE",
        "docs/", "doc/", "ARCHITECTURE",
    ]

    IGNORE_DIRS = {
        ".git", ".svn", ".hg", "__pycache__", "node_modules",
        ".venv", "venv", "env", ".env", ".tox", ".mypy_cache",
        ".pytest_cache", "dist", "build", ".eggs", ".idea", ".vscode", ".vs",
    }

    IGNORE_DIR_SUFFIXES = (".egg-info",)

    def __init__(self, repo_path: str, max_depth: int = 3, max_files: int = 500):
        self.repo_path = Path(repo_path).resolve()
        self.max_depth = max_depth
        self.max_files = max_files
        if not self.repo_path.exists():
            raise FileNotFoundError(f"Repository not found: {repo_path}")

    def scan(self) -> RepoMap:
        """Scan the repository and return a structured map."""
        total_files = 0
        total_lines = 0
        directories = []
        entry_points = []
        test_files = []
        config_files = []
        doc_files = []
        language_stats: dict[str, int] = {}

        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS and not d.endswith(self.IGNORE_DIR_SUFFIXES) and not d.startswith(".")]

            rel_root = Path(root).relative_to(self.repo_path)
            depth = len(rel_root.parts) if str(rel_root) != "." else 0
            if depth > self.max_depth:
                dirs.clear()
                continue

            if str(rel_root) != ".":
                directories.append(str(rel_root))

            for file in files:
                if total_files >= self.max_files:
                    dirs.clear()
                    break

                file_path = Path(root) / file
                rel_path = str(file_path.relative_to(self.repo_path))
                total_files += 1

                try:
                    with open(file_path, "r", errors="ignore") as f:
                        lines = len(f.readlines())
                        total_lines += lines
                except (PermissionError, OSError):
                    pass

                ext = file_path.suffix
                lang_map = {
                    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
                    ".go": "Go", ".rs": "Rust", ".java": "Java",
                    ".rb": "Ruby", ".c": "C", ".cpp": "C++",
                    ".h": "C/C++", ".cs": "C#", ".php": "PHP",
                    ".swift": "Swift", ".kt": "Kotlin",
                }
                if ext in lang_map:
                    lang = lang_map[ext]
                    language_stats[lang] = language_stats.get(lang, 0) + 1

                if self._matches_any(rel_path, self.ENTRY_POINT_PATTERNS):
                    entry_points.append(rel_path)
                if self._matches_any(rel_path, self.TEST_PATTERNS):
                    test_files.append(rel_path)
                if self._matches_any(rel_path, self.CONFIG_PATTERNS):
                    config_files.append(rel_path)
                if self._matches_any(rel_path, self.DOC_PATTERNS):
                    doc_files.append(rel_path)

        language = max(language_stats, key=language_stats.get) if language_stats else "Unknown"
        subsystems = self._identify_subsystems(directories, test_files)
        dependencies = self._extract_dependencies()
        conventions = self._detect_conventions()

        return RepoMap(
            root=str(self.repo_path),
            name=self.repo_path.name,
            language=language,
            total_files=total_files,
            total_lines=total_lines,
            directories=directories[:50],
            entry_points=entry_points[:20],
            test_files=test_files[:30],
            config_files=config_files[:20],
            doc_files=doc_files[:10],
            subsystems=subsystems,
            dependencies=dependencies[:30],
            conventions=conventions,
        )

    def _matches_any(self, path: str, patterns: list[str]) -> bool:
        """Match path against patterns using path-component-aware matching.

        For test-related patterns (test_, _test., spec/, _spec.), prevents false
        positives like 'src/test_utils.py' by requiring the file to be in a
        tests/ directory or at root level.
        For other patterns (entry points, config, docs), uses simple substring
        matching as before.
        """
        path_lower = path.lower()
        path_parts = Path(path).parts

        # Patterns that should only match in test directories or at root level
        TEST_PREFIX_PATTERNS = {"test_", "_test", "spec", "_spec"}
        TEST_DIR_PATTERNS = {"/test/", "/tests/", "/spec/"}

        for pattern in patterns:
            pat_lower = pattern.lower()

            # Check if this is a test-related pattern that needs directory awareness
            is_test_pattern = (
                any(pat_lower.startswith(p) for p in TEST_PREFIX_PATTERNS) or
                any(pat_lower.startswith(p) for p in TEST_DIR_PATTERNS)
            )

            if is_test_pattern:
                # For test patterns, require the file to be in a tests/ directory
                # or at the repo root level
                if '/' in pat_lower:
                    # Directory pattern like 'tests/' — check full path
                    if pat_lower in path_lower:
                        return True
                else:
                    # Filename pattern like 'test_' — check filename starts with pattern
                    filename = path_parts[-1].lower()
                    if filename.startswith(pat_lower):
                        parent_dirs = path_parts[:-1]
                        is_in_tests = any(
                            d.lower() in ('tests', 'test', 'spec')
                            for d in parent_dirs
                        )
                        is_at_root = len(parent_dirs) == 0
                        if is_in_tests or is_at_root:
                            return True
            else:
                # Non-test patterns — use substring matching (original behavior)
                if pat_lower in path_lower:
                    return True

        return False

    def _identify_subsystems(self, directories: list[str], test_files: list[str]) -> list[dict[str, Any]]:
        """Identify subsystems by grouping directories up to 2 levels deep.

        For repos with src/auth/, src/api/, src/models/, this produces
        separate subsystems for each subdirectory instead of collapsing
        everything into a single 'src' entry.
        """
        subsystems: dict[str, dict[str, Any]] = {}

        for d in directories:
            parts = d.split("/")
            # Use up to 2 levels: e.g., "src/auth" → "src/auth", "src/api" → "src/api"
            if len(parts) >= 2:
                key = "/".join(parts[:2])
            else:
                key = parts[0]

            if key not in subsystems:
                subsystems[key] = {
                    "name": key,
                    "file_count": 0,
                    "has_tests": False,
                    "test_files": [],
                }
            subsystems[key]["file_count"] += 1

        # Associate test files with subsystems
        for tf in test_files:
            tf_lower = tf.lower()
            for key in subsystems:
                if key.lower() in tf_lower:
                    subsystems[key]["has_tests"] = True
                    subsystems[key]["test_files"].append(tf)

        return sorted(subsystems.values(), key=lambda s: -s["file_count"])[:15]

    def _extract_dependencies(self) -> list[str]:
        deps = []
        req_file = self.repo_path / "requirements.txt"
        if req_file.exists():
            with open(req_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Extract package name (before any version specifier)
                        match = re.match(r'^([a-zA-Z0-9_-]+)', line)
                        if match:
                            deps.append(match.group(1))

        pyproject = self.repo_path / "pyproject.toml"
        if pyproject.exists():
            try:
                import tomllib
                with open(pyproject, "rb") as f:
                    data = tomllib.load(f)
                # Safely extract from PEP 621 dependencies
                project_deps = data.get("project", {}).get("dependencies", [])
                for dep in project_deps:
                    # Extract just the package name from specifier like "requests>=2.0,<3.0"
                    match = re.match(r'^([a-zA-Z0-9_-]+)', dep.strip())
                    if match:
                        deps.append(match.group(1))
            except Exception:
                pass

        package_json = self.repo_path / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    data = json.load(f)
                for section in ["dependencies", "devDependencies"]:
                    if section in data:
                        deps.extend(data[section].keys())
            except (json.JSONDecodeError, KeyError):
                pass

        return list(dict.fromkeys(deps))

    def _detect_python_test_framework(self, test_files: list[Path]) -> str:
        """Detect whether a Python repo uses pytest or unittest.

        Heuristic (in order of confidence):
        1. Check test file imports for 'pytest' or 'unittest'
        2. Check pyproject.toml / setup.cfg / requirements.txt for pytest dep
        3. Default to 'pytest' if test_*.py files exist (common convention)
        """
        # 1. Inspect imports in test files
        has_pytest_import = False
        has_unittest_import = False
        for tf in test_files:
            try:
                content = tf.read_text(errors="ignore")
                if re.search(r"^\s*import\s+pytest|^\s*from\s+pytest", content, re.M):
                    has_pytest_import = True
                if re.search(r"^\s*import\s+unittest|^\s*from\s+unittest", content, re.M):
                    has_unittest_import = True
            except OSError:
                pass

        if has_pytest_import and not has_unittest_import:
            return "pytest"
        if has_unittest_import and not has_pytest_import:
            return "unittest"
        # Both or neither import found — fall through to dependency check

        # 2. Check declared dependencies
        for dep_file in ("pyproject.toml", "setup.cfg", "requirements.txt", "Pipfile"):
            dep_path = self.repo_path / dep_file
            if dep_path.exists():
                try:
                    content = dep_path.read_text(errors="ignore")
                    if "pytest" in content:
                        return "pytest"
                except OSError:
                    pass

        # 3. Default: pytest is the most common convention for test_*.py naming
        return "pytest"

    def _detect_conventions(self) -> dict[str, Any]:
        conventions: dict[str, Any] = {}
        py_files = list(self.repo_path.glob("*.py"))[:5]
        if py_files:
            has_type_hints = False
            has_docstrings = False
            uses_fstrings = False
            indent_style = "unknown"

            for py_file in py_files:
                try:
                    with open(py_file, "r", errors="ignore") as f:
                        content = f.read()
                    if "def " in content and "->" in content:
                        has_type_hints = True
                    if '"""' in content or "'''" in content:
                        has_docstrings = True
                    if 'f"' in content or "f'" in content:
                        uses_fstrings = True
                    for line in content.split("\n"):
                        if line.startswith("    ") and not line.startswith("        "):
                            indent_style = "4 spaces"
                            break
                        elif line.startswith("\t"):
                            indent_style = "tabs"
                            break
                except (PermissionError, OSError):
                    continue

            conventions["python"] = {
                "type_hints": has_type_hints,
                "docstrings": has_docstrings,
                "f_strings": uses_fstrings,
                "indent": indent_style,
            }

        # Detect Python test framework: check imports in test files and dependencies
        test_files = list(self.repo_path.rglob("test_*.py"))[:5]
        if test_files:
            framework = self._detect_python_test_framework(test_files)
            conventions["test_framework"] = framework
        elif (self.repo_path / "package.json").exists():
            try:
                with open(self.repo_path / "package.json") as f:
                    pkg = json.load(f)
                dev_deps = pkg.get("devDependencies", {})
                if "jest" in dev_deps:
                    conventions["test_framework"] = "jest"
                elif "vitest" in dev_deps:
                    conventions["test_framework"] = "vitest"
            except (json.JSONDecodeError, KeyError):
                pass

        if (self.repo_path / "Makefile").exists():
            conventions["build_system"] = "make"
        elif (self.repo_path / "pyproject.toml").exists():
            conventions["build_system"] = "setuptools/poetry"
        elif (self.repo_path / "package.json").exists():
            conventions["build_system"] = "npm/yarn"
        elif (self.repo_path / "Cargo.toml").exists():
            conventions["build_system"] = "cargo"
        elif (self.repo_path / "go.mod").exists():
            conventions["build_system"] = "go modules"

        return conventions


# ==========================================
# Probe Generator
# ==========================================

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
            # Write a tiny temp script that validates the config, then run it.
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


# ==========================================
# Guidance Generator
# ==========================================

class GuidanceGenerator:
    """Generates operational guidance from repo map and probe results."""

    def __init__(self, repo_map: RepoMap):
        self.repo_map = repo_map

    def generate(self, probes: list[dict[str, Any]] | None = None) -> Guidance:
        """Generate compact operational guidance."""
        sections: dict[str, str] = {}
        sections["overview"] = self._gen_overview()
        sections["structure"] = self._gen_structure()
        if self.repo_map.entry_points:
            sections["entry_points"] = self._gen_entry_points()
        sections["testing"] = self._gen_testing()
        if self.repo_map.dependencies:
            sections["dependencies"] = self._gen_dependencies()
        if self.repo_map.conventions:
            sections["conventions"] = self._gen_conventions()
        if self.repo_map.subsystems:
            sections["subsystems"] = self._gen_subsystems()
        if probes:
            sections["findings"] = self._gen_findings(probes)

        content = self._combine_sections(sections)

        return Guidance(
            content=content,
            version=1,
            probes_run=len(probes) if probes else 0,
            probes_passed=sum(1 for p in probes if p.get("passed", False)) if probes else 0,
            char_count=len(content),
            sections=sections,
        )

    def _gen_overview(self) -> str:
        return (
            f"# {self.repo_map.name}\n\n"
            f"**Language:** {self.repo_map.language}  \n"
            f"**Files:** {self.repo_map.total_files}  \n"
            f"**Lines:** {self.repo_map.total_lines:,}  \n\n"
        )

    def _gen_structure(self) -> str:
        lines = ["## Structure", ""]
        top_dirs = set()
        for d in self.repo_map.directories:
            parts = d.split("/")
            if len(parts) == 1:
                top_dirs.add(parts[0])
        for d in sorted(top_dirs)[:15]:
            lines.append(f"- `{d}/`")
        lines.append("")
        return "\n".join(lines)

    def _gen_entry_points(self) -> str:
        lines = ["## Entry Points", ""]
        for ep in self.repo_map.entry_points[:10]:
            lines.append(f"- `{ep}`")
        lines.append("")
        return "\n".join(lines)

    def _gen_testing(self) -> str:
        lines = ["## Testing", ""]
        gen = ProbeGenerator(self.repo_map)
        test_cmd = gen._detect_test_command()
        if "&&" in test_cmd:
            cmd = test_cmd.split("&&")[-1].strip()
        else:
            cmd = test_cmd
        lines.append(f"**Test command:** `{cmd}`")
        lines.append("")
        if self.repo_map.test_files:
            lines.append("**Test files:**")
            for tf in self.repo_map.test_files[:10]:
                lines.append(f"- `{tf}`")
            lines.append("")
        return "\n".join(lines)

    def _gen_dependencies(self) -> str:
        lines = ["## Dependencies", ""]
        for dep in self.repo_map.dependencies[:20]:
            lines.append(f"- {dep}")
        if len(self.repo_map.dependencies) > 20:
            lines.append(f"- ... and {len(self.repo_map.dependencies) - 20} more")
        lines.append("")
        return "\n".join(lines)

    def _gen_conventions(self) -> str:
        lines = ["## Conventions", ""]
        for lang, conv in self.repo_map.conventions.items():
            if isinstance(conv, dict):
                items = ", ".join(f"{k}: {v}" for k, v in conv.items())
                lines.append(f"- **{lang}:** {items}")
            else:
                lines.append(f"- **{lang}:** {conv}")
        lines.append("")
        return "\n".join(lines)

    def _gen_subsystems(self) -> str:
        lines = ["## Subsystems", ""]
        for sub in self.repo_map.subsystems[:10]:
            test_info = " (has tests)" if sub["has_tests"] else " (no tests)"
            lines.append(f"- **{sub['name']}/** — {sub['file_count']} files{test_info}")
        lines.append("")
        return "\n".join(lines)

    def _gen_findings(self, probes: list[dict[str, Any]]) -> str:
        lines = ["## Probe Findings", ""]
        for probe in probes:
            status = "PASS" if probe.get("passed", False) else "FAIL"
            lines.append(f"- [{status}] {probe['description']}")
            if probe.get("findings"):
                for finding in probe["findings"]:
                    lines.append(f"  - {finding}")
        lines.append("")
        return "\n".join(lines)

    def _combine_sections(self, sections: dict[str, str]) -> str:
        order = ["overview", "structure", "entry_points", "subsystems",
                 "testing", "dependencies", "conventions", "findings"]
        parts = []
        total_chars = 0
        for key in order:
            if key in sections:
                section = sections[key]
                if total_chars + len(section) > 2900:
                    remaining = 2900 - total_chars
                    if remaining > 100:
                        parts.append(section[:remaining] + "\n\n...")
                    break
                parts.append(section)
                total_chars += len(section)
        return "\n".join(parts)


# ==========================================
# Main RepoMapper Class
# ==========================================

class RepoMapper:
    """
    Main class that orchestrates repository understanding.
    Scans, probes, and generates operational guidance.
    """

    def __init__(self, repo_path: str, max_depth: int = 3, max_files: int = 500):
        self.repo_path = repo_path
        self.scanner = RepoScanner(repo_path, max_depth=max_depth, max_files=max_files)

    def map(self, run_probes: bool = True, probe_count: int = 5) -> dict[str, Any]:
        """Full pipeline: scan → probe → generate guidance."""
        start_time = time.time()

        repo_map = self.scanner.scan()

        probes: list[dict[str, Any]] = []
        if run_probes:
            probe_gen = ProbeGenerator(repo_map)
            probe_defs = probe_gen.generate_probes(probe_count)
            for probe_def in probe_defs:
                result = self._run_probe(probe_def)
                probes.append(result)

        guidance_gen = GuidanceGenerator(repo_map)
        guidance = guidance_gen.generate(probes)

        duration = time.time() - start_time

        return {
            "repo_map": {
                "name": repo_map.name,
                "language": repo_map.language,
                "total_files": repo_map.total_files,
                "total_lines": repo_map.total_lines,
                "entry_points": repo_map.entry_points,
                "test_files": repo_map.test_files,
                "config_files": repo_map.config_files,
                "subsystems": repo_map.subsystems,
                "dependencies": repo_map.dependencies,
                "conventions": repo_map.conventions,
            },
            "probes": probes,
            "guidance": {
                "content": guidance.content,
                "char_count": guidance.char_count,
                "probes_run": guidance.probes_run,
                "probes_passed": guidance.probes_passed,
                "sections": list(guidance.sections.keys()),
            },
            "duration_seconds": round(duration, 2),
        }

    def _is_missing_tool_error(self, output: str) -> bool:
        """Check if probe output indicates a missing tool (not a real repo error)."""
        missing_patterns = [
            "No module named",
            "ModuleNotFoundError",
            "command not found",
            "not recognized as an internal or external command",
            "executable not found",
        ]
        return any(p in output for p in missing_patterns)

    def _run_probe(self, probe: dict[str, Any]) -> dict[str, Any]:
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
                    cwd=self.repo_path,
                )
                output = proc.stdout + proc.stderr
                result["output"] = output[:500]

                if "IMPORT_FAILED" in output or "SYNTAX_ERROR" in output or "Traceback" in output:
                    # Distinguish "tool not installed" from real errors
                    if self._is_missing_tool_error(output):
                        result["findings"].append("Test tool not installed in environment")
                    else:
                        result["findings"].append("Error detected in output")
                elif proc.returncode != 0 and "No test command" not in output and "SYNTAX_ERROR" not in output:
                    if self._is_missing_tool_error(output):
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

    def export_guidance(self, output_path: str, run_probes: bool = True) -> str:
        """Generate and export guidance to a file."""
        result = self.map(run_probes=run_probes)
        guidance = result["guidance"]["content"]
        with open(output_path, "w") as f:
            f.write(guidance)
        return guidance


# ==========================================
# CLI
# ==========================================

def main():
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(
        description="RepoMapper: Repository Understanding for Coding Agents",
        epilog="Based on arXiv:2606.20512 (Jun 2026)",
    )
    parser.add_argument("repo_path", help="Path to the repository")
    parser.add_argument("--output", "-o", help="Output file for guidance (default: AGENTS.md)")
    parser.add_argument("--no-probes", action="store_true", help="Skip running probes")
    parser.add_argument("--probe-count", type=int, default=5, help="Number of probes to run")
    parser.add_argument("--max-depth", type=int, default=3, help="Max directory depth to scan")
    parser.add_argument("--max-files", type=int, default=500, help="Max files to scan")
    parser.add_argument("--json", action="store_true", help="Output full JSON result")
    args = parser.parse_args()

    mapper = RepoMapper(args.repo_path, max_depth=args.max_depth, max_files=args.max_files)
    result = mapper.map(run_probes=not args.no_probes, probe_count=args.probe_count)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        rm = result["repo_map"]
        print(f"Repository: {rm['name']}")
        print(f"Language: {rm['language']}")
        print(f"Files: {rm['total_files']}")
        print(f"Lines: {rm['total_lines']:,}")
        print(f"Entry points: {len(rm['entry_points'])}")
        print(f"Test files: {len(rm['test_files'])}")
        print(f"Subsystems: {len(rm['subsystems'])}")
        print(f"Probes: {result['guidance']['probes_passed']}/{result['guidance']['probes_run']} passed")
        print(f"Guidance: {result['guidance']['char_count']} chars")
        print(f"Duration: {result['duration_seconds']}s")

    output = args.output or os.path.join(args.repo_path, "AGENTS.md")
    with open(output, "w") as f:
        f.write(result["guidance"]["content"])
    if not args.json:
        print(f"\nGuidance written to: {output}")


if __name__ == "__main__":
    main()

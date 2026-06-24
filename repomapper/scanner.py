"""Repository scanner for RepoMapper."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from .models import RepoMap


class RepoScanner:
    """Scans a repository and builds a structured map."""

    ENTRY_POINT_PATTERNS = [
        "main.py",
        "app.py",
        "server.py",
        "cli.py",
        "__main__.py",
        "index.js",
        "index.ts",
        "server.ts",
        "app.ts",
        "main.go",
        "cmd/main.go",
        "src/main/java",
        "Main.java",
        "lib.rs",
        "main.rs",
    ]

    TEST_PATTERNS = [
        "test_",
        "_test.",
        "tests/",
        "/test/",
        "spec/",
        "_spec.",
        "conftest.py",
        "pytest.ini",
        "setup.cfg",
        "tox.ini",
        "jest.config",
        "vitest.config",
    ]

    CONFIG_PATTERNS = [
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "package.json",
        "tsconfig.json",
        "Cargo.toml",
        "go.mod",
        "Makefile",
        "Dockerfile",
        "docker-compose",
        ".github/",
        "CMakeLists.txt",
        "pom.xml",
        "build.gradle",
    ]

    DOC_PATTERNS = [
        "README",
        "CONTRIBUTING",
        "CHANGELOG",
        "LICENSE",
        "docs/",
        "doc/",
        "ARCHITECTURE",
    ]

    IGNORE_DIRS = {
        ".git",
        ".svn",
        ".hg",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        "env",
        ".env",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        "dist",
        "build",
        ".eggs",
        ".idea",
        ".vscode",
        ".vs",
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
            dirs[:] = [
                d
                for d in dirs
                if d not in self.IGNORE_DIRS
                and not d.endswith(self.IGNORE_DIR_SUFFIXES)
                and not d.startswith(".")
            ]

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
                    with open(file_path, errors="ignore") as f:
                        lines = len(f.readlines())
                        total_lines += lines
                except (PermissionError, OSError):
                    pass

                ext = file_path.suffix
                lang_map = {
                    ".py": "Python",
                    ".js": "JavaScript",
                    ".ts": "TypeScript",
                    ".go": "Go",
                    ".rs": "Rust",
                    ".java": "Java",
                    ".rb": "Ruby",
                    ".c": "C",
                    ".cpp": "C++",
                    ".h": "C/C++",
                    ".cs": "C#",
                    ".php": "PHP",
                    ".swift": "Swift",
                    ".kt": "Kotlin",
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

        language = (
            max(language_stats, key=language_stats.get)  # type: ignore[arg-type]
            if language_stats
            else "Unknown"
        )
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
        test_prefix_patterns = {"test_", "_test", "spec", "_spec"}
        test_dir_patterns = {"/test/", "/tests/", "/spec/"}

        for pattern in patterns:
            pat_lower = pattern.lower()

            is_test_pattern = (
                any(pat_lower.startswith(p) for p in test_prefix_patterns) or
                any(pat_lower.startswith(p) for p in test_dir_patterns)
            )

            if is_test_pattern:
                # For test patterns, require the file to be in a tests/ directory
                # or at the repo root level
                if "/" in pat_lower:
                    # Directory pattern like 'tests/' — check full path
                    if pat_lower in path_lower:
                        return True
                else:
                    # Filename pattern like 'test_' — check filename starts with pattern
                    filename = path_parts[-1].lower()
                    if filename.startswith(pat_lower):
                        parent_dirs = path_parts[:-1]
                        is_in_tests = any(
                            d.lower() in ("tests", "test", "spec") for d in parent_dirs
                        )
                        is_at_root = len(parent_dirs) == 0
                        if is_in_tests or is_at_root:
                            return True
            else:
                # Non-test patterns — use substring matching (original behavior)
                if pat_lower in path_lower:
                    return True

        return False

    def _identify_subsystems(
        self, directories: list[str], test_files: list[str]
    ) -> list[dict[str, Any]]:
        """Identify subsystems by grouping directories up to 2 levels deep.

        For repos with src/auth/, src/api/, src/models/, this produces
        separate subsystems for each subdirectory instead of collapsing
        everything into a single 'src' entry.
        """
        subsystems: dict[str, dict[str, Any]] = {}

        for d in directories:
            parts = d.split("/")
            # Use up to 2 levels: e.g., "src/auth" → "src/auth", "src/api" → "src/api"
            key = "/".join(parts[:2]) if len(parts) >= 2 else parts[0]

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
                        match = re.match(r"^([a-zA-Z0-9_-]+)", line)
                        if match:
                            deps.append(match.group(1))

        pyproject = self.repo_path / "pyproject.toml"
        if pyproject.exists():
            try:
                import tomli as tomllib

                with open(pyproject, "rb") as f:
                    data = tomllib.load(f)
                # Safely extract from PEP 621 dependencies
                project_deps = data.get("project", {}).get("dependencies", [])
                for dep in project_deps:
                    # Extract just the package name from specifier like "requests>=2.0,<3.0"
                    match = re.match(r"^([a-zA-Z0-9_-]+)", dep.strip())
                    if match:
                        deps.append(match.group(1))
            except Exception:  # noqa: S110 — intentional fallback to package_json
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

        # Modern lock files — extract package names as signals
        modern_files = {
            "poetry.lock": "poetry",
            "uv.lock": "uv",
            "Pipfile": "pipenv",
            "Pipfile.lock": "pipenv",
        }
        for filename, tool in modern_files.items():
            filepath = self.repo_path / filename
            if filepath.exists():
                # Add the tool itself as a detected dependency signal
                deps.append(f"__tool__{tool}")

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
                    with open(py_file, errors="ignore") as f:
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

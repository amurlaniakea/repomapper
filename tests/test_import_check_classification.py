# SPDX-FileCopyrightText: 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Regression tests for import_check misclassification (Claude audit).

BUG: _is_missing_tool_error() decides the message looking ONLY at the output
text, ignoring which probe produced it. "ModuleNotFoundError" / "No module
named" mean different things per probe:

  - config_valid_* (TOML via tomllib): on Python 3.10 tomllib is absent from
    the stdlib — a ModuleNotFoundError here IS a real environment/tool absence
    and must stay classified as "Test tool not installed in environment".

  - import_check (imports the scanned repo's entry module): a
    ModuleNotFoundError almost always means the SCANNED REPO has a genuinely
    broken import (bad relative paths, missing __init__.py, ...) — verified on
    real repos (click: examples.complex.complex.cli; fastapi). Hiding it as
    "Test tool not installed in environment" masks real repo defects.

Tests below exercise the real subprocess path (no mocks) for import_check, and
the classification function for the tomllib case.
"""


from repomapper import ProbeGenerator, RepoMap
from repomapper.probes import _is_missing_tool_error, run_probe


def _make_repo_map(
    root,
    language="Python",
    entry_points=None,
    config_files=None,
    subsystems=None,
):
    """Create a minimal RepoMap with the requested probe-relevant fields."""
    return RepoMap(
        root=root,
        name="fixture",
        language=language,
        total_files=3,
        total_lines=10,
        directories=["tests"],
        entry_points=entry_points or [],
        test_files=["tests/test_main.py"],
        config_files=config_files or [],
        doc_files=["README.md"],
        subsystems=subsystems or [],
        dependencies=[],
        conventions={"test_framework": "pytest", "build_system": "setuptools"},
    )


def _import_check_probe(repo_path, entry_point: str) -> dict:
    """Generate the import_check probe for a repo with the given entry point."""
    repo_map = _make_repo_map(str(repo_path), entry_points=[entry_point])
    probes = ProbeGenerator(repo_map).generate_probes(count=5)
    return next(p for p in probes if p["id"] == "import_check")


class TestImportCheckMisclassification:
    """BUG: import_check genuine repo import failure mislabeled as missing tool."""

    def test_import_check_genuine_module_error_not_missing_tool(self, tmp_path):
        """Reproduces the click case: entry module with a broken internal import.

        The subprocess runs for real (cwd=repo dir): importlib.import_module()
        loads the scanned repo's own module, which raises a genuine
        ModuleNotFoundError for its broken dependency. Finding must NOT claim
        "Test tool not installed in environment" — it must report the module
        import failure.
        """
        top = tmp_path / "repo"
        (top / "click_pkg").mkdir(parents=True)
        (top / "click_pkg" / "__init__.py").write_text("")
        # Genuinely broken import inside the scanned repo's module.
        (top / "click_pkg" / "cli.py").write_text(
            "import definitely_missing_dependency\n"  # ModuleNotFoundError
        )

        probe = _import_check_probe(top, "click_pkg/cli.py")
        result = run_probe(str(top), probe)

        assert result["passed"] is False, f"broken import must fail: {result}"
        assert "Test tool not installed in environment" not in " ".join(
            result["findings"]
        ), f"genuine repo defect mislabeled as missing tool: {result['findings']}"
        assert "Module import failed: click_pkg.cli" in result["findings"], (
            f"expected exact module name in finding, got: {result['findings']}"
        )

    def test_import_check_missing_module_not_missing_tool(self, tmp_path):
        """Entry module file absent from the scanned repo is also a repo defect.

        importlib.import_module() raises ModuleNotFoundError because the scanned
        repo simply does not provide the module — same misclassification class
        as the click case.
        """
        top = tmp_path / "repo"
        top.mkdir()
        (top / "app.py").write_text("x = 1\n")

        probe = _import_check_probe(top, "nonexistent_mod.py")
        result = run_probe(str(top), probe)

        assert "Test tool not installed in environment" not in " ".join(
            result["findings"]
        ), f"missing scanned module mislabeled as missing tool: {result['findings']}"
        assert "Module import failed: nonexistent_mod" in result["findings"], (
            f"expected exact module name in finding, got: {result['findings']}"
        )


class TestConfigValidKeepsMissingToolClassification:
    """config_valid_* must keep classifying stdlib absence as missing tool."""

    def test_config_valid_tomllib_absent_is_missing_tool(self):
        """Python 3.10 lacks stdlib tomllib -> 'No module named tomllib' output.

        For config_valid probes this IS a real environment/tool absence and must
        keep producing the "Test tool not installed in environment" verdict.
        """
        output = (
            "Traceback (most recent call last):\n"
            '  File "<string>", line 1, in <module>\n'
            "ModuleNotFoundError: No module named 'tomllib'\n"
        )
        assert _is_missing_tool_error(output, "config_valid_pyproject_toml") is True

    def test_config_valid_integration_tomllib_absent_is_missing_tool(
        self, tmp_path, monkeypatch
    ):
        """End-to-end: config_valid output with tomllib absent stays classified.

        Uses a stubbed subprocess because the test interpreter (3.12) HAS
        tomllib; Python 3.10 (where the bug bites) cannot be emulated by a real
        run. The stub returns exactly what Python 3.10 would print.
        """
        top = tmp_path / "repo"
        top.mkdir()
        (top / "pyproject.toml").write_text("[project]\nname = 'x'\n")
        repo_map = _make_repo_map(str(top), config_files=["pyproject.toml"])
        probes = ProbeGenerator(repo_map).generate_probes(count=5)
        probe = next(p for p in probes if p["id"].startswith("config_valid"))

        class _FakeProc:
            returncode = 1
            stdout = ""
            stderr = (
                "Traceback (most recent call last):\n"
                "ModuleNotFoundError: No module named 'tomllib'\n"
            )

        monkeypatch.setattr("repomapper.probes.subprocess.run", lambda *a, **k: _FakeProc())

        result = run_probe(str(top), probe)

        assert result["passed"] is False
        assert "Test tool not installed in environment" in result["findings"], (
            f"tomllib absence must stay a missing-tool signal: {result['findings']}"
        )

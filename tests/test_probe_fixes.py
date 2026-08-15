# SPDX-FileCopyrightText: 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Regression tests for probes.py bugs found by Claude audit.

BUG 1: Command strings embed "2>&1" as a literal token. run_probe() executes
with shell=False + shlex.split(), so the redirection is never interpreted by
a shell — it is passed as a literal argument to the binary. `ls -d <dir> 2>&1`
becomes `ls -d <dir> '2>&1'`, which always fails with exit code 2 regardless
of the real state of the scanned repo (subsystem_structure probe).

BUG 2: The syntax probe caps at 50 .py files via `rglob("*.py")[:50]` without
(a) excluding dependency/generated directories (venv, .venv, node_modules...)
and (b) disclosing that a 50-file sample is partial when the repo has more
real Python files.
"""

import pathlib

from repomapper import ProbeGenerator, RepoMap
from repomapper.probes import run_probe


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


def _write_py_files(directory: pathlib.Path, count: int, prefix: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (directory / f"{prefix}_{i:03d}.py").write_text("x = 1\n")


def _syntax_probe(repo_path):
    """Return the generated syntax_check probe (by id, order-agnostic)."""
    repo_map = _make_repo_map(str(repo_path))
    probes = ProbeGenerator(repo_map).generate_probes(count=5)
    return next(p for p in probes if p["id"] == "syntax_check")


class TestBug1_EmbeddedRedirection:
    """BUG 1: "2>&1" embedded in command strings breaks shell=False probes."""

    def test_subsystem_structure_existing_dir_passes(self, tmp_path):
        """subsystem_structure on a valid existing dir must pass.

        With the bug, the generated command is
        `ls -d <dir> 2>&1` which shlex.split() turns into
        ['ls', '-d', '<dir>', '2>&1'] — ls fails with exit 2 even though
        the directory exists, so the probe never passes.
        """
        top = tmp_path / "repo"
        (top / "src" / "core").mkdir(parents=True)
        (top / "src" / "core" / "mod_a.py").write_text("x = 1\n")
        (top / "src" / "core" / "mod_b.py").write_text("x = 2\n")

        repo_map = _make_repo_map(
            str(top),
            subsystems=[{"name": "src/core", "file_count": 2, "has_tests": False}],
        )
        probes = ProbeGenerator(repo_map).generate_probes(count=5)
        probe = next(p for p in probes if p["id"] == "subsystem_structure")

        result = run_probe(str(top), probe)

        assert result["passed"] is True, f"findings: {result['findings']}"
        assert "Command executed successfully" in result["findings"]

    def test_python_probes_have_no_embedded_redirection(self, tmp_path):
        """No generated command probe may embed '2>&1' as a literal token.

        Guards every interpolation point: import_check, config_valid (JSON and
        TOML) and subsystem_structure. `ls -d /x 2>&1` is only valid if a
        shell interprets it; shell=False + shlex.split() passes it literally.
        """
        top = tmp_path / "repo"
        top.mkdir()
        (top / "app.py").write_text("x = 1\n")
        (top / "cfg.json").write_text("{}")
        (top / "cfg.toml").write_text("key = 1\n")
        (top / "src" / "core").mkdir(parents=True)

        repo_map = _make_repo_map(
            str(top),
            entry_points=["app.py"],
            config_files=["cfg.json", "cfg.toml"],
            subsystems=[{"name": "src/core", "file_count": 1, "has_tests": False}],
        )
        probes = ProbeGenerator(repo_map).generate_probes(count=20)

        command_probes = [p for p in probes if p.get("command")]
        assert command_probes, "expected at least one command probe"
        for probe in command_probes:
            assert "2>&1" not in probe["command"], (
                f"probe {probe['id']} embeds '2>&1': {probe['command']}"
            )


class TestBug2_SyntaxSampling:
    """BUG 2: syntax probe truncates at 50 files without honest disclosure."""

    def test_sampling_disclosed_when_more_than_50_py_files(self, tmp_path):
        """With 60 real .py files, the finding must say 'Sampled 50 of 60',
        not the misleading 'All 50 Python files compile cleanly'.
        """
        top = tmp_path / "repo"
        top.mkdir()
        _write_py_files(top, count=60, prefix="real")

        result = run_probe(str(top), _syntax_probe(top))

        assert result["passed"] is True, f"findings: {result['findings']}"
        assert any("Sampled 50 of 60" in f for f in result["findings"]), (
            f"partial sampling not disclosed in findings: {result['findings']}"
        )

    def test_dependency_dirs_excluded_from_syntax_count(self, tmp_path):
        """venv/.venv files must not fill the 50-file cap nor inflate counts."""
        top = tmp_path / "repo"
        top.mkdir()
        (top / "a.py").write_text("x = 1\n")
        (top / "b.py").write_text("x = 2\n")
        _write_py_files(top / ".venv" / "lib" / "site-packages", count=60, prefix="venv")

        result = run_probe(str(top), _syntax_probe(top))

        assert result["passed"] is True, f"findings: {result['findings']}"
        assert any("All 2 Python files compile cleanly" in f for f in result["findings"]), (
            f"venv files leaked into the syntax count: {result['findings']}"
        )

"""Adversarial tests for command injection vulnerability in RepoMapper probes.

These tests MUST FAIL against the unpatched code (RED) and PASS after the fix (GREEN).

Each test covers a DISTINCT interpolation point in ProbeGenerator → _run_probe pipeline:
1. _detect_test_command: root path interpolated into "cd {root} && ..."
2. import_check: entry_points[0] interpolated into python3 -c 'import {entry_mod}'
3. config_valid_*: root + config interpolated into python3 -c 'open("{root}/{config}")'
4. syntax_check: root path interpolated into "cd {root} && python3 -m py_compile $(find ...)"
5. subsystem_structure: root path interpolated into "ls -la {root}/{name}/"
"""
import os
import sys
import pathlib
import tempfile

import pytest

# Ensure repomapper package is importable (tests/ → parent dir)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))


def _make_repo_map(root, language="Python", entry_points=None, config_files=None, subsystems=None):
    """Create a RepoMap with a malicious path in the specified field."""
    from repomapper import RepoMap

    return RepoMap(
        root=root,
        name="evil",
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


def _run_probe_and_assert_no_execution(mapper, probe, marker_path):
    """Call _run_probe and assert the injected command did NOT execute."""
    marker = pathlib.Path(marker_path)
    if marker.exists():
        marker.unlink()

    result = mapper._run_probe(probe)

    assert not marker.exists(), (
        f"SECURITY FAIL: Command injection via probe '{probe['id']}'! "
        f"{marker} exists. Command was: {probe.get('command', 'N/A')!r}"
    )
    return result


class TestCommandInjection_FullPipeline:
    """Test the COMPLETE pipeline: ProbeGenerator.generate_probes() → _run_probe().

    Each test uses a REAL ProbeGenerator with a RepoMap that has a malicious
    path in a DIFFERENT field, covering all 5 distinct interpolation points.
    """

    def test_vector_1_detect_test_command(self):
        """Vector 1: _detect_test_command interpolates root into 'cd {root} && ...'

        BEFORE FIX: command contains "cd /tmp/evil$(touch /tmp/PWNED_V1) && ..."
        AFTER FIX: command no longer interpolates root (uses cwd instead).
        """
        from repomapper import RepoMapper, ProbeGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            malicious_root = "/tmp/evil_v1$(touch /tmp/PWNED_V1)"

            repo_map = _make_repo_map(root=malicious_root)

            gen = ProbeGenerator(repo_map)
            probes = gen.generate_probes(count=5)

            test_runner = next((p for p in probes if p["id"] == "test_runner"), None)
            assert test_runner is not None, "test_runner probe not generated"

            # AFTER FIX: root should NOT appear in the command (cwd handles it)
            # BEFORE FIX: root appears in "cd {root} && ..."
            if malicious_root in test_runner["command"]:
                # If root still appears, verify no execution happens
                mapper = RepoMapper.__new__(RepoMapper)
                mapper.repo_path = tmpdir
                _run_probe_and_assert_no_execution(mapper, test_runner, "/tmp/PWNED_V1")
            else:
                # Fix verified: root no longer interpolated into command
                assert "cd " not in test_runner["command"], (
                    f"Expected no 'cd' in test_runner command, got: {test_runner['command']}"
                )

    def test_vector_2_import_check(self):
        """Vector 2: import_check interpolates entry_points[0] into python3 -c.

        BEFORE FIX: command = "python3 -c 'import main$(touch /tmp/PWNED_V2)'"
        AFTER FIX: command uses sys.argv to pass the module name safely.
        """
        from repomapper import RepoMapper, ProbeGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            malicious_root = tmpdir
            malicious_entry = "main$(touch /tmp/PWNED_V2)"

            repo_map = _make_repo_map(
                root=malicious_root,
                entry_points=[f"{malicious_entry}.py"],
            )

            gen = ProbeGenerator(repo_map)
            probes = gen.generate_probes(count=5)

            import_check = next((p for p in probes if p["id"] == "import_check"), None)
            assert import_check is not None, "import_check probe not generated"

            mapper = RepoMapper.__new__(RepoMapper)
            mapper.repo_path = tmpdir

            _run_probe_and_assert_no_execution(mapper, import_check, "/tmp/PWNED_V2")

    def test_vector_3_config_valid(self):
        """Vector 3: config_valid_* interpolates root + config into open("{root}/{config}")

        BEFORE FIX: command = "python3 -c 'open("/tmp/evil$(touch /tmp/PWNED_V3)/config.toml")'"
        AFTER FIX: command uses sys.argv to pass the path safely.
        """
        from repomapper import RepoMapper, ProbeGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            malicious_root = "/tmp/evil_v3$(touch /tmp/PWNED_V3)"

            repo_map = _make_repo_map(
                root=malicious_root,
                config_files=["pyproject.toml"],
            )

            gen = ProbeGenerator(repo_map)
            probes = gen.generate_probes(count=5)

            config_probe = next((p for p in probes if p["id"].startswith("config_valid")), None)
            assert config_probe is not None, f"config_valid probe not generated. Got: {[p['id'] for p in probes]}"

            mapper = RepoMapper.__new__(RepoMapper)
            mapper.repo_path = tmpdir

            _run_probe_and_assert_no_execution(mapper, config_probe, "/tmp/PWNED_V3")

    def test_vector_4_syntax_check(self):
        """Vector 4: syntax_check interpolates root into 'cd {root} && ... $(find ...)'

        BEFORE FIX: command = "cd /tmp/evil$(touch /tmp/PWNED_V4) && python3 -m py_compile $(find ...)"
        AFTER FIX: command no longer interpolates root (uses cwd instead).
        """
        from repomapper import RepoMapper, ProbeGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            malicious_root = "/tmp/evil_v4$(touch /tmp/PWNED_V4)"

            repo_map = _make_repo_map(root=malicious_root)

            gen = ProbeGenerator(repo_map)
            probes = gen.generate_probes(count=5)

            syntax_check = next((p for p in probes if p["id"] == "syntax_check"), None)
            assert syntax_check is not None, f"syntax_check probe not generated. Got: {[p['id'] for p in probes]}"

            # AFTER FIX: root should NOT appear in the command
            if malicious_root in syntax_check["command"]:
                # If it still appears, verify no execution
                mapper = RepoMapper.__new__(RepoMapper)
                mapper.repo_path = tmpdir
                _run_probe_and_assert_no_execution(mapper, syntax_check, "/tmp/PWNED_V4")
            else:
                # Fix verified: root no longer interpolated
                assert "cd " not in syntax_check["command"], (
                    f"Expected no 'cd' in syntax_check command, got: {syntax_check['command']}"
                )

    def test_vector_5_subsystem_structure(self):
        """Vector 5: subsystem_structure interpolates root into 'ls -la {root}/{name}/'

        BEFORE FIX: command = "ls -la /tmp/evil$(touch /tmp/PWNED_V5)/tests/"
        AFTER FIX: command uses shlex.quote() on the path.
        """
        from repomapper import RepoMapper, ProbeGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            malicious_root = "/tmp/evil_v5$(touch /tmp/PWNED_V5)"

            repo_map = _make_repo_map(
                root=malicious_root,
                subsystems=[{"name": "tests", "file_count": 1, "has_tests": True, "test_files": ["tests/test_main.py"]}],
            )

            gen = ProbeGenerator(repo_map)
            probes = gen.generate_probes(count=5)

            subsystem_probe = next((p for p in probes if p["id"] == "subsystem_structure"), None)
            assert subsystem_probe is not None, f"subsystem_structure probe not generated. Got: {[p['id'] for p in probes]}"

            mapper = RepoMapper.__new__(RepoMapper)
            mapper.repo_path = tmpdir

            _run_probe_and_assert_no_execution(mapper, subsystem_probe, "/tmp/PWNED_V5")

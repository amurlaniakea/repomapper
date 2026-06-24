"""Adversarial tests for command injection vulnerability in RepoMapper probes.

These tests MUST FAIL against the unpatched code (RED) and PASS after the fix (GREEN).

Each test covers a DISTINCT interpolation point in ProbeGenerator -> run_probe pipeline:
1. _detect_test_command: root path interpolated into "cd {root} && ..."
2. import_check: entry_points[0] interpolated into python3 -c 'import {entry_mod}'
3. config_valid_*: root + config interpolated into python3 -c 'open("{root}/{config}")'
4. syntax_check: root path interpolated into "cd {root} && ... $(find ...)"
5. subsystem_structure: root path interpolated into "ls -la {root}/{name}/"
"""

import pathlib
import tempfile

from repomapper import ProbeGenerator
from repomapper.probes import run_probe


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


class TestCommandInjection_FullPipeline:
    """Test the COMPLETE pipeline: ProbeGenerator.generate_probes() -> run_probe()."""

    def test_vector_1_detect_test_command(self):
        """Vector 1: _detect_test_command interpolates root into 'cd {root} && ...'"""
        with tempfile.TemporaryDirectory() as tmpdir:
            malicious_root = "/tmp/evil_v1$(touch /tmp/PWNED_V1)"
            marker = pathlib.Path("/tmp/PWNED_V1")
            if marker.exists():
                marker.unlink()

            repo_map = _make_repo_map(root=malicious_root)
            gen = ProbeGenerator(repo_map)
            probes = gen.generate_probes(count=5)

            test_runner = next((p for p in probes if p["id"] == "test_runner"), None)
            assert test_runner is not None, "test_runner probe not generated"

            if malicious_root in test_runner["command"]:
                # If root still appears in command, verify no execution
                run_probe(tmpdir, test_runner)
                assert not marker.exists(), f"INJECTION via test_runner! {marker} exists"
            else:
                # Fix verified: root no longer interpolated
                assert "cd " not in test_runner["command"], (
                    f"Expected no 'cd' in command: {test_runner['command']}"
                )

    def test_vector_2_import_check(self):
        """Vector 2: import_check interpolates entry_points[0] into python3 -c."""
        with tempfile.TemporaryDirectory() as tmpdir:
            malicious_root = tmpdir
            malicious_entry = "main$(touch /tmp/PWNED_V2)"
            marker = pathlib.Path("/tmp/PWNED_V2")
            if marker.exists():
                marker.unlink()

            repo_map = _make_repo_map(
                root=malicious_root,
                entry_points=[f"{malicious_entry}.py"],
            )
            gen = ProbeGenerator(repo_map)
            probes = gen.generate_probes(count=5)

            import_check = next((p for p in probes if p["id"] == "import_check"), None)
            assert import_check is not None, "import_check probe not generated"

            run_probe(tmpdir, import_check)
            assert not marker.exists(), f"INJECTION via import_check! {marker} exists"

    def test_vector_3_config_valid(self):
        """Vector 3: config_valid_* interpolates root + config into open("{root}/{config}")"""
        with tempfile.TemporaryDirectory() as tmpdir:
            malicious_root = "/tmp/evil_v3$(touch /tmp/PWNED_V3)"
            marker = pathlib.Path("/tmp/PWNED_V3")
            if marker.exists():
                marker.unlink()

            repo_map = _make_repo_map(
                root=malicious_root,
                config_files=["pyproject.toml"],
            )
            gen = ProbeGenerator(repo_map)
            probes = gen.generate_probes(count=5)

            config_probe = next((p for p in probes if p["id"].startswith("config_valid")), None)
            assert config_probe is not None, (
                f"config_valid probe not generated: {[p['id'] for p in probes]}"
            )

            run_probe(tmpdir, config_probe)
            assert not marker.exists(), f"INJECTION via config_valid! {marker} exists"

    def test_vector_4_syntax_check(self):
        """Vector 4: syntax_check interpolates root into 'cd {root} && ... $(find ...)'"""
        with tempfile.TemporaryDirectory() as tmpdir:
            malicious_root = "/tmp/evil_v4$(touch /tmp/PWNED_V4)"
            marker = pathlib.Path("/tmp/PWNED_V4")
            if marker.exists():
                marker.unlink()

            repo_map = _make_repo_map(root=malicious_root)
            gen = ProbeGenerator(repo_map)
            probes = gen.generate_probes(count=5)

            syntax_check = next((p for p in probes if p["id"] == "syntax_check"), None)
            assert syntax_check is not None, (
                f"syntax_check probe not generated: {[p['id'] for p in probes]}"
            )

            if malicious_root in syntax_check["command"]:
                run_probe(tmpdir, syntax_check)
                assert not marker.exists(), f"INJECTION via syntax_check! {marker} exists"
            else:
                assert "cd " not in syntax_check["command"], (
                    f"Expected no 'cd' in command: {syntax_check['command']}"
                )

    def test_vector_5_subsystem_structure(self):
        """Vector 5: subsystem_structure interpolates root into 'ls -la {root}/{name}/'"""
        with tempfile.TemporaryDirectory() as tmpdir:
            malicious_root = "/tmp/evil_v5$(touch /tmp/PWNED_V5)"
            marker = pathlib.Path("/tmp/PWNED_V5")
            if marker.exists():
                marker.unlink()

            repo_map = _make_repo_map(
                root=malicious_root,
                subsystems=[
                    {
                        "name": "tests",
                        "file_count": 1,
                        "has_tests": True,
                        "test_files": ["tests/test_main.py"],
                    }
                ],
            )
            gen = ProbeGenerator(repo_map)
            probes = gen.generate_probes(count=5)

            subsystem_probe = next((p for p in probes if p["id"] == "subsystem_structure"), None)
            assert subsystem_probe is not None, (
                f"subsystem_structure probe not generated: {[p['id'] for p in probes]}"
            )

            run_probe(tmpdir, subsystem_probe)
            assert not marker.exists(), f"INJECTION via subsystem_structure! {marker} exists"

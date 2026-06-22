"""RepoMapper tests."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from repomapper import RepoMapper, RepoScanner, ProbeGenerator, GuidanceGenerator


@pytest.fixture
def sample_repo(tmp_path):
    """Create a sample repository for testing."""
    # Create structure
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "docs").mkdir()

    # Main file
    (tmp_path / "src" / "main.py").write_text(
        '"""Main module."""\n\ndef main():\n    """Entry point."""\n    print("Hello")\n\nif __name__ == "__main__":\n    main()\n'
    )

    # Utils
    (tmp_path / "src" / "utils.py").write_text(
        '"""Utils."""\n\ndef helper():\n    """Helper function."""\n    return True\n'
    )

    # Test file
    (tmp_path / "tests" / "test_main.py").write_text(
        '"""Tests."""\nfrom src.main import main\n\ndef test_main():\n    """Test main."""\n    assert main is not None\n'
    )

    # Config
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "test-repo"\nversion = "0.1.0"\n'
    )

    # README
    (tmp_path / "README.md").write_text("# Test Repo\n\nA test repository.\n")

    return tmp_path


class TestRepoScanner:
    def test_scan_basic(self, sample_repo):
        scanner = RepoScanner(str(sample_repo))
        repo_map = scanner.scan()
        assert repo_map.name == sample_repo.name
        assert repo_map.language == "Python"
        assert repo_map.total_files > 0

    def test_detect_entry_points(self, sample_repo):
        scanner = RepoScanner(str(sample_repo))
        repo_map = scanner.scan()
        assert any("main.py" in ep for ep in repo_map.entry_points)

    def test_detect_test_files(self, sample_repo):
        scanner = RepoScanner(str(sample_repo))
        repo_map = scanner.scan()
        assert len(repo_map.test_files) > 0

    def test_detect_config(self, sample_repo):
        scanner = RepoScanner(str(sample_repo))
        repo_map = scanner.scan()
        assert any("pyproject.toml" in c for c in repo_map.config_files)

    def test_detect_dependencies(self, sample_repo):
        scanner = RepoScanner(str(sample_repo))
        repo_map = scanner.scan()
        # pyproject.toml has no dependencies section in our test
        assert isinstance(repo_map.dependencies, list)

    def test_detect_conventions(self, sample_repo):
        scanner = RepoScanner(str(sample_repo))
        repo_map = scanner.scan()
        # Should detect at least test_framework or build_system
        assert len(repo_map.conventions) > 0

    def test_max_depth(self, sample_repo):
        scanner = RepoScanner(str(sample_repo), max_depth=1)
        repo_map = scanner.scan()
        # Should still work with limited depth
        assert repo_map.total_files > 0

    def test_max_files(self, sample_repo):
        scanner = RepoScanner(str(sample_repo), max_files=3)
        repo_map = scanner.scan()
        assert repo_map.total_files <= 3

    def test_nonexistent_repo(self):
        with pytest.raises(FileNotFoundError):
            RepoScanner("/nonexistent/path")


class TestProbeGenerator:
    def test_generate_probes(self, sample_repo):
        scanner = RepoScanner(str(sample_repo))
        repo_map = scanner.scan()
        gen = ProbeGenerator(repo_map)
        probes = gen.generate_probes(3)
        assert len(probes) == 3
        assert all("id" in p for p in probes)
        assert all("command" in p for p in probes)

    def test_test_command_detection_python(self, sample_repo):
        scanner = RepoScanner(str(sample_repo))
        repo_map = scanner.scan()
        gen = ProbeGenerator(repo_map)
        cmd = gen._detect_test_command()
        assert "pytest" in cmd or "unittest" in cmd


class TestGuidanceGenerator:
    def test_generate_guidance(self, sample_repo):
        scanner = RepoScanner(str(sample_repo))
        repo_map = scanner.scan()
        gen = GuidanceGenerator(repo_map)
        guidance = gen.generate()
        assert guidance.content != ""
        assert guidance.char_count > 0
        assert guidance.char_count <= 3000
        assert "overview" in guidance.sections

    def test_generate_with_probes(self, sample_repo):
        scanner = RepoScanner(str(sample_repo))
        repo_map = scanner.scan()
        gen = GuidanceGenerator(repo_map)
        probes = [
            {"id": "test1", "description": "Test probe", "passed": True, "findings": ["OK"]},
        ]
        guidance = gen.generate(probes)
        assert "findings" in guidance.sections

    def test_guidance_contains_key_sections(self, sample_repo):
        scanner = RepoScanner(str(sample_repo))
        repo_map = scanner.scan()
        gen = GuidanceGenerator(repo_map)
        guidance = gen.generate()
        assert "# " in guidance.content  # Has title
        assert "Language:" in guidance.content
        assert "Structure" in guidance.content


class TestRepoMapper:
    def test_full_pipeline(self, sample_repo):
        mapper = RepoMapper(str(sample_repo))
        result = mapper.map(run_probes=False)
        assert "repo_map" in result
        assert "guidance" in result
        assert result["guidance"]["char_count"] > 0

    def test_with_probes(self, sample_repo):
        mapper = RepoMapper(str(sample_repo))
        result = mapper.map(run_probes=True, probe_count=3)
        assert result["guidance"]["probes_run"] == 3

    def test_export_guidance(self, sample_repo):
        mapper = RepoMapper(str(sample_repo))
        output = str(sample_repo / "AGENTS.md")
        guidance = mapper.export_guidance(output, run_probes=False)
        assert Path(output).exists()
        content = Path(output).read_text()
        assert content == guidance

    def test_json_output(self, sample_repo):
        mapper = RepoMapper(str(sample_repo))
        result = mapper.map(run_probes=False)
        json_str = json.dumps(result, default=str)
        parsed = json.loads(json_str)
        assert "repo_map" in parsed

    def test_map_returns_timing(self, sample_repo):
        mapper = RepoMapper(str(sample_repo))
        result = mapper.map(run_probes=False)
        assert "duration_seconds" in result
        assert result["duration_seconds"] >= 0


# ==========================================
# CLI subprocess tests (real invocation path)
# ==========================================

import subprocess
import sys


class TestCLI:
    def test_cli_module_invocation(self, sample_repo):
        """python3 -m repomapper /path --no-probes should succeed."""
        result = subprocess.run(
            [sys.executable, "-m", "repomapper", str(sample_repo), "--no-probes"],
            capture_output=True, text=True
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "Language:" in result.stdout

    def test_cli_json_output(self, sample_repo):
        """python3 -m repomapper /path --no-probes --json should return valid JSON."""
        result = subprocess.run(
            [sys.executable, "-m", "repomapper", str(sample_repo), "--no-probes", "--json"],
            capture_output=True, text=True
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert "repo_map" in data
        assert "guidance" in data

    def test_cli_writes_agents_md(self, sample_repo):
        """CLI should write AGENTS.md to the repo path by default."""
        result = subprocess.run(
            [sys.executable, "-m", "repomapper", str(sample_repo), "--no-probes"],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        agents_md = sample_repo / "AGENTS.md"
        assert agents_md.exists()
        content = agents_md.read_text()
        assert len(content) > 0
        # Clean up
        agents_md.unlink()

    def test_cli_custom_output(self, sample_repo):
        """--output should write to the specified file."""
        out_file = sample_repo / "GUIDE.md"
        result = subprocess.run(
            [sys.executable, "-m", "repomapper", str(sample_repo), "--no-probes", "-o", str(out_file)],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert out_file.exists()
        out_file.unlink()

    def test_cli_nonexistent_repo(self):
        """CLI with invalid path should fail gracefully."""
        result = subprocess.run(
            [sys.executable, "-m", "repomapper", "/nonexistent/path/xyz", "--no-probes"],
            capture_output=True, text=True
        )
        assert result.returncode != 0

"""Tests for the CLI entry point of RepoMapper."""

import io
import json
import sys
from unittest.mock import patch

import pytest

from repomapper import main


@pytest.fixture
def sample_repo(tmp_path):
    """Create a minimal repository for CLI testing."""
    (tmp_path / "main.py").write_text('"""Main."""\ndef main():\n    pass\n')
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text(
        '"""Tests."""\ndef test_nothing():\n    assert True\n'
    )
    (tmp_path / "README.md").write_text("# Test Repo\n")
    return tmp_path


def run_cli(argv):
    """Run main() with given argv, capture exit code, stdout, and stderr."""
    buf_out = io.StringIO()
    buf_err = io.StringIO()
    exit_code = None

    # argv[0] must be the program name (repomapper), rest are actual args
    full_argv = ["repomapper"] + argv
    with patch.object(sys, "argv", full_argv), patch.object(sys.stdout, "write", buf_out.write), patch.object(sys.stderr, "write", buf_err.write):
            try:
                main()
            except SystemExit as e:
                exit_code = e.code
            else:
                exit_code = 0

    return exit_code, buf_out.getvalue(), buf_err.getvalue()


class TestCLIMain:
    """Test the main() CLI function with mocked sys.argv."""

    def test_basic_invocation(self, sample_repo):
        """CLI should succeed with a valid repo path."""
        code, out, err = run_cli([str(sample_repo), "--no-probes"])
        assert code == 0, f"stderr: {err}"
        assert "Repository:" in out

    def test_json_output(self, sample_repo):
        """CLI should output JSON when --json is passed."""
        code, out, err = run_cli([str(sample_repo), "--no-probes", "--json"])
        assert code == 0, f"stderr: {err}"
        data = json.loads(out)
        assert "repo_map" in data
        assert "guidance" in data

    def test_custom_output(self, sample_repo):
        """CLI should write to custom output file when -o is passed."""
        output_file = sample_repo / "GUIDE.md"
        code, out, err = run_cli([str(sample_repo), "--no-probes", "-o", str(output_file)])
        assert code == 0, f"stderr: {err}"
        assert output_file.exists()
        content = output_file.read_text()
        assert len(content) > 0

    def test_with_probes(self, sample_repo):
        """CLI should run probes when --probe-count is given."""
        code, out, err = run_cli([str(sample_repo), "--probe-count", "3"])
        assert code == 0, f"stderr: {err}"
        assert "Probes:" in out

    def test_nonexistent_repo(self):
        """CLI should raise FileNotFoundError for an invalid path."""
        with pytest.raises(FileNotFoundError):
            run_cli(["/nonexistent/path/xyz"])

    def test_writes_agents_md_by_default(self, sample_repo):
        """CLI should write AGENTS.md to the repo path by default."""
        code, out, err = run_cli([str(sample_repo), "--no-probes"])
        assert code == 0, f"stderr: {err}"
        agents_md = sample_repo / "AGENTS.md"
        assert agents_md.exists()
        content = agents_md.read_text()
        assert "Language:" in content

    def test_json_output_contains_key_fields(self, sample_repo):
        """JSON output should contain expected top-level keys."""
        code, out, err = run_cli([str(sample_repo), "--no-probes", "--json"])
        assert code == 0, f"stderr: {err}"
        data = json.loads(out)
        assert "repo_map" in data
        assert "probes" in data
        assert "guidance" in data
        assert "duration_seconds" in data
        rm = data["repo_map"]
        assert "name" in rm
        assert "language" in rm
        assert "total_files" in rm

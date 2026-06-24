"""CLI integration test for command injection vulnerability.

Uses os.makedirs with literal $(touch <witness>) in the directory name.
The witness path is absolute (from tempfile.mkdtemp) so it works regardless
of cwd. If shell=True is used anywhere in the pipeline, the witness file
is created. If shell=False is used correctly, it is NOT created.
"""

import os
import subprocess
import sys
import tempfile

import pytest


@pytest.fixture
def evil_repo():
    """Create a repo with $(touch <witness>) in the directory name.

    Uses os.makedirs to create a directory whose name literally contains
    $(touch /path/to/witness). No shell expansion happens during creation.
    """
    base_dir = tempfile.mkdtemp()

    # The witness file will be at this absolute path IF injection succeeds
    witness_file = os.path.join(base_dir, "PWNED_TEST")

    # Directory name with injection payload
    # When shell=True interpolates this, $(touch /path/PWNED_TEST) executes
    evil_dir_name = "evil_repo$(touch " + witness_file + ")"
    evil_repo_path = os.path.join(base_dir, evil_dir_name)

    os.makedirs(evil_repo_path, exist_ok=True)

    # Minimal structure so repomapper doesn't crash from missing files
    with open(os.path.join(evil_repo_path, "README.md"), "w") as f:
        f.write("# Test Repo")

    return evil_repo_path, witness_file


class TestCLIInjection:
    def test_cli_does_not_execute_injected_commands(self, evil_repo):
        """Full end-to-end PoC: CLI must not execute $(touch) from repo path."""
        evil_repo_path, witness_file = evil_repo

        # Clean any pre-existing witness
        if os.path.exists(witness_file):
            os.remove(witness_file)

        # Invoke the CLI exactly as a user would
        result = subprocess.run(
            [sys.executable, "-m", "repomapper", evil_repo_path, "--probe-count", "5"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # THE ASSERT: witness must NOT exist
        assert not os.path.exists(witness_file), (
            f"VULNERABILITY DETECTED: Injected command executed!\n"
            f"Witness file exists: {witness_file}\n"
            f"CLI stdout: {result.stdout[:300]}\n"
            f"CLI stderr: {result.stderr[:300]}"
        )

"""Tests for heuristic branches in RepoScanner._detect_conventions."""



from repomapper import RepoScanner


class TestDetectConventionsEdgeCases:
    """Force execution of heuristic branches in _detect_conventions."""

    def test_detects_pytest_by_import(self, tmp_path):
        """Detect pytest when test files import pytest."""
        (tmp_path / "main.py").write_text("x = 1\n")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_x.py").write_text(
            "import pytest\n\ndef test_foo():\n    pass\n"
        )
        scanner = RepoScanner(str(tmp_path))
        conventions = scanner._detect_conventions()
        assert conventions.get("test_framework") == "pytest"

    def test_detects_unittest_by_import(self, tmp_path):
        """Detect unittest when test files import unittest."""
        (tmp_path / "main.py").write_text("x = 1\n")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_x.py").write_text(
            "import unittest\n\nclass TestFoo(unittest.TestCase):\n    def test_bar(self):\n        pass\n"
        )
        scanner = RepoScanner(str(tmp_path))
        conventions = scanner._detect_conventions()
        assert conventions.get("test_framework") == "unittest"

    def test_detects_pytest_by_pyproject_dependency(self, tmp_path):
        """Detect pytest when declared in pyproject.toml dependencies."""
        (tmp_path / "main.py").write_text("x = 1\n")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_x.py").write_text("def test_foo():\n    pass\n")
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test"\ndependencies = ["pytest>=7.0"]\n'
        )
        scanner = RepoScanner(str(tmp_path))
        conventions = scanner._detect_conventions()
        assert conventions.get("test_framework") == "pytest"

    def test_detects_jest_from_package_json(self, tmp_path):
        """Detect jest from package.json devDependencies."""
        (tmp_path / "main.py").write_text("x = 1\n")
        (tmp_path / "package.json").write_text(
            '{"devDependencies": {"jest": "^29.0"}}'
        )
        scanner = RepoScanner(str(tmp_path))
        conventions = scanner._detect_conventions()
        assert conventions.get("test_framework") == "jest"

    def test_detects_vitest_from_package_json(self, tmp_path):
        """Detect vitest from package.json devDependencies."""
        (tmp_path / "main.py").write_text("x = 1\n")
        (tmp_path / "package.json").write_text(
            '{"devDependencies": {"vitest": "^1.0"}}'
        )
        scanner = RepoScanner(str(tmp_path))
        conventions = scanner._detect_conventions()
        assert conventions.get("test_framework") == "vitest"

    def test_detects_build_system_makefile(self, tmp_path):
        """Detect make build system from Makefile presence."""
        (tmp_path / "main.py").write_text("x = 1\n")
        (tmp_path / "Makefile").write_text("all:\n\techo hello\n")
        scanner = RepoScanner(str(tmp_path))
        conventions = scanner._detect_conventions()
        assert conventions.get("build_system") == "make"

    def test_detects_build_system_npm(self, tmp_path):
        """Detect npm/yarn from package.json presence."""
        (tmp_path / "main.py").write_text("x = 1\n")
        (tmp_path / "package.json").write_text('{"name": "test"}\n')
        scanner = RepoScanner(str(tmp_path))
        conventions = scanner._detect_conventions()
        assert conventions.get("build_system") == "npm/yarn"

    def test_detects_build_system_cargo(self, tmp_path):
        """Detect cargo from Cargo.toml presence."""
        (tmp_path / "main.py").write_text("x = 1\n")
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"\n')
        scanner = RepoScanner(str(tmp_path))
        conventions = scanner._detect_conventions()
        assert conventions.get("build_system") == "cargo"

    def test_detects_build_system_go_modules(self, tmp_path):
        """Detect go modules from go.mod presence."""
        (tmp_path / "main.py").write_text("x = 1\n")
        (tmp_path / "go.mod").write_text("module test\n\ngo 1.21\n")
        scanner = RepoScanner(str(tmp_path))
        conventions = scanner._detect_conventions()
        assert conventions.get("build_system") == "go modules"

    def test_python_conventions_type_hints(self, tmp_path):
        """Detect Python type hints in source files."""
        (tmp_path / "main.py").write_text(
            "def greet(name: str) -> str:\n    return f'Hello {name}'\n"
        )
        scanner = RepoScanner(str(tmp_path))
        conventions = scanner._detect_conventions()
        assert "python" in conventions
        assert conventions["python"]["type_hints"] is True

    def test_python_conventions_docstrings(self, tmp_path):
        """Detect Python docstrings in source files."""
        (tmp_path / "main.py").write_text(
            '"""Main module."""\n\ndef main():\n    """Entry point."""\n    pass\n'
        )
        scanner = RepoScanner(str(tmp_path))
        conventions = scanner._detect_conventions()
        assert conventions["python"]["docstrings"] is True

    def test_python_conventions_fstrings(self, tmp_path):
        """Detect Python f-strings in source files."""
        (tmp_path / "main.py").write_text(
            'name = "world"\nprint(f"Hello {name}")\n'
        )
        scanner = RepoScanner(str(tmp_path))
        conventions = scanner._detect_conventions()
        assert conventions["python"]["f_strings"] is True

    def test_python_conventions_indent_tabs(self, tmp_path):
        """Detect tab indentation in Python files."""
        (tmp_path / "main.py").write_text(
            "def main():\n\tpass\n"
        )
        scanner = RepoScanner(str(tmp_path))
        conventions = scanner._detect_conventions()
        assert conventions["python"]["indent"] == "tabs"

    def test_python_conventions_indent_4spaces(self, tmp_path):
        """Detect 4-space indentation in Python files."""
        (tmp_path / "main.py").write_text(
            "def main():\n    pass\n"
        )
        scanner = RepoScanner(str(tmp_path))
        conventions = scanner._detect_conventions()
        assert conventions["python"]["indent"] == "4 spaces"

    def test_detects_poetry_lock(self, tmp_path):
        """Detect poetry.lock as dependency signal."""
        (tmp_path / "main.py").write_text("x = 1\n")
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
        (tmp_path / "poetry.lock").write_text("# Poetry lock file\n")
        scanner = RepoScanner(str(tmp_path))
        deps = scanner._extract_dependencies()
        assert "__tool__poetry" in deps

    def test_detects_uv_lock(self, tmp_path):
        """Detect uv.lock as dependency signal."""
        (tmp_path / "main.py").write_text("x = 1\n")
        (tmp_path / "uv.lock").write_text("# UV lock file\n")
        scanner = RepoScanner(str(tmp_path))
        deps = scanner._extract_dependencies()
        assert "__tool__uv" in deps

    def test_detects_pipenv(self, tmp_path):
        """Detect Pipfile as dependency signal."""
        (tmp_path / "main.py").write_text("x = 1\n")
        (tmp_path / "Pipfile").write_text("[[source]]\nurl = \"https://pypi.org/simple\"\n")
        scanner = RepoScanner(str(tmp_path))
        deps = scanner._extract_dependencies()
        assert "__tool__pipenv" in deps

    def test_no_python_files_returns_no_python_conventions(self, tmp_path):
        """No Python files means no python conventions detected."""
        (tmp_path / "README.md").write_text("Hello\n")
        scanner = RepoScanner(str(tmp_path))
        conventions = scanner._detect_conventions()
        assert "python" not in conventions

    def test_default_pytest_when_no_imports_or_deps(self, tmp_path):
        """Default to pytest when test_*.py files exist but no imports found."""
        (tmp_path / "main.py").write_text("x = 1\n")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_x.py").write_text("def test_foo():\n    pass\n")
        scanner = RepoScanner(str(tmp_path))
        conventions = scanner._detect_conventions()
        assert conventions.get("test_framework") == "pytest"

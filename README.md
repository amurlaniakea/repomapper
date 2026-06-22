# RepoMapper

**Repository Understanding for Coding Agents**

Generates a compact `AGENTS.md`-style operational guide for any code repository.
Based on the paper ["Probe-and-Refine Tuning of Repository Guidance for Coding Agents"](https://arxiv.org/abs/2606.20512) (arXiv:2606.20512, Jun 2026).

## The Problem

LLM-based coding agents need operational knowledge about a repository that doesn't exist in the code itself:
- Which files house which subsystems
- How to run the test suite
- Which workflows have historically led to wrong fixes
- Coding conventions and project structure

Engineers maintain `AGENTS.md` files to supply this context, but creating them manually is tedious and error-prone.

## The Solution

RepoMapper automates this by:
1. **Scanning** the repository structure, detecting language, entry points, tests, subsystems, dependencies, and conventions
2. **Probing** with synthetic tasks (import check, syntax check, test runner, config validation)
3. **Generating** a compact operational guide (< 3000 chars) in `AGENTS.md` format

## Quick Start

```bash
# Clone
git clone https://github.com/amurlaniakea/repomapper.git
cd repomapper

# Setup
python3 -m venv venv
source venv/bin/activate
pip install -e .

# Generate AGENTS.md for a repository
python3 -m repomapper /path/to/repo

# With probes (validates imports, syntax, tests)
python3 -m repomapper /path/to/repo --probe-count 5

# JSON output
python3 -m repomapper /path/to/repo --json

# Custom output file
python3 -m repomapper /path/to/repo --output GUIDE.md
```

## Example Output

```markdown
# my-project

**Language:** Python
**Files:** 142
**Lines:** 8,523

## Structure

- `src/`
- `tests/`
- `docs/`

## Entry Points

- `src/main.py`
- `src/cli.py`

## Subsystems

- **src/** — 8 files (has tests)
- **tests/** — 5 files (has tests)

## Testing

**Test command:** `cd /path/to/repo && python3 -m pytest --co -q 2>&1 | head -20`

**Test files:**
- `tests/test_main.py`
- `tests/test_utils.py`

## Conventions

- **python:** type_hints: True, docstrings: True, f_strings: True, indent: 4 spaces
- **test_framework:** pytest
- **build_system:** setuptools/poetry

## Probe Findings

- [PASS] Run the test suite
- [PASS] Import the main module
- [PASS] Check Python syntax
```

## Supported Languages

- Python, JavaScript, TypeScript, Go, Rust, Java, Ruby, C/C++, C#, PHP, Swift, Kotlin

## Project Structure

```
repomapper/
├── repomapper/
│   ├── __init__.py      # Main module (RepoMapper, Scanner, Probes, Guidance)
│   └── core/
│       └── __init__.py
├── tests/
│   └── test_repomapper.py
├── docs/
│   └── PAPER.md
├── examples/
│   └── example_usage.py
├── README.md
├── LICENSE
└── .gitignore
```

## CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `repo_path` | (required) | Path to the repository |
| `--output, -o` | `AGENTS.md` | Output file path |
| `--no-probes` | False | Skip running probes |
| `--probe-count` | 5 | Number of probes to run |
| `--max-depth` | 3 | Max directory depth to scan |
| `--max-files` | 500 | Max files to scan |
| `--json` | False | Output full JSON result |

## Differences from the Paper

| Feature | Paper | RepoMapper |
|---------|-------|------------|
| Method | Probe-and-refine tuning with LLM calls | Static analysis + synthetic probes |
| Output | Refined AGENTS.md via LLM | Generated AGENTS.md via templates |
| Model required | Yes (LLM for tuning) | No |
| SWE-bench eval | Yes | No (future work) |
| Scope | Python repos | Multi-language |

## License

AGPL-3.0 — Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>

## References

- Asa Shepard, Jeannie Albrecht. "Probe-and-Refine Tuning of Repository Guidance for Coding Agents." arXiv:2606.20512, Jun 2026.
- Code: https://github.com/asashepard/probe-and-refine-tuning

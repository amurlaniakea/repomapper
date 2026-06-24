"""Data models for RepoMapper."""

from dataclasses import dataclass
from typing import Any


@dataclass
class RepoMap:
    """Structured representation of a repository."""

    root: str
    name: str
    language: str
    total_files: int
    total_lines: int
    directories: list[str]
    entry_points: list[str]
    test_files: list[str]
    config_files: list[str]
    doc_files: list[str]
    subsystems: list[dict[str, Any]]
    dependencies: list[str]
    conventions: dict[str, Any]


@dataclass
class ProbeResult:
    """Result of a synthetic probe task."""

    probe_id: str
    description: str
    command: str
    expected: str
    passed: bool
    output: str
    findings: list[str]


@dataclass
class Guidance:
    """Operational guidance for a repository."""

    content: str
    version: int
    probes_run: int
    probes_passed: int
    char_count: int
    sections: dict[str, str]

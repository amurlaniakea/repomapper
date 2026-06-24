"""
RepoMapper: Repository Understanding for Coding Agents.

Based on: "Probe-and-Refine Tuning of Repository Guidance for Coding Agents"
          (arXiv:2606.20512, Jun 2026)

Copyright (C) 2026 Pedro Sordo Martínez <amurlaniakea@gmail.com>
License: AGPL-3.0
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from .guidance import GuidanceGenerator
from .models import Guidance, ProbeResult, RepoMap  # noqa: F401 — public API
from .probes import ProbeGenerator, run_probe
from .scanner import RepoScanner

__all__ = [
    "RepoMap",
    "ProbeResult",
    "Guidance",
    "RepoScanner",
    "ProbeGenerator",
    "GuidanceGenerator",
    "RepoMapper",
]


# ==========================================
# Main RepoMapper Class
# ==========================================


class RepoMapper:
    """
    Main class that orchestrates repository understanding.
    Scans, probes, and generates operational guidance.
    """

    def __init__(self, repo_path: str, max_depth: int = 3, max_files: int = 500):
        self.repo_path = repo_path
        self.scanner = RepoScanner(repo_path, max_depth=max_depth, max_files=max_files)

    def map(self, run_probes: bool = True, probe_count: int = 5) -> dict[str, Any]:
        """Full pipeline: scan -> probe -> generate guidance."""
        start_time = time.time()

        repo_map = self.scanner.scan()

        probes: list[dict[str, Any]] = []
        if run_probes:
            probe_gen = ProbeGenerator(repo_map)
            probe_defs = probe_gen.generate_probes(probe_count)
            for probe_def in probe_defs:
                result = run_probe(self.repo_path, probe_def)
                probes.append(result)

        guidance_gen = GuidanceGenerator(repo_map)
        guidance = guidance_gen.generate(probes)

        duration = time.time() - start_time

        return {
            "repo_map": {
                "name": repo_map.name,
                "language": repo_map.language,
                "total_files": repo_map.total_files,
                "total_lines": repo_map.total_lines,
                "entry_points": repo_map.entry_points,
                "test_files": repo_map.test_files,
                "config_files": repo_map.config_files,
                "subsystems": repo_map.subsystems,
                "dependencies": repo_map.dependencies,
                "conventions": repo_map.conventions,
            },
            "probes": probes,
            "guidance": {
                "content": guidance.content,
                "char_count": guidance.char_count,
                "probes_run": guidance.probes_run,
                "probes_passed": guidance.probes_passed,
                "sections": list(guidance.sections.keys()),
            },
            "duration_seconds": round(duration, 2),
        }

    def export_guidance(self, output_path: str, run_probes: bool = True) -> str:
        """Generate and export guidance to a file."""
        result = self.map(run_probes=run_probes)
        guidance: str = result["guidance"]["content"]
        with open(output_path, "w") as f:
            f.write(guidance)
        return guidance


# ==========================================
# CLI
# ==========================================


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="RepoMapper: Repository Understanding for Coding Agents",
        epilog="Based on arXiv:2606.20512 (Jun 2026)",
    )
    parser.add_argument("repo_path", help="Path to the repository")
    parser.add_argument("--output", "-o", help="Output file for guidance (default: AGENTS.md)")
    parser.add_argument("--no-probes", action="store_true", help="Skip running probes")
    parser.add_argument("--probe-count", type=int, default=5, help="Number of probes to run")
    parser.add_argument("--max-depth", type=int, default=3, help="Max directory depth to scan")
    parser.add_argument("--max-files", type=int, default=500, help="Max files to scan")
    parser.add_argument("--json", action="store_true", help="Output full JSON result")
    args = parser.parse_args()

    mapper = RepoMapper(args.repo_path, max_depth=args.max_depth, max_files=args.max_files)
    result = mapper.map(run_probes=not args.no_probes, probe_count=args.probe_count)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        rm = result["repo_map"]
        print(f"Repository: {rm['name']}")
        print(f"Language: {rm['language']}")
        print(f"Files: {rm['total_files']}")
        print(f"Lines: {rm['total_lines']:,}")
        print(f"Entry points: {len(rm['entry_points'])}")
        print(f"Test files: {len(rm['test_files'])}")
        print(f"Subsystems: {len(rm['subsystems'])}")
        probes_passed = result['guidance']['probes_passed']
        probes_run = result['guidance']['probes_run']
        print(f"Probes: {probes_passed}/{probes_run} passed")
        print(f"Guidance: {result['guidance']['char_count']} chars")
        print(f"Duration: {result['duration_seconds']}s")

    output = args.output or os.path.join(args.repo_path, "AGENTS.md")
    with open(output, "w") as f:
        f.write(result["guidance"]["content"])
    if not args.json:
        print(f"\nGuidance written to: {output}")


if __name__ == "__main__":
    main()

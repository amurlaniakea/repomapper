"""Guidance generation for RepoMapper."""

from __future__ import annotations

from typing import Any

from .models import Guidance, RepoMap


class GuidanceGenerator:
    """Generates operational guidance from repo map and probe results."""

    def __init__(self, repo_map: RepoMap):
        self.repo_map = repo_map

    def generate(self, probes: list[dict[str, Any]] | None = None) -> Guidance:
        """Generate compact operational guidance."""
        sections: dict[str, str] = {}
        sections["overview"] = self._gen_overview()
        sections["structure"] = self._gen_structure()
        if self.repo_map.entry_points:
            sections["entry_points"] = self._gen_entry_points()
        sections["testing"] = self._gen_testing()
        if self.repo_map.dependencies:
            sections["dependencies"] = self._gen_dependencies()
        if self.repo_map.conventions:
            sections["conventions"] = self._gen_conventions()
        if self.repo_map.subsystems:
            sections["subsystems"] = self._gen_subsystems()
        if probes:
            sections["findings"] = self._gen_findings(probes)

        content = self._combine_sections(sections)

        return Guidance(
            content=content,
            version=1,
            probes_run=len(probes) if probes else 0,
            probes_passed=sum(1 for p in probes if p.get("passed", False)) if probes else 0,
            char_count=len(content),
            sections=sections,
        )

    def _gen_overview(self) -> str:
        return (
            f"# {self.repo_map.name}\n\n"
            f"**Language:** {self.repo_map.language}  \n"
            f"**Files:** {self.repo_map.total_files}  \n"
            f"**Lines:** {self.repo_map.total_lines:,}  \n\n"
        )

    def _gen_structure(self) -> str:
        lines = ["## Structure", ""]
        top_dirs = set()
        for d in self.repo_map.directories:
            parts = d.split("/")
            if len(parts) == 1:
                top_dirs.add(parts[0])
        for d in sorted(top_dirs)[:15]:
            lines.append(f"- `{d}/`")
        lines.append("")
        return "\n".join(lines)

    def _gen_entry_points(self) -> str:
        lines = ["## Entry Points", ""]
        for ep in self.repo_map.entry_points[:10]:
            lines.append(f"- `{ep}`")
        lines.append("")
        return "\n".join(lines)

    def _gen_testing(self) -> str:
        lines = ["## Testing", ""]
        from .probes import ProbeGenerator

        gen = ProbeGenerator(self.repo_map)
        test_cmd = gen._detect_test_command()
        cmd = test_cmd.split("&&")[-1].strip() if "&&" in test_cmd else test_cmd
        lines.append(f"**Test command:** `{cmd}`")
        lines.append("")
        if self.repo_map.test_files:
            lines.append("**Test files:**")
            for tf in self.repo_map.test_files[:10]:
                lines.append(f"- `{tf}`")
            lines.append("")
        return "\n".join(lines)

    def _gen_dependencies(self) -> str:
        lines = ["## Dependencies", ""]
        for dep in self.repo_map.dependencies[:20]:
            lines.append(f"- {dep}")
        if len(self.repo_map.dependencies) > 20:
            lines.append(f"- ... and {len(self.repo_map.dependencies) - 20} more")
        lines.append("")
        return "\n".join(lines)

    def _gen_conventions(self) -> str:
        lines = ["## Conventions", ""]
        for lang, conv in self.repo_map.conventions.items():
            if isinstance(conv, dict):
                items = ", ".join(f"{k}: {v}" for k, v in conv.items())
                lines.append(f"- **{lang}:** {items}")
            else:
                lines.append(f"- **{lang}:** {conv}")
        lines.append("")
        return "\n".join(lines)

    def _gen_subsystems(self) -> str:
        lines = ["## Subsystems", ""]
        for sub in self.repo_map.subsystems[:10]:
            test_info = " (has tests)" if sub["has_tests"] else " (no tests)"
            lines.append(f"- **{sub['name']}/** — {sub['file_count']} files{test_info}")
        lines.append("")
        return "\n".join(lines)

    def _gen_findings(self, probes: list[dict[str, Any]]) -> str:
        lines = ["## Probe Findings", ""]
        for probe in probes:
            status = "PASS" if probe.get("passed", False) else "FAIL"
            lines.append(f"- [{status}] {probe['description']}")
            if probe.get("findings"):
                for finding in probe["findings"]:
                    lines.append(f"  - {finding}")
        lines.append("")
        return "\n".join(lines)

    def _combine_sections(self, sections: dict[str, str]) -> str:
        order = [
            "overview",
            "structure",
            "entry_points",
            "subsystems",
            "testing",
            "dependencies",
            "conventions",
            "findings",
        ]
        parts = []
        total_chars = 0
        for key in order:
            if key in sections:
                section = sections[key]
                if total_chars + len(section) > 2900:
                    remaining = 2900 - total_chars
                    if remaining > 100:
                        parts.append(section[:remaining] + "\n\n...")
                    break
                parts.append(section)
                total_chars += len(section)
        return "\n".join(parts)

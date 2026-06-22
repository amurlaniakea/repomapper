#!/usr/bin/env python3
"""Example: using RepoMapper as a library."""

from repomapper import RepoMapper
import json

# Basic usage — scan a repo and generate guidance
mapper = RepoMapper("/path/to/your/repo")
result = mapper.map(run_probes=True, probe_count=5)

# Access structured data
rm = result["repo_map"]
print(f"Language: {rm['language']}")
print(f"Files: {rm['total_files']}")
print(f"Entry points: {rm['entry_points']}")
print(f"Test files: {rm['test_files']}")
print(f"Subsystems: {rm['subsystems']}")

# Access guidance
guidance = result["guidance"]
print(f"\nGuidance ({guidance['char_count']} chars):")
print(guidance["content"])

# Export to JSON
with open("repomap.json", "w") as f:
    json.dump(result, f, indent=2, default=str)

# Write AGENTS.md
with open("AGENTS.md", "w") as f:
    f.write(guidance["content"])

print("\nDone. AGENTS.md and repomap.json written.")

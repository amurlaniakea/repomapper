# Probe-and-Refine Tuning of Repository Guidance for Coding Agents

**Asa Shepard, Jeannie Albrecht**
arXiv:2606.20512, June 2026

## Summary

This paper introduces a method for automatically generating and refining
`AGENTS.md`-style operational guides for code repositories. The approach
combines static repository analysis with synthetic "probes" — small
validation tasks that verify imports, syntax, test execution, and
configuration integrity.

## Key Contributions

1. **Probe-and-Refine Loop**: An LLM-based tuning loop that generates
   candidate guidance, probes the repository to validate it, and refines
   based on probe results.

2. **Synthetic Probes**: Automated checks (import verification, syntax
   validation, test runner detection, config linting) that ground the
   guidance in observable repository behavior.

3. **AGENTS.md Format**: A compact operational guide format (< 3000 chars)
   covering structure, subsystems, entry points, testing commands, and
   coding conventions.

4. **Evaluation**: Demonstrated improvement on SWE-bench tasks when agents
   use the generated guidance vs. baseline.

## How RepoMapper Relates

RepoMapper implements the core scanning and probe generation ideas from
the paper, using static analysis instead of LLM-based tuning:

| Aspect | Paper | RepoMapper |
|--------|-------|------------|
| Method | Probe-and-refine with LLM | Static analysis + synthetic probes |
| Model required | Yes | No |
| SWE-bench eval | Yes | No (future work) |
| Scope | Python repos | Multi-language |

## Reference

```bibtex
@article{shepard2026probe,
  title={Probe-and-Refine Tuning of Repository Guidance for Coding Agents},
  author={Shepard, Asa and Albrecht, Jeannie},
  journal={arXiv preprint arXiv:2606.20512},
  year={2026}
}
```

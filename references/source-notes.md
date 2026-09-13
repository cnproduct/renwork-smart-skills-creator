# Verified source notes

Verified on 2026-09-13. These sources informed architecture and evaluation choices; no third-party implementation code is vendored.

- [agentskills/agentskills](https://github.com/agentskills/agentskills) — open Skill format, required frontmatter, optional scripts/references/assets, and three-stage progressive disclosure.
- [anthropics/skills](https://github.com/anthropics/skills) — production examples showing compact entrypoints and task-specific resources.
- [adewale/skill-eval-harness](https://github.com/adewale/skill-eval-harness) — paired with/without evaluation, deterministic local grading, split discipline, leakage lint, traces, and materialized ablations.
- [gcamilo/skill-eval](https://github.com/gcamilo/skill-eval) — three-tier rubrics, programmatic checker constraints, calibrated judges, and position-swapped pairwise evaluation.
- [opendatahub-io/agent-eval-harness](https://github.com/opendatahub-io/agent-eval-harness) — Codex/Claude/CLI runner abstraction, natural-language dataset generation, agent judges, and iterative refinement.
- [FrancyJGLisboa/agent-skills-platform](https://github.com/FrancyJGLisboa/agent-skills-platform) — current successor to the earlier `agent-skill-creator`, emphasizing evidence, lifecycle governance, quarantine, rollback, and distribution.
- [warpdotdev/common-skills](https://github.com/warpdotdev/common-skills) — `skill-doctor` pattern for scoring recent local conversations and drafting evidence-linked edits without uploading transcripts.
- [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills), [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills), and [karanb192/awesome-claude-skills](https://github.com/karanb192/awesome-claude-skills) — discovery catalogs, not runtime dependencies or proof that every listed skill is production-grade.

Repository popularity is not used as a quality gate. A source idea is adopted only when it improves a concrete invariant in this implementation.

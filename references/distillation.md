# Conversation-to-SOP distillation

Use this mode when the user wants a completed workflow turned into a reusable Skill.

## Evidence inventory

For each source, retain a local-only record with:

- source kind, stable content hash, timestamp, and workspace;
- user intent and explicit constraints;
- actions actually taken, including tools and important parameters;
- observable verification and unresolved gates;
- failures, root causes, successful recoveries, and discarded approaches;
- user corrections and stable preferences;
- output artifacts without credentials or private identifiers.

Do not treat assistant narration as proof. A command was successful only when its output, a file diff, a target-surface check, or another independent observation supports it.

## SOP contract

Model the reusable workflow with these fields before writing instructions:

1. `trigger`: what request or situation should activate the Skill;
2. `scope`: included and excluded systems, actors, data, and side effects;
3. `inputs`: required facts, files, accounts, and authorization;
4. `preflight`: cheap checks that prevent expensive or irreversible failures;
5. `decisions`: branches and the evidence used to choose them;
6. `actions`: ordered work, placing repeatable mechanics in scripts;
7. `verification`: objective assertions and target-surface acceptance;
8. `stop_conditions`: missing authority, unsafe ambiguity, and retry limits;
9. `recovery`: rollback, cursor restore, idempotency, and quarantine;
10. `outputs`: artifacts, status, evidence boundaries, and next step.

## Skill packaging

- Keep `name` and `description` precise enough for reliable discovery.
- Keep the shared workflow in `SKILL.md` and conditional detail in one-level references.
- Write deterministic parsers, validators, and API operations as scripts.
- Add anonymized regression cases that exercise the new non-obvious rule.
- Store temporary examples, evidence packets, and reports under `.local/`, not inside the published Skill.
- Preserve platform-specific differences in adapters; do not pretend Codex and Antigravity have the same trace format.

Before promotion, map every instruction to either explicit user intent, observed evidence, a verified source contract, or a documented derived rule.

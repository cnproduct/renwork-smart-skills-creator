# Evaluation and release gates

Use deterministic checks first; spend model calls only after the package is safe and structurally valid.

## Fast local gates

`scripts/renwork-skills validate` checks:

- Agent Skills frontmatter and directory naming;
- progressive-disclosure limits and referenced-file reachability;
- unfinished scaffold text and empty resources;
- secret-like content in publishable files;
- required lifecycle, verification, failure, and recovery concepts.

`scripts/renwork-skills eval` scores an old/new pair with a deterministic structural rubric. This is a cheap regression gate, not proof of causal behavioral lift.

## Release-grade behavioral evaluation

For consequential Skill changes, run the same task, model, repetition, fixtures, and population against:

- `without_skill` versus `with_skill` to measure causal lift;
- `old_skill` versus `new_skill` to detect regressions;
- materialized ablations to test which instruction or script is load-bearing.

Use tune, holdout, and holdback splits. Do not expose expected outputs or judge rubrics to the generation arm. Prefer deterministic oracles for files, JSON, commands, and exact invariants. Use an LLM judge only for semantic qualities, calibrate it against human labels, and swap order in pairwise judging.

The repository can export an `adewale/skill-eval-harness` v1 manifest with `scripts/renwork-skills eval --export-manifest .local/shared-benchmark.json`. Use `gcamilo/skill-eval` when tiered rubrics and position-swap comparison are preferred, or `opendatahub-io/agent-eval-harness` for runner-based end-to-end evaluation; those two integrations are documented patterns rather than bundled runtime dependencies.

## Promotion rule

A candidate may be pushed to an evolution branch only when all critical gates pass, no secret finding exists, the deterministic score does not regress, and the change includes evidence provenance. A candidate that broadens permissions or external side effects remains review-only even when every automated gate passes.

# Operations

## Local configuration

Copy `config.example.json` to `.local/config.json` or run:

```bash
scripts/renwork-skills install --workspace-root "/absolute/workspace/path"
```

`workspace_roots` filters Codex sessions by their recorded working directory. Antigravity task artifacts currently do not expose a reliable workspace field, so their collection is artifact-based and should be narrowed by explicit export roots when necessary.

## Source fidelity

- Codex: parse only user/assistant message records from JSONL; skip encrypted reasoning, system instructions, tool outputs, and rate-limit metadata.
- Antigravity: read durable Markdown task artifacts. Inventory `.pb` files but do not decode them without a published schema.
- Exports: accept explicit Markdown, text, JSON, or JSONL files selected by the operator.

Every collected record is redacted and hashed before it reaches the evidence store. Collection state and excerpts remain under `.local/`.

## Automation

The macOS installer creates `~/Library/LaunchAgents/com.cnproduct.renwork-smart-skills-creator.plist`. It runs `cycle --apply --sync` at the configured interval and initializes the cursor to installation time, so earlier conversations are not silently mined.

Useful commands:

```bash
scripts/renwork-skills doctor --config .local/config.json
scripts/renwork-skills cycle --config .local/config.json
scripts/renwork-skills cycle --config .local/config.json --apply --sync
scripts/renwork-skills uninstall-automation
```

The default sync target is exactly `cnproduct/renwork-smart-skills-creator`. A mismatched remote or authenticated GitHub owner fails closed.

## Status meanings

- `no_change`: no new evidence passed the threshold.
- `proposed`: a local proposal packet exists; no skill or Git state changed.
- `synced`: a validated branch and pull request were created.
- `quarantined`: generation or a gate failed; accepted skills are unchanged.
- `blocked`: required CLI, authentication, clean repository state, or allowlisted target is unavailable.

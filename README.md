# RenWork Smart Skills Creator

`renwork-smart-skills-creator` turns local Codex, Antigravity, and exported agent conversations into evidence-backed SOPs and portable Agent Skills. It then watches later conversations for demonstrated improvements, validates candidate edits in an isolated worktree, and syncs passing changes to GitHub as reviewable pull requests.

The design follows the open [Agent Skills specification](https://github.com/agentskills/agentskills), while combining progressive disclosure, deterministic scripts, evidence provenance, regression cases, causal-lift evaluation hooks, quarantine, rollback, and guarded GitHub distribution.

## What is automated

```text
local conversations
        |
        v
collect + redact + hash  (raw data stays in .local/)
        |
        v
evidence mining  ---> no strong signal ---> no change
        |
        v
isolated evolution branch
        |
        v
spec + secret + regression gates
        |
        +-- fail --> quarantine locally
        |
        `-- pass --> push branch + open GitHub PR
```

Automatic sync deliberately stops at a pull request. Main-branch merge remains governed because a conversation is evidence, never authorization.

## Quick start

Requirements: Python 3.11+, Git, and optionally `codex` and `gh` for automatic editing and GitHub sync.

```bash
git clone https://github.com/cnproduct/renwork-smart-skills-creator.git
cd renwork-smart-skills-creator
python3 -m unittest discover -s tests -v
scripts/renwork-skills validate
scripts/renwork-skills install --workspace-root "/path/to/workspace" --interval-hours 6
```

The installer writes private runtime state to ignored `.local/`, links this skill into Codex and the selected workspace, records a cursor so only future conversations are watched, and installs a macOS LaunchAgent for the guarded cycle.

Nothing from an existing transcript is uploaded automatically. To distill selected history intentionally:

```bash
scripts/renwork-skills collect --config .local/config.json --since-hours 168
scripts/renwork-skills mine --config .local/config.json
scripts/renwork-skills cycle --config .local/config.json --apply --sync
```

## Supported sources

- Codex JSONL sessions under `~/.codex/sessions/`.
- Antigravity task artifacts (`task.md`, `implementation_plan.md`, and `walkthrough.md`) under `~/.gemini/antigravity/brain/`.
- Explicit `.md`, `.txt`, `.json`, and `.jsonl` exports.

Antigravity `.pb` conversation stores are inventoried but not decoded because their schema is not public and the local files may be opaque. Use Antigravity's durable task artifacts or provide an explicit export; the system never claims a lossy binary scrape is complete.

## Commands

```bash
scripts/renwork-skills doctor
scripts/renwork-skills collect --since-hours 24
scripts/renwork-skills mine
scripts/renwork-skills validate
scripts/renwork-skills eval
scripts/renwork-skills cycle --apply --sync
scripts/renwork-skills install --workspace-root "/path/to/workspace"
scripts/renwork-skills machine-id
scripts/renwork-skills issue-license --key admin_private_key.pem --mid "<MID>" --name "Customer"
scripts/renwork-skills protect --skill path/to/skill --output dist
```

## Commercial Protection & Anti-Piracy (Zero-Trust Guard)

All skills authored or packaged by RenWork can be automatically protected against prompt and code theft:
- **Hardware Binding**: Locks execution to a physical machine ID (`MID-XXXX-XXXX-XXXX-XXXX`).
- **Binary Obfuscation**: Compiles Python source code to native `.pyd` C-extensions using PyArmor and strips all plaintext sources.
- **Store Mutex Locking**: Enforces single-window 1:1 tenant isolation and maximum 1-switch quota (`switch_count <= 1`) to eliminate carousel piracy.
- **Serverless Cloud Gateway**: Cloudflare Workers + KV for real-time remote banning and usage analytics, with resilient offline grace fallback.

See [references/protection.md](references/protection.md) for full operational instructions.

## Privacy and governance

- `.local/`, raw transcripts, evidence packets, prompts, logs, and worktrees are ignored.
- Redaction runs before evidence is written.
- Secret scanning fails closed before a branch can be pushed.
- External writes require the configured repository allowlist and an authenticated `gh` CLI.
- Automatic changes never merge themselves.
- Failed candidates are quarantined and do not alter the accepted skill.

## License and sources

MIT licensed. This repository implements its own code. See [references/source-notes.md](references/source-notes.md) for verified projects whose design ideas informed it.

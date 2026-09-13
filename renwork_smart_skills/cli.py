"""Command-line interface for the RenWork Skill lifecycle."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .collectors import atomic_write_json, collect_antigravity, collect_codex, collect_exports
from .evaluation import compare, export_paired_manifest
from .evolution import evolve, lock
from .mining import mine
from .validation import validate_repo, write_report


REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO / ".local" / "config.json"


def load_config(path: Path | None) -> tuple[dict, Path]:
    selected = (path or DEFAULT_CONFIG).expanduser().resolve()
    if not selected.exists():
        raise SystemExit(f"config not found: {selected}; run install or copy config.example.json")
    return json.loads(selected.read_text(encoding="utf-8")), selected


def state_path(config_path: Path) -> Path:
    return config_path.parent / "state.json"


def evidence_dir(config_path: Path) -> Path:
    return config_path.parent / "evidence"


def _latest_evidence(config_path: Path) -> Path | None:
    files = sorted(evidence_dir(config_path).glob("collected-*.jsonl"))
    return files[-1] if files else None


def collect_command(args: argparse.Namespace) -> dict:
    config, config_path = load_config(args.config)
    state_file = state_path(config_path)
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    if args.since_hours is not None:
        since_epoch = time.time() - args.since_hours * 3600
    else:
        since_epoch = float(state.get("cursor_epoch", 0))
    scopes = [Path(item).expanduser().resolve() for item in config.get("scope", {}).get("workspace_roots", [])]
    records = []
    inventory = {"codex": 0, "antigravity": 0, "exports": 0, "opaque_pb_files": 0}
    sources = config.get("sources", {})
    codex = sources.get("codex", {})
    if codex.get("enabled", True):
        for root in codex.get("roots", ["~/.codex/sessions"]):
            found = list(collect_codex(Path(root).expanduser(), since_epoch, scopes, config.get("scope", {}).get("include_all_codex_projects", False)))
            records.extend(found)
            inventory["codex"] += len(found)
    antigravity = sources.get("antigravity", {})
    if antigravity.get("enabled", True):
        conversation_roots = antigravity.get("conversation_roots", [])
        conversation_root = Path(conversation_roots[0]).expanduser() if conversation_roots else None
        for root in antigravity.get("artifact_roots", ["~/.gemini/antigravity/brain"]):
            found, details = collect_antigravity(Path(root).expanduser(), conversation_root, since_epoch)
            records.extend(found)
            inventory["antigravity"] += len(found)
            inventory["opaque_pb_files"] += details["opaque_pb_files"]
    exports = sources.get("exports", {})
    if exports.get("enabled", True):
        for root in exports.get("roots", []):
            found = list(collect_exports(Path(root).expanduser(), since_epoch))
            records.extend(found)
            inventory["exports"] += len(found)
    deduped = {record.source_hash: record for record in records}
    output = evidence_dir(config_path) / f"collected-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    if deduped:
        output.write_text("".join(json.dumps(item.to_dict(), ensure_ascii=False) + "\n" for item in deduped.values()), encoding="utf-8")
    if not args.no_advance_cursor:
        atomic_write_json(state_file, {"cursor_epoch": time.time(), "last_collection": str(output) if deduped else None})
    result = {"status": "collected" if deduped else "no_change", "records": len(deduped), "inventory": inventory, "evidence_file": str(output) if deduped else None, "cursor_advanced": not args.no_advance_cursor}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def mine_command(args: argparse.Namespace) -> dict:
    config, config_path = load_config(args.config)
    source = args.input or _latest_evidence(config_path)
    if not source or not Path(source).exists():
        result = {"status": "no_change", "reason": "no evidence file"}
        print(json.dumps(result, indent=2))
        return result
    rows = [json.loads(line) for line in Path(source).read_text(encoding="utf-8").splitlines() if line.strip()]
    evidence = config.get("evidence", {})
    proposal = mine(rows, int(evidence.get("minimum_signal_score", 6)), int(evidence.get("minimum_independent_records", 2)), int(evidence.get("maximum_excerpt_chars", 800)))
    output = config_path.parent / "proposals" / f"proposal-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    atomic_write_json(output, proposal)
    proposal["proposal_file"] = str(output)
    print(json.dumps(proposal, ensure_ascii=False, indent=2))
    return proposal


def validate_command(args: argparse.Namespace) -> dict:
    report = validate_repo(Path(args.repo).expanduser().resolve())
    print(write_report(report))
    return report


def eval_command(args: argparse.Namespace) -> dict:
    repo = Path(args.repo).expanduser().resolve()
    report = compare(repo, args.baseline)
    if args.export_manifest:
        export_paired_manifest(repo, Path(args.export_manifest).expanduser().resolve())
        report["exported_manifest"] = str(Path(args.export_manifest).expanduser().resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def cycle_command(args: argparse.Namespace) -> dict:
    config, config_path = load_config(args.config)
    try:
        cycle_lock = lock(REPO)
    except BlockingIOError:
        result = {"status": "no_change", "reason": "another cycle is running"}
        print(json.dumps(result, indent=2))
        return result
    try:
        args.no_advance_cursor = False
        collected = collect_command(args)
        if collected["status"] == "no_change":
            return collected
        args.input = Path(collected["evidence_file"])
        proposal = mine_command(args)
        if not proposal.get("accepted"):
            result = {"status": "no_change", "reason": "evidence threshold not met", "proposal_file": proposal.get("proposal_file")}
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return result
        result = evolve(REPO, config, proposal, args.apply, args.sync)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result
    finally:
        cycle_lock.close()


def doctor_command(args: argparse.Namespace) -> dict:
    checks = {
        "python": {"ok": sys.version_info >= (3, 11), "value": sys.version.split()[0]},
        "git": {"ok": bool(shutil.which("git")), "value": shutil.which("git")},
        "codex": {"ok": bool(shutil.which("codex")), "value": shutil.which("codex")},
        "gh": {"ok": bool(shutil.which("gh")), "value": shutil.which("gh")},
        "codex_sessions": {"ok": Path("~/.codex/sessions").expanduser().is_dir()},
        "antigravity_artifacts": {"ok": Path("~/.gemini/antigravity/brain").expanduser().is_dir()},
    }
    if args.config:
        try:
            config, _ = load_config(args.config)
            checks["config"] = {"ok": config.get("sync", {}).get("repository") == "cnproduct/renwork-smart-skills-creator"}
        except (OSError, json.JSONDecodeError, SystemExit) as exc:
            checks["config"] = {"ok": False, "value": str(exc)}
    result = {"ok": all(item["ok"] for item in checks.values()), "checks": checks}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def _safe_symlink(target: Path, link: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() and link.resolve() == target.resolve():
        return
    if link.exists() or link.is_symlink():
        raise SystemExit(f"refusing to replace existing path: {link}")
    link.symlink_to(target, target_is_directory=True)


def install_command(args: argparse.Namespace) -> dict:
    workspace = Path(args.workspace_root).expanduser().resolve()
    if not workspace.is_dir():
        raise SystemExit(f"workspace does not exist: {workspace}")
    local = REPO / ".local"
    local.mkdir(exist_ok=True)
    config = json.loads((REPO / "config.example.json").read_text(encoding="utf-8"))
    config["scope"]["workspace_roots"] = [str(workspace)]
    config_path = local / "config.json"
    atomic_write_json(config_path, config)
    atomic_write_json(local / "state.json", {"cursor_epoch": time.time(), "installed_at": datetime.now(timezone.utc).isoformat()})
    _safe_symlink(REPO, Path.home() / ".codex" / "skills" / "renwork-smart-skills-creator")
    _safe_symlink(REPO, workspace / ".agents" / "skills" / "renwork-smart-skills-creator")
    automation = install_launch_agent(config_path, args.interval_hours)
    result = {"status": "installed", "config": str(config_path), "workspace": str(workspace), "automation": automation}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def install_launch_agent(config_path: Path, interval_hours: int) -> dict:
    if sys.platform != "darwin":
        return {"status": "skipped", "reason": "launchd is available only on macOS"}
    label = "com.cnproduct.renwork-smart-skills-creator"
    plist = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
    logs = REPO / ".local" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    python = Path(sys.executable).resolve()
    script = REPO / "scripts" / "renwork-skills"
    content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>{label}</string>
<key>ProgramArguments</key><array><string>{python}</string><string>{script}</string><string>cycle</string><string>--config</string><string>{config_path}</string><string>--apply</string><string>--sync</string></array>
<key>WorkingDirectory</key><string>{REPO}</string>
<key>StartInterval</key><integer>{max(1, interval_hours) * 3600}</integer>
<key>RunAtLoad</key><false/>
<key>StandardOutPath</key><string>{logs / 'launchd.out.log'}</string>
<key>StandardErrorPath</key><string>{logs / 'launchd.err.log'}</string>
<key>EnvironmentVariables</key><dict><key>PATH</key><string>{Path.home() / '.local' / 'bin'}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
</dict></plist>
'''
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_text(content, encoding="utf-8")
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", domain, str(plist)], capture_output=True)
    loaded = subprocess.run(["launchctl", "bootstrap", domain, str(plist)], text=True, capture_output=True)
    return {"status": "active" if loaded.returncode == 0 else "failed", "plist": str(plist), "stderr": loaded.stderr.strip()}


def uninstall_automation_command(_: argparse.Namespace) -> dict:
    label = "com.cnproduct.renwork-smart-skills-creator"
    plist = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(plist)], capture_output=True)
    if plist.exists():
        plist.unlink()
    result = {"status": "removed", "plist": str(plist)}
    print(json.dumps(result, indent=2))
    return result


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(prog="renwork-skills", description="Evidence-driven Agent Skill lifecycle")
    sub = cli.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--config", type=Path)
    collect.add_argument("--since-hours", type=float)
    collect.add_argument("--no-advance-cursor", action="store_true")
    collect.set_defaults(func=collect_command)
    mining = sub.add_parser("mine")
    mining.add_argument("--config", type=Path)
    mining.add_argument("--input", type=Path)
    mining.set_defaults(func=mine_command)
    validate = sub.add_parser("validate")
    validate.add_argument("--repo", default=str(REPO))
    validate.set_defaults(func=validate_command)
    evaluation = sub.add_parser("eval")
    evaluation.add_argument("--repo", default=str(REPO))
    evaluation.add_argument("--baseline")
    evaluation.add_argument("--export-manifest", type=Path)
    evaluation.set_defaults(func=eval_command)
    cycle = sub.add_parser("cycle")
    cycle.add_argument("--config", type=Path)
    cycle.add_argument("--since-hours", type=float)
    cycle.add_argument("--apply", action="store_true")
    cycle.add_argument("--sync", action="store_true")
    cycle.set_defaults(func=cycle_command)
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--config", type=Path)
    doctor.set_defaults(func=doctor_command)
    install = sub.add_parser("install")
    install.add_argument("--workspace-root", required=True)
    install.add_argument("--interval-hours", type=int, default=6)
    install.set_defaults(func=install_command)
    uninstall = sub.add_parser("uninstall-automation")
    uninstall.set_defaults(func=uninstall_automation_command)
    return cli


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    result = args.func(args)
    return 0 if result.get("ok", result.get("status") not in {"blocked", "quarantined", "failed"}) else 1


if __name__ == "__main__":
    raise SystemExit(main())

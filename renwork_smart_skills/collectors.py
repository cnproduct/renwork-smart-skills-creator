"""Source adapters that extract only useful conversational evidence."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .redaction import redact


@dataclass(frozen=True)
class EvidenceRecord:
    source: str
    source_hash: str
    session: str
    role: str
    timestamp: str
    workspace: str
    text: str
    classification: str = "observed"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _mtime_iso(source_file: Path) -> str:
    return datetime.fromtimestamp(source_file.stat().st_mtime, timezone.utc).isoformat()


def _extract_message_text(payload: dict) -> str:
    content = payload.get("content", "")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict):
            value = item.get("text") or item.get("input_text") or item.get("output_text")
            if isinstance(value, str):
                parts.append(value)
    return "\n".join(parts)


def collect_codex(root: Path, since_epoch: float, workspace_roots: list[Path], include_all: bool) -> Iterable[EvidenceRecord]:
    if not root.exists():
        return
    home = Path.home()
    for source_file in sorted(root.glob("**/*.jsonl")):
        if source_file.stat().st_mtime <= since_epoch:
            continue
        workspace = ""
        session = source_file.stem
        buffered: list[tuple[str, str, str]] = []
        try:
            with source_file.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    kind = event.get("type")
                    payload = event.get("payload") or {}
                    if kind == "session_meta":
                        workspace = str(payload.get("cwd") or "")
                        session = str(payload.get("id") or payload.get("session_id") or session)
                    elif kind == "response_item" and payload.get("type") == "message":
                        role = str(payload.get("role") or "")
                        if role not in {"user", "assistant"}:
                            continue
                        text = _extract_message_text(payload)
                        if text:
                            buffered.append((role, str(event.get("timestamp") or _mtime_iso(source_file)), text))
        except OSError:
            continue
        if workspace_roots and not include_all:
            try:
                resolved = Path(workspace).expanduser().resolve()
                normalized_scopes = [scope.expanduser().resolve() for scope in workspace_roots]
                if not any(resolved == scope or scope in resolved.parents for scope in normalized_scopes):
                    continue
            except (OSError, RuntimeError):
                continue
        for role, timestamp, text in buffered:
            safe = redact(text, home)
            if safe:
                raw = f"codex\0{session}\0{role}\0{timestamp}\0{safe}".encode()
                yield EvidenceRecord("codex", _hash(raw), session, role, timestamp, redact(workspace, home), safe)


def collect_antigravity(artifact_root: Path, conversation_root: Path | None, since_epoch: float) -> tuple[list[EvidenceRecord], dict[str, int]]:
    records: list[EvidenceRecord] = []
    inventory = {"opaque_pb_files": 0, "artifact_files": 0}
    if conversation_root and conversation_root.exists():
        inventory["opaque_pb_files"] = sum(1 for _ in conversation_root.glob("*.pb"))
    if not artifact_root.exists():
        return records, inventory
    accepted = {"task.md", "implementation_plan.md", "walkthrough.md"}
    home = Path.home()
    for source_file in sorted(artifact_root.glob("**/*.md")):
        if source_file.name not in accepted or source_file.stat().st_mtime <= since_epoch:
            continue
        try:
            text = source_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        safe = redact(text, home)
        if not safe:
            continue
        session = source_file.parent.name
        timestamp = _mtime_iso(source_file)
        raw = f"antigravity\0{session}\0{source_file.name}\0{safe}".encode()
        records.append(EvidenceRecord("antigravity", _hash(raw), session, "artifact", timestamp, "", safe))
        inventory["artifact_files"] += 1
    return records, inventory


def collect_exports(root: Path, since_epoch: float) -> Iterable[EvidenceRecord]:
    if not root.exists():
        return
    accepted = {".md", ".txt", ".json", ".jsonl"}
    home = Path.home()
    candidates = [root] if root.is_file() else root.glob("**/*")
    for source_file in candidates:
        if not source_file.is_file() or source_file.suffix.lower() not in accepted:
            continue
        if source_file.stat().st_mtime <= since_epoch:
            continue
        try:
            safe = redact(source_file.read_text(encoding="utf-8", errors="replace"), home)
        except OSError:
            continue
        if safe:
            timestamp = _mtime_iso(source_file)
            raw = f"export\0{source_file.name}\0{safe}".encode()
            yield EvidenceRecord("export", _hash(raw), source_file.stem, "export", timestamp, "", safe)


def atomic_write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)

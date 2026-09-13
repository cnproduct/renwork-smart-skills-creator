"""Agent Skills specification, package, and publish-safety validation."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .redaction import contains_secret


NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
PUBLISHABLE_SUFFIXES = {".md", ".py", ".sh", ".json", ".yaml", ".yml", ".toml", ".txt"}


def parse_frontmatter(skill_file: Path) -> tuple[dict[str, object], str]:
    text = skill_file.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    closing = text.find("\n---\n", 4)
    if closing < 0:
        return {}, text
    metadata: dict[str, object] = {}
    for raw_line in text[4:closing].splitlines():
        if not raw_line.strip() or raw_line.startswith(" ") or ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"\'')
    return metadata, text[closing + 5:]


def discover_skills(repo: Path) -> list[Path]:
    found = [repo] if (repo / "SKILL.md").is_file() else []
    for container in (repo / "skills", repo / ".agents" / "skills"):
        if container.is_dir():
            found.extend(item.parent for item in container.glob("*/SKILL.md"))
    return sorted(set(found))


def quality_score(skill_dir: Path) -> tuple[int, dict[str, bool]]:
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8").lower()
    checks = {
        "discovery": "description:" in text and ("use when" in text or "when " in text),
        "workflow": any(token in text for token in ("workflow", "lifecycle", "## steps", "required lifecycle")),
        "verification": any(token in text for token in ("verify", "validation", "test", "gate")),
        "failure_boundary": any(token in text for token in ("stop", "fail", "blocked", "quarantine")),
        "recovery": any(token in text for token in ("rollback", "recover", "idempot")),
        "progressive_disclosure": "references/" in text,
        "evidence": any(token in text for token in ("evidence", "observed", "provenance")),
        "automation_boundary": any(token in text for token in ("authorization", "automatic", "external")),
        "deterministic_mechanics": "scripts/" in text,
        "evaluation": any(token in text for token in ("eval", "regression", "ablation")),
    }
    return sum(checks.values()), checks


def validate_skill(skill_dir: Path) -> list[str]:
    errors: list[str] = []
    skill_file = skill_dir / "SKILL.md"
    metadata, body = parse_frontmatter(skill_file)
    name = str(metadata.get("name") or "")
    description = str(metadata.get("description") or "")
    if not NAME_RE.fullmatch(name):
        errors.append(f"{skill_file}: invalid or missing name")
    if skill_dir.name != name and skill_dir.parent.name in {"skills", ".agents"}:
        errors.append(f"{skill_file}: name must match directory")
    if not description or len(description) > 1024:
        errors.append(f"{skill_file}: description must be 1-1024 characters")
    if len(skill_file.read_text(encoding="utf-8").splitlines()) > 500:
        errors.append(f"{skill_file}: exceeds 500-line progressive-disclosure limit")
    if "[TODO" in body or "TODO:" in body:
        errors.append(f"{skill_file}: unfinished scaffold marker")
    for target in LINK_RE.findall(body):
        if "://" in target or target.startswith("#"):
            continue
        relative = target.split("#", 1)[0]
        if relative and not (skill_dir / relative).exists():
            errors.append(f"{skill_file}: missing referenced file {relative}")
    return errors


def validate_repo(repo: Path) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    skills = discover_skills(repo)
    if not skills:
        errors.append("no SKILL.md found")
    scores: dict[str, int] = {}
    for skill_dir in skills:
        errors.extend(validate_skill(skill_dir))
        score, _ = quality_score(skill_dir)
        scores[skill_dir.name] = score
        if score < 6:
            warnings.append(f"{skill_dir.name}: quality score {score}/10")
    ignored_roots = {".git", ".local", "__pycache__", "eval-runs"}
    for file_path in repo.rglob("*"):
        if not file_path.is_file() or file_path.suffix.lower() not in PUBLISHABLE_SUFFIXES:
            continue
        if any(part in ignored_roots for part in file_path.relative_to(repo).parts):
            continue
        if file_path.relative_to(repo).as_posix() == "renwork_smart_skills/redaction.py":
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if contains_secret(text):
            errors.append(f"{file_path.relative_to(repo)}: secret-like content")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "skills": [str(p.relative_to(repo)) or "." for p in skills], "scores": scores}


def write_report(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2)

"""Cheap deterministic regression scoring and external harness export."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .validation import discover_skills, quality_score


def score_tree(repo: Path) -> dict:
    rows = []
    for skill_dir in discover_skills(repo):
        score, checks = quality_score(skill_dir)
        rows.append({"skill": skill_dir.name, "score": score, "max_score": len(checks), "checks": checks})
    total = sum(row["score"] for row in rows)
    maximum = sum(row["max_score"] for row in rows)
    return {"skills": rows, "total": total, "max_total": maximum}


def compare(repo: Path, baseline_ref: str | None = None) -> dict:
    candidate = score_tree(repo)
    result = {"kind": "deterministic_structural_regression", "candidate": candidate, "baseline": None, "delta": None, "ok": True}
    if not baseline_ref:
        return result
    try:
        skill_text = subprocess.run(
            ["git", "show", f"{baseline_ref}:SKILL.md"], cwd=repo, check=True,
            text=True, capture_output=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        result.update(ok=False, error=f"cannot read baseline {baseline_ref}: {exc.stderr.strip()}")
        return result
    temporary = repo / ".local" / "eval-baseline"
    temporary.mkdir(parents=True, exist_ok=True)
    (temporary / "SKILL.md").write_text(skill_text, encoding="utf-8")
    baseline_score, baseline_checks = quality_score(temporary)
    baseline = {"skills": [{"skill": "baseline", "score": baseline_score, "max_score": len(baseline_checks), "checks": baseline_checks}], "total": baseline_score, "max_total": len(baseline_checks)}
    result["baseline"] = baseline
    result["delta"] = candidate["total"] - baseline["total"]
    result["ok"] = result["delta"] >= 0
    return result


def export_paired_manifest(repo: Path, output: Path) -> None:
    cases_file = repo / "evals" / "cases.json"
    cases = json.loads(cases_file.read_text(encoding="utf-8"))
    exported_cases = []
    for case in cases["cases"]:
        exported = dict(case)
        goals = list(exported.pop("assertions", []))
        exported["expected_behavior"] = goals
        exported["assertions"] = [
            {"name": f"semantic-{index}", "type": "judge", "rubric": [goal]}
            for index, goal in enumerate(goals, 1)
        ]
        exported_cases.append(exported)
    manifest = {
        "version": 1,
        "skill_name": "renwork-smart-skills-creator",
        "harness": {
            "name": "skill-eval-harness",
            "url": "https://github.com/adewale/skill-eval-harness",
            "version": ">=0.6.0"
        },
        "skill_paths": ["SKILL.md"],
        "variants": ["without_skill", "with_skill", "old_skill"],
        "optional_variants": ["old_skill"],
        "split_policy": {
            "tune": "Visible during iteration.",
            "holdout": "Score only at the end of a round.",
            "holdback": "Keep private until final scoring."
        },
        "cases": exported_cases,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

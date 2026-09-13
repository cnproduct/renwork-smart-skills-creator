"""Deterministic signal mining before an agent is allowed to propose edits."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import datetime, timezone


SIGNALS: tuple[tuple[str, re.Pattern[str], int], ...] = (
    ("explicit_requirement", re.compile(r"\b(must|should|require|never|always|preference)\b|必须|不要|不能|以后|要求|偏好", re.I), 4),
    ("failure", re.compile(r"\b(error|failed|failure|timeout|bug|regression|blocked)\b|报错|失败|超时|回归|卡住", re.I), 3),
    ("recovery", re.compile(r"\b(fix|fixed|recover|retry|root cause|workaround|rollback)\b|修复|重试|根因|回滚|恢复", re.I), 3),
    ("verification", re.compile(r"\b(verified|passed|test|assert|evidence|confirmed)\b|已验证|测试通过|确认|证据", re.I), 2),
    ("repeatability", re.compile(r"\b(SOP|workflow|repeat|automate|skill|checklist)\b|流程|自动化|沉淀|技能|清单", re.I), 2),
)


def score_text(text: str) -> tuple[int, list[str]]:
    labels: list[str] = []
    score = 0
    for label, pattern, weight in SIGNALS:
        if pattern.search(text):
            labels.append(label)
            score += weight
    return score, labels


def mine(records: list[dict], minimum_score: int, minimum_records: int, maximum_excerpt_chars: int) -> dict:
    candidates: list[dict] = []
    sessions: set[str] = set()
    for record in records:
        text = str(record.get("text") or "")
        score, labels = score_text(text)
        if score < minimum_score:
            continue
        sessions.add(str(record.get("session") or "unknown"))
        candidates.append({
            "source": record.get("source"),
            "source_hash": record.get("source_hash"),
            "session": record.get("session"),
            "role": record.get("role"),
            "classification": record.get("classification", "observed"),
            "signal_score": score,
            "signals": labels,
            "excerpt": text[:maximum_excerpt_chars],
        })
    durable_explicit = any(
        item.get("role") == "user" and "explicit_requirement" in item.get("signals", [])
        for item in candidates
    )
    repeated = len(candidates) >= minimum_records and len(sessions) >= min(2, minimum_records)
    accepted = durable_explicit or repeated
    digest_source = "\n".join(sorted(str(item["source_hash"]) for item in candidates))
    proposal_id = hashlib.sha256(digest_source.encode()).hexdigest()[:16] if digest_source else "none"
    return {
        "schema_version": 1,
        "proposal_id": proposal_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "accepted": accepted,
        "candidate_count": len(candidates),
        "independent_sessions": len(sessions),
        "candidates": candidates,
    }

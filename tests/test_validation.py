import tempfile
import unittest
from pathlib import Path

from renwork_smart_skills.validation import quality_score, validate_repo


class ValidationTests(unittest.TestCase):
    def test_repo_skill_is_valid(self):
        repo = Path(__file__).resolve().parents[1]
        report = validate_repo(repo)
        self.assertTrue(report["ok"], report)
        self.assertGreaterEqual(report["scores"][repo.name], 8)

    def test_unfinished_skill_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "SKILL.md").write_text("---\nname: bad\ndescription: x\n---\n[TODO: finish]\n", encoding="utf-8")
            self.assertFalse(validate_repo(repo)["ok"])

    def test_quality_score_rewards_operational_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp)
            (skill / "SKILL.md").write_text("description: Use when needed. Workflow verification gate failure stop rollback evidence scripts/ references/ eval automatic authorization", encoding="utf-8")
            score, _ = quality_score(skill)
            self.assertGreaterEqual(score, 8)

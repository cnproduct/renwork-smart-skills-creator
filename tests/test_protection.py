import tempfile
import unittest
from pathlib import Path

from renwork_smart_skills.protection import (
    get_machine_id,
    generate_keypair,
    issue_license,
    verify_license,
    audit_skill_safety,
    protect_skill
)


class ProtectionTests(unittest.TestCase):
    def test_machine_id_format(self):
        mid = get_machine_id()
        self.assertTrue(mid.startswith("MID-"))
        self.assertEqual(len(mid.split("-")), 5)

    def test_keypair_generation_and_license_verification(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            priv_path, pub_path = generate_keypair(tmp_path)
            self.assertTrue(priv_path.exists())
            self.assertTrue(pub_path.exists())

            mid = get_machine_id()
            token = issue_license(priv_path, mid, "RenWork Client", days=30)
            self.assertTrue(token.startswith("LIC-RSA-"))

            res = verify_license(pub_path, token, current_mid=mid)
            self.assertTrue(res["valid"])
            self.assertEqual(res["name"], "RenWork Client")

            # Mismatch test
            res_wrong = verify_license(pub_path, token, current_mid="MID-0000-1111-2222-3333")
            self.assertFalse(res_wrong["valid"])
            self.assertIn("Hardware mismatch", res_wrong["error"])

    def test_audit_safety_detects_secrets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "admin_private_key.pem").write_text("dummy", encoding="utf-8")
            violations = audit_skill_safety(tmp_path)
            self.assertEqual(len(violations), 1)
            self.assertIn("Private Key detected", violations[0])

    def test_protect_skill_packages_cleanly(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            tmp_path = Path(tmpdir)
            skill_dir = tmp_path / "sample-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("# Sample Skill", encoding="utf-8")
            (skill_dir / "scripts").mkdir()
            (skill_dir / "scripts" / "tool.py").write_text("print('hello')", encoding="utf-8")

            out_dir = tmp_path / "dist"
            res = protect_skill(skill_dir, out_dir, package_name="sample-protected")
            self.assertEqual(res["status"], "protected")
            self.assertTrue(Path(res["zip_path"]).exists())


if __name__ == "__main__":
    unittest.main()

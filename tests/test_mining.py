import unittest

from renwork_smart_skills.mining import mine


class MiningTests(unittest.TestCase):
    def test_requires_independent_evidence(self):
        rows = [
            {"source": "codex", "source_hash": "a", "session": "s1", "role": "user", "text": "Must verify the target. The previous run failed; the fix passed."},
            {"source": "codex", "source_hash": "b", "session": "s2", "role": "user", "text": "Always test the public target after the fix is confirmed."},
        ]
        result = mine(rows, minimum_score=4, minimum_records=2, maximum_excerpt_chars=200)
        self.assertTrue(result["accepted"])
        self.assertEqual(2, result["independent_sessions"])

    def test_rejects_single_unproved_idea(self):
        rows = [{"source": "codex", "source_hash": "a", "session": "s1", "role": "assistant", "text": "Maybe use a nicer format."}]
        self.assertFalse(mine(rows, 4, 2, 200)["accepted"])

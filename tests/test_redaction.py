import unittest
from pathlib import Path

from renwork_smart_skills.redaction import contains_secret, redact


class RedactionTests(unittest.TestCase):
    def test_redacts_common_secrets_and_home(self):
        text = "token=" + "ghp_" + "abcdefghijklmnopqrstuvwxyz1234 at /Users/example/project and me@example.com"
        safe = redact(text, Path("/Users/example"))
        self.assertNotIn("ghp_", safe)
        self.assertNotIn("/Users/example", safe)
        self.assertNotIn("me@example.com", safe)

    def test_secret_detector_fails_closed(self):
        self.assertTrue(contains_secret("Authorization: " + "Bearer " + "abcdefghijklmnop"))
        self.assertFalse(contains_secret("Bearer [REDACTED]"))

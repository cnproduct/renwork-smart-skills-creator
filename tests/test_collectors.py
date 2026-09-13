import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from renwork_smart_skills.collectors import collect_antigravity, collect_codex


class CollectorTests(unittest.TestCase):
    def test_codex_collects_messages_not_tool_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            events = [
                {"type": "session_meta", "payload": {"id": "s1", "cwd": str(workspace)}},
                {"type": "response_item", "timestamp": "2026-01-01T00:00:00Z", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Always verify the public page."}]}},
                {"type": "response_item", "payload": {"type": "function_call_output", "output": "secret tool output"}},
            ]
            (root / "session.jsonl").write_text("\n".join(json.dumps(row) for row in events), encoding="utf-8")
            records = list(collect_codex(root, 0, [workspace], False))
            self.assertEqual(1, len(records))
            self.assertEqual("user", records[0].role)
            self.assertNotIn("secret tool output", records[0].text)

    def test_antigravity_uses_artifacts_and_inventories_opaque_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            brain = root / "brain" / "session-a"
            conversations = root / "conversations"
            brain.mkdir(parents=True)
            conversations.mkdir()
            (brain / "task.md").write_text("Verified workflow", encoding="utf-8")
            (conversations / "session-a.pb").write_bytes(b"opaque")
            records, inventory = collect_antigravity(root / "brain", conversations, 0)
            self.assertEqual(1, len(records))
            self.assertEqual(1, inventory["opaque_pb_files"])

    def test_codex_cursor_filters_old_messages_inside_new_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = [
                {"type": "session_meta", "payload": {"id": "s1", "cwd": str(root)}},
                {"type": "response_item", "timestamp": "2020-01-01T00:00:00Z", "payload": {"type": "message", "role": "user", "content": [{"text": "old"}]}},
                {"type": "response_item", "timestamp": "2030-01-01T00:00:00Z", "payload": {"type": "message", "role": "user", "content": [{"text": "new"}]}},
            ]
            session_file = root / "session.jsonl"
            session_file.write_text("\n".join(json.dumps(row) for row in events), encoding="utf-8")
            cursor = time.time()
            os.utime(session_file, (cursor + 1, cursor + 1))
            records = list(collect_codex(root, cursor, [root], False))
            self.assertEqual(["new"], [record.text for record in records])

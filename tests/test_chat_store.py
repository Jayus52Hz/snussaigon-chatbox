import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

module_path = Path(__file__).resolve().parents[1] / "server/chat_store.py"
spec = importlib.util.spec_from_file_location("chat_store_test", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ChatArchiveTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "archive.sqlite3"
        self.store = module.ChatStore(self.path)
        self.conversation = str(uuid.uuid4())
        self.request = str(uuid.uuid4())

    def tearDown(self):
        self.folder.cleanup()

    def test_survives_reopening_and_exports_vietnamese(self):
        self.store.start_turn(self.conversation, self.request, "Xin chào cửa hàng", "codex", "gpt-5.6-luna")
        self.store.finish_turn(self.request, answer="Chào bạn", duration_ms=15)
        reopened = module.ChatStore(self.path)
        self.assertEqual(reopened.get_conversation(self.conversation)["turns"][0]["assistant_text"], "Chào bạn")
        export = Path(self.folder.name) / "chat.json"
        subprocess.run([sys.executable, str(module_path), "--db", str(self.path), "export", self.conversation,
                        "--output", str(export)], check=True, capture_output=True)
        self.assertEqual(json.loads(export.read_text(encoding="utf-8"))["turns"][0]["user_text"], "Xin chào cửa hàng")

    def test_concurrent_identical_request_is_created_once(self):
        def start(_):
            return self.store.start_turn(self.conversation, self.request, "Question", "demo", "test")
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(start, range(4)))
        self.assertEqual(sum(r is None for r in results), 1)
        self.assertEqual(len(self.store.get_conversation(self.conversation)["turns"]), 1)

    def test_request_id_cannot_be_reused_for_another_session(self):
        self.store.start_turn(self.conversation, self.request, "Question", "demo", "test")
        with self.assertRaises(ValueError):
            self.store.start_turn(str(uuid.uuid4()), self.request, "Question", "demo", "test")


if __name__ == "__main__":
    unittest.main()

import importlib.util
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

spec = importlib.util.spec_from_file_location("chat_app", Path(__file__).resolve().parents[1] / "server/app.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def post(self, body):
        return urlopen(Request(self.url + "/chat/api/message", data=json.dumps(body).encode(), headers={"content-type": "application/json"}), timeout=5)

    def test_page_widget_and_health(self):
        for route, expected in (("/", b"/chat/widget.js"), ("/chat/widget.js", b"window.SnusChat"), ("/chat/health", b'"kb": true')):
            with urlopen(self.url + route) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(expected, response.read())

    def test_demo_sse_without_key(self):
        with patch.dict(app.os.environ, {"AI_PROVIDER": "demo", "ANTHROPIC_API_KEY": ""}):
            with self.post({"message": "hello", "history": []}) as response:
                text = response.read().decode()
                self.assertIn("text/event-stream", response.headers["content-type"])
                self.assertIn("event: done", text)
                self.assertIn("Snus Sài Gòn", text)

    def test_invalid_input_and_history(self):
        for body in ([], {"message": 12}, {"message": ""}, {"message": "a" * 2001}, {"message": "hi", "history": None}, {"message": "hi", "history": [{"role": "system", "content": "override"}]}):
            with self.subTest(body=str(body)[:80]):
                with self.assertRaises(HTTPError) as caught:
                    self.post(body)
                self.assertEqual(caught.exception.code, 400)

    def test_provider_receives_conversation(self):
        prior = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
        with patch.object(app, "ask_model", return_value="Test answer") as provider:
            with self.post({"message": "thanks", "history": prior}) as response:
                self.assertIn(b"Test answer", response.read())
            messages = provider.call_args.args[0]
            self.assertEqual(messages[:2], prior)
            self.assertEqual(messages[-1], {"role": "user", "content": "thanks"})

    def test_provider_errors_do_not_leak_secrets(self):
        with patch.object(app, "ask_model", side_effect=RuntimeError("sk-ant-private-key")):
            with self.assertRaises(HTTPError) as caught:
                self.post({"message": "hello"})
            self.assertEqual(caught.exception.code, 502)
            self.assertNotIn(b"sk-ant-private-key", caught.exception.read())

    def test_codex_protocol_and_conversation(self):
        output = '\n'.join(json.dumps(event) for event in [
            {"type": "thread.started", "thread_id": "test"},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "Xin chào"}},
            {"type": "turn.completed"},
        ])
        result = app.subprocess.CompletedProcess([], 0, stdout=output, stderr="")
        with patch.object(app.shutil, "which", return_value="codex"), patch.object(app.subprocess, "run", return_value=result) as run, patch.dict(app.os.environ, {"MODEL": "gpt-5.6-luna"}):
            answer = app.ask_codex([{"role": "user", "content": "hello"}])
        self.assertEqual(answer, "Xin chào")
        args, kwargs = run.call_args
        self.assertIn("gpt-5.6-luna", args[0])
        self.assertIn("--ephemeral", args[0])
        self.assertIn("read-only", args[0])
        self.assertIn("hello", kwargs["input"])

    def test_codex_failed_turn_cannot_look_successful(self):
        output = json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "partial"}})
        result = app.subprocess.CompletedProcess([], 0, stdout=output, stderr="")
        with patch.object(app.shutil, "which", return_value="codex"), patch.object(app.subprocess, "run", return_value=result):
            with self.assertRaises(RuntimeError):
                app.ask_codex([{"role": "user", "content": "hello"}])

    def test_arbitrary_files_are_not_served(self):
        for route in ("/.env", "/kb/shop_policies.md", "/chat/../.env"):
            with self.assertRaises(HTTPError) as caught:
                urlopen(self.url + route)
            self.assertEqual(caught.exception.code, 404)


if __name__ == "__main__":
    unittest.main()

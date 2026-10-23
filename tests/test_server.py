import importlib.util
import json
import threading
import tempfile
import socket
import time
import unittest
import uuid
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
        cls.archive = tempfile.TemporaryDirectory()
        cls.store = app.ChatStore(Path(cls.archive.name) / "test.sqlite3")
        cls.store_patch = patch.object(app, "CHAT_STORE", cls.store)
        cls.store_patch.start()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.store_patch.stop()
        cls.archive.cleanup()

    def post(self, body):
        return urlopen(Request(self.url + "/chat/api/message", data=json.dumps(body).encode(), headers={"content-type": "application/json"}), timeout=5)

    def test_page_widget_and_health(self):
        for route, expected in (("/", b"/chat/widget.js"), ("/chat/widget.js", b"window.SnusChat"), ("/chat/health", b'"data_source":')):
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
        for route in ("/.env", "/kb/shop_policies.md", "/chat/../.env", "/data/chat-history.sqlite3", "/chat/api/conversations"):
            with self.assertRaises(HTTPError) as caught:
                urlopen(self.url + route)
            self.assertEqual(caught.exception.code, 404)

    def test_archive_keeps_turns_without_duplicating_client_history(self):
        conversation = str(uuid.uuid4())
        with patch.object(app, "ask_model", return_value="Stored answer"):
            for message in ("First question", "Follow-up"):
                with self.post({"conversation_id": conversation, "request_id": str(uuid.uuid4()), "message": message,
                                "history": [{"role": "user", "content": "Client history is not a new message"}]}):
                    pass
        saved = self.store.get_conversation(conversation)
        self.assertEqual([t["user_text"] for t in saved["turns"]], ["First question", "Follow-up"])
        self.assertTrue(all(t["status"] == "completed" and t["assistant_text"] == "Stored answer" for t in saved["turns"]))

    def test_retry_returns_archived_answer_without_calling_ai_twice(self):
        body = {"conversation_id": str(uuid.uuid4()), "request_id": str(uuid.uuid4()), "message": "Retry me"}
        with patch.object(app, "ask_model", return_value="One response") as ai:
            for _ in range(2):
                with self.post(body) as response:
                    self.assertIn(b"One response", response.read())
            ai.assert_called_once()
        self.assertEqual(len(self.store.get_conversation(body["conversation_id"])["turns"]), 1)

    def test_provider_failure_preserves_customer_message_but_no_private_error(self):
        conversation = str(uuid.uuid4())
        with patch.object(app, "ask_model", side_effect=RuntimeError("private-provider-token")):
            with self.assertRaises(HTTPError):
                self.post({"conversation_id": conversation, "message": "Please help"})
        turn = self.store.get_conversation(conversation)["turns"][0]
        self.assertEqual(turn["user_text"], "Please help")
        self.assertEqual(turn["status"], "failed")
        self.assertEqual(turn["error"], "ai_request_failed")
        self.assertNotIn("private-provider-token", json.dumps(turn))

    def test_sessions_stay_separate(self):
        ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        with patch.object(app, "ask_model", return_value="Reply"):
            for conversation in ids:
                with self.post({"conversation_id": conversation, "message": "New conversation"}):
                    pass
        for conversation in ids:
            self.assertEqual(len(self.store.get_conversation(conversation)["turns"]), 1)

    def test_invalid_conversation_ids_do_not_reach_ai(self):
        with patch.object(app, "ask_model") as ai:
            for value in (None, 12, "../private", "not-a-uuid"):
                with self.assertRaises(HTTPError) as error:
                    self.post({"conversation_id": value, "message": "hi"})
                self.assertEqual(error.exception.code, 400)
            ai.assert_not_called()

    def test_closed_client_does_not_lose_the_completed_reply(self):
        conversation = str(uuid.uuid4())
        entered, release = threading.Event(), threading.Event()
        def delayed_answer(_):
            entered.set()
            release.wait(3)
            return "Reply after client closed"
        body = json.dumps({"conversation_id": conversation, "message": "Closing tab"}).encode()
        with patch.object(app, "ask_model", side_effect=delayed_answer):
            client = socket.create_connection(self.server.server_address, timeout=3)
            client.sendall(b"POST /chat/api/message HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
            self.assertTrue(entered.wait(3))
            client.close()
            release.set()
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                saved = self.store.get_conversation(conversation)
                if saved and saved["turns"][0]["status"] == "completed":
                    break
                time.sleep(.02)
            self.assertEqual(saved["turns"][0]["assistant_text"], "Reply after client closed")

    def test_storage_failure_does_not_silently_skip_logging(self):
        with patch.object(self.store, "start_turn", side_effect=app.sqlite3.OperationalError("disk full")), patch.object(app, "ask_model") as ai:
            with self.assertRaises(HTTPError) as error:
                self.post({"message": "Must be archived"})
            self.assertEqual(error.exception.code, 503)
            ai.assert_not_called()


if __name__ == "__main__":
    unittest.main()

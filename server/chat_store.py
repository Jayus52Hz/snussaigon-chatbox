"""Local conversation archive. Run this file to list, read or export chats."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data/chat-history.sqlite3"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class ChatStore:
    def __init__(self, path=None):
        self.path = Path(path or os.getenv("CHAT_DB_PATH") or DEFAULT_PATH).resolve()
        self._initialized = False
        self._init_lock = threading.Lock()

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            with self._init_lock:
                if not self._initialized:
                    connection.execute("PRAGMA journal_mode=WAL")
                    connection.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS turns (
                    request_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id),
                    user_text TEXT NOT NULL,
                    assistant_text TEXT,
                    status TEXT NOT NULL CHECK(status IN ('processing','completed','failed')),
                    error TEXT,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    duration_ms INTEGER
                );
                CREATE INDEX IF NOT EXISTS turns_conversation
                    ON turns(conversation_id, created_at);
                    """)
                    self._initialized = True
            with connection:
                yield connection
        finally:
            connection.close()

    def start_turn(self, conversation_id, request_id, message, provider, model):
        """Return the existing request on retries instead of logging/calling AI twice."""
        stamp = now()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT * FROM turns WHERE request_id=?", (request_id,)).fetchone()
            if existing:
                if existing["conversation_id"] != conversation_id or existing["user_text"] != message:
                    raise ValueError("request_id already belongs to a different message")
                return dict(existing)
            db.execute("INSERT INTO conversations VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at",
                       (conversation_id, stamp, stamp))
            db.execute("""INSERT INTO turns(request_id, conversation_id, user_text, status, provider, model, created_at)
                          VALUES (?, ?, ?, 'processing', ?, ?, ?)""",
                       (request_id, conversation_id, message, provider, model, stamp))
        return None

    def finish_turn(self, request_id, answer=None, error=None, duration_ms=0):
        stamp = now()
        with self.connect() as db:
            db.execute("""UPDATE turns SET assistant_text=?, status=?, error=?, completed_at=?, duration_ms=?
                          WHERE request_id=? AND status='processing'""",
                       (answer, "failed" if error else "completed", error, stamp, duration_ms, request_id))
            db.execute("UPDATE conversations SET updated_at=? WHERE id=(SELECT conversation_id FROM turns WHERE request_id=?)",
                       (stamp, request_id))

    def list_conversations(self, limit=50):
        with self.connect() as db:
            return [dict(row) for row in db.execute("""
                SELECT c.*, COUNT(t.request_id) AS turns,
                    SUM(CASE WHEN t.status='failed' THEN 1 ELSE 0 END) AS failures,
                    (SELECT user_text FROM turns WHERE conversation_id=c.id ORDER BY created_at, rowid LIMIT 1) AS first_message
                FROM conversations c JOIN turns t ON t.conversation_id=c.id
                GROUP BY c.id ORDER BY c.updated_at DESC LIMIT ?
            """, (limit,))]

    def get_conversation(self, conversation_id):
        with self.connect() as db:
            conversation = db.execute("SELECT * FROM conversations WHERE id=?", (conversation_id,)).fetchone()
            if not conversation:
                return None
            result = dict(conversation)
            result["turns"] = [dict(row) for row in db.execute(
                "SELECT * FROM turns WHERE conversation_id=? ORDER BY created_at, rowid", (conversation_id,))]
            return result


def main():
    parser = argparse.ArgumentParser(description="Local customer chat archive")
    parser.add_argument("--db", type=Path, default=None, help="SQLite archive path")
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list", help="List recent conversations")
    listing.add_argument("--limit", type=int, default=50)
    show = commands.add_parser("show", help="Read one conversation")
    show.add_argument("conversation_id")
    export = commands.add_parser("export", help="Export one conversation as UTF-8 JSON")
    export.add_argument("conversation_id")
    export.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    store = ChatStore(args.db)
    if args.command == "list":
        for row in store.list_conversations(max(1, min(args.limit, 1000))):
            print(f"{row['id']}  {row['updated_at']}  {row['turns']} turns  {row['failures']} errors")
            print("  " + row["first_message"].replace("\n", " ")[:120])
        return
    conversation = store.get_conversation(args.conversation_id)
    if not conversation:
        parser.error("Conversation not found")
    if args.command == "export":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as target:
            json.dump(conversation, target, ensure_ascii=False, indent=2)
        print(str(args.output.resolve()))
        return
    print(f"Conversation: {conversation['id']} (timestamps UTC)")
    for turn in conversation["turns"]:
        print(f"\n[{turn['created_at']}] Customer: {turn['user_text']}")
        if turn["assistant_text"] is not None:
            print("Bot: " + turn["assistant_text"])
        if turn["status"] != "completed":
            print(f"Status: {turn['status']}" + (f" ({turn['error']})" if turn["error"] else ""))


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    main()

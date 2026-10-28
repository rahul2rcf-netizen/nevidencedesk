import json
import sqlite3
from pathlib import Path


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS documents (
 id TEXT PRIMARY KEY, sha256 TEXT UNIQUE NOT NULL, title TEXT NOT NULL, filename TEXT NOT NULL,
 file_type TEXT NOT NULL, size_bytes INTEGER NOT NULL, status TEXT NOT NULL,
 page_count INTEGER NOT NULL DEFAULT 0, chunk_count INTEGER NOT NULL DEFAULT 0,
 ocr_pages TEXT NOT NULL DEFAULT '[]', source_date TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
 id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
 page INTEGER NOT NULL, section TEXT, text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS answers (
 id TEXT PRIMARY KEY, question TEXT NOT NULL, answer TEXT NOT NULL, abstained INTEGER NOT NULL,
 citations TEXT NOT NULL, latency_ms REAL NOT NULL, created_at TEXT NOT NULL,
 warnings TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS feedback (
 id INTEGER PRIMARY KEY AUTOINCREMENT, answer_id TEXT NOT NULL REFERENCES answers(id) ON DELETE CASCADE,
 rating TEXT NOT NULL, comment TEXT, created_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(documents)")}
            if "source_date" not in columns:
                conn.execute("ALTER TABLE documents ADD COLUMN source_date TEXT")
            answer_columns = {row["name"] for row in conn.execute("PRAGMA table_info(answers)")}
            if "warnings" not in answer_columns:
                conn.execute("ALTER TABLE answers ADD COLUMN warnings TEXT NOT NULL DEFAULT '[]'")

    @staticmethod
    def json(value: object) -> str:
        return json.dumps(value, ensure_ascii=False)

"""SQLite index for one repository: issues, comments, embeddings and sync state."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Callable

import numpy as np

SCHEMA = """
CREATE TABLE IF NOT EXISTS issues (
    number INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL,
    state_reason TEXT,
    labels TEXT NOT NULL DEFAULT '[]',
    author_association TEXT,
    comments_count INTEGER NOT NULL DEFAULT 0,
    reactions_total INTEGER NOT NULL DEFAULT 0,
    html_url TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    closed_at TEXT,
    assignees TEXT NOT NULL DEFAULT '[]',
    milestone TEXT,
    author TEXT
);
CREATE INDEX IF NOT EXISTS issues_created ON issues (created_at, number);
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY,
    issue_number INTEGER NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    author_association TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS comments_issue ON comments (issue_number, created_at);
CREATE TABLE IF NOT EXISTS embeddings (
    number INTEGER PRIMARY KEY,
    model TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    vector BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# Full-text index over titles and bodies, kept in step with `issues` by triggers.
KEYWORD_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS issues_fts USING fts5(title, body, content='issues', content_rowid='number');
CREATE TRIGGER IF NOT EXISTS issues_ai AFTER INSERT ON issues BEGIN
    INSERT INTO issues_fts (rowid, title, body) VALUES (new.number, new.title, new.body);
END;
CREATE TRIGGER IF NOT EXISTS issues_ad AFTER DELETE ON issues BEGIN
    INSERT INTO issues_fts (issues_fts, rowid, title, body) VALUES ('delete', old.number, old.title, old.body);
END;
CREATE TRIGGER IF NOT EXISTS issues_au AFTER UPDATE ON issues BEGIN
    INSERT INTO issues_fts (issues_fts, rowid, title, body) VALUES ('delete', old.number, old.title, old.body);
    INSERT INTO issues_fts (rowid, title, body) VALUES (new.number, new.title, new.body);
END;
"""

ISSUE_COLUMNS = (
    "number", "title", "body", "state", "state_reason", "labels", "author_association",
    "comments_count", "reactions_total", "html_url", "created_at", "updated_at", "closed_at",
    "assignees", "milestone", "author",
)

# Columns added after indexes were first built; ALTER TABLE adds them to existing index files.
# assignees, milestone, author and reactions are stored now (#15) so the v0.2 digest needs no full resync.
ADDED_ISSUE_COLUMNS = {
    "assignees": "TEXT NOT NULL DEFAULT '[]'",
    "milestone": "TEXT",
    "author": "TEXT",
}


def _issue_row(item: dict) -> tuple:
    return (
        item["number"],
        item["title"],
        item.get("body") or "",
        item["state"],
        item.get("state_reason"),
        json.dumps([label["name"] for label in item.get("labels", [])]),
        item.get("author_association"),
        item.get("comments", 0),
        (item.get("reactions") or {}).get("total_count", 0),
        item["html_url"],
        item["created_at"],
        item["updated_at"],
        item.get("closed_at"),
        json.dumps([a["login"] for a in item.get("assignees") or []]),
        (item.get("milestone") or {}).get("title"),
        (item.get("user") or {}).get("login"),
    )


def _issue_dict(row: sqlite3.Row) -> dict:
    issue = dict(row)
    issue["labels"] = json.loads(issue["labels"])
    issue["assignees"] = json.loads(issue["assignees"])
    return issue


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        existing = {row["name"] for row in self.conn.execute("PRAGMA table_info(issues)")}
        for column, definition in ADDED_ISSUE_COLUMNS.items():
            if column not in existing:
                self.conn.execute(f"ALTER TABLE issues ADD COLUMN {column} {definition}")
        had_keyword_index = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'issues_fts'"
        ).fetchone()
        self.conn.executescript(KEYWORD_SCHEMA)
        if not had_keyword_index:
            self.conn.execute("INSERT INTO issues_fts (issues_fts) VALUES ('rebuild')")
        self.conn.commit()

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def get_state(self, key: str, default: Any = None) -> Any:
        row = self.conn.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def set_state(self, key: str, value: Any) -> None:
        if value is None:
            self.conn.execute("DELETE FROM state WHERE key = ?", (key,))
        else:
            self.conn.execute(
                "INSERT INTO state (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, json.dumps(value)),
            )

    def upsert_issues(self, items: list[dict]) -> int:
        rows = [_issue_row(item) for item in items if "pull_request" not in item]
        columns = ", ".join(ISSUE_COLUMNS)
        marks = ", ".join("?" for _ in ISSUE_COLUMNS)
        updates = ", ".join(f"{c} = excluded.{c}" for c in ISSUE_COLUMNS[1:])
        self.conn.executemany(
            f"INSERT INTO issues ({columns}) VALUES ({marks}) ON CONFLICT(number) DO UPDATE SET {updates}", rows
        )
        return len(rows)

    def upsert_comments(self, items: list[dict]) -> int:
        rows = [
            (
                c["id"],
                int(c["issue_url"].rsplit("/", 1)[1]),
                c.get("body") or "",
                c.get("author_association"),
                c["created_at"],
                c["updated_at"],
            )
            for c in items
        ]
        self.conn.executemany(
            "INSERT INTO comments (id, issue_number, body, author_association, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET body = excluded.body, "
            "author_association = excluded.author_association, updated_at = excluded.updated_at",
            rows,
        )
        return len(rows)

    def issue(self, number: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM issues WHERE number = ?", (number,)).fetchone()
        return _issue_dict(row) if row else None

    def issues(self) -> list[dict]:
        return [_issue_dict(r) for r in self.conn.execute("SELECT * FROM issues ORDER BY created_at, number")]

    def comments_for(self, number: int) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM comments WHERE issue_number = ? ORDER BY created_at, id", (number,))
        return [dict(r) for r in rows]

    def keyword_search(self, query: str, limit: int = 100) -> list[int]:
        """Issue numbers matching any word of the query, best bm25 rank first."""
        words = re.findall(r"\w+", query)
        if not words:
            return []
        match = " OR ".join(f'"{w}"' for w in words)  # quoted words: user text never becomes FTS syntax
        rows = self.conn.execute(
            "SELECT rowid FROM issues_fts WHERE issues_fts MATCH ? ORDER BY bm25(issues_fts) LIMIT ?", (match, limit)
        )
        return [r[0] for r in rows]

    def filter_rows(self) -> list[tuple[int, str, list[str], str]]:
        """Light rows for filtering: number, state, labels (decoded) and created_at."""
        rows = self.conn.execute("SELECT number, state, labels, created_at FROM issues")
        return [(r["number"], r["state"], json.loads(r["labels"]), r["created_at"]) for r in rows]

    def maintainer_replied(self, associations: tuple[str, ...]) -> set[int]:
        marks = ", ".join("?" for _ in associations)
        rows = self.conn.execute(
            f"SELECT DISTINCT issue_number FROM comments WHERE author_association IN ({marks})", associations
        )
        return {r[0] for r in rows}

    def latest_comments(self) -> dict[int, tuple[str | None, str]]:
        """Per issue: (author_association, created_at) of its most recent stored comment."""
        latest: dict[int, tuple[str | None, str]] = {}
        for r in self.conn.execute("SELECT issue_number, author_association, created_at FROM comments ORDER BY created_at, id"):
            latest[r[0]] = (r[1], r[2])
        return latest

    def count_issues(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM issues").fetchone()[0]

    def pending_embeddings(self, model: str, text_for: Callable[[dict], str]) -> list[tuple[int, str, str]]:
        known = {
            r["number"]: r["content_hash"]
            for r in self.conn.execute("SELECT number, content_hash FROM embeddings WHERE model = ?", (model,))
        }
        pending = []
        for row in self.conn.execute("SELECT number, title, body FROM issues ORDER BY number"):
            issue = dict(row)
            text = text_for(issue)
            digest = hashlib.sha256(f"{model}\n{text}".encode()).hexdigest()
            if known.get(issue["number"]) != digest:
                pending.append((issue["number"], text, digest))
        return pending

    def save_embeddings(self, model: str, rows: list[tuple[int, str, np.ndarray]]) -> None:
        self.conn.executemany(
            "INSERT INTO embeddings (number, model, content_hash, vector) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(number) DO UPDATE SET model = excluded.model, content_hash = excluded.content_hash, "
            "vector = excluded.vector",
            [(n, model, h, np.asarray(v, dtype=np.float32).tobytes()) for n, h, v in rows],
        )

    def matrix(self, model: str) -> tuple[np.ndarray, np.ndarray]:
        rows = self.conn.execute(
            "SELECT e.number, e.vector FROM embeddings e JOIN issues i ON i.number = e.number "
            "WHERE e.model = ? ORDER BY i.created_at, i.number",
            (model,),
        ).fetchall()
        if not rows:
            return np.zeros(0, dtype=np.int64), np.zeros((0, 0), dtype=np.float32)
        numbers = np.array([r[0] for r in rows], dtype=np.int64)
        vectors = np.frombuffer(b"".join(r[1] for r in rows), dtype=np.float32).reshape(len(rows), -1)
        return numbers, vectors

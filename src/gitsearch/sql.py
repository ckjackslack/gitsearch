"""Query commit history with (read-only) SQL.

Commits are loaded into an in-memory SQLite database with two tables::

    commits(sha, short_sha, author, email, date, timestamp, day, subject, message,
            parents, is_merge, insertions, deletions, files_changed)
    files(sha, path, insertions, deletions)        -- one row per changed file

Only a single ``SELECT`` (or ``WITH ... SELECT``) statement is allowed: an SQLite
authorizer rejects anything that would write, attach or change pragmas, and a
progress handler aborts queries that run longer than the configured timeout.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass

from .models import Commit

SCHEMA = """
CREATE TABLE commits (
    sha TEXT PRIMARY KEY,
    short_sha TEXT NOT NULL,
    author TEXT NOT NULL,
    email TEXT NOT NULL,
    date TEXT NOT NULL,          -- ISO 8601 author date with offset
    timestamp INTEGER NOT NULL,  -- unix time of the author date
    day TEXT NOT NULL,           -- YYYY-MM-DD in the author's timezone
    subject TEXT NOT NULL,
    message TEXT NOT NULL,
    parents TEXT NOT NULL,       -- space separated parent shas
    is_merge INTEGER NOT NULL,
    insertions INTEGER NOT NULL,
    deletions INTEGER NOT NULL,
    files_changed INTEGER NOT NULL
);
CREATE TABLE files (
    sha TEXT NOT NULL REFERENCES commits(sha),
    path TEXT NOT NULL,
    insertions INTEGER,          -- NULL for binary files
    deletions INTEGER
);
CREATE INDEX files_sha ON files(sha);
CREATE INDEX files_path ON files(path);
"""

TABLES = {
    "commits": [
        "sha", "short_sha", "author", "email", "date", "timestamp", "day", "subject",
        "message", "parents", "is_merge", "insertions", "deletions", "files_changed",
    ],
    "files": ["sha", "path", "insertions", "deletions"],
}

_ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}
# SQLITE_RECURSIVE (33) is not exported by every Python version.
_ALLOWED_ACTIONS.add(getattr(sqlite3, "SQLITE_RECURSIVE", 33))


class QueryError(ValueError):
    """The SQL query was rejected or failed."""


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    truncated: bool = False

    def to_dict(self) -> dict:
        return {
            "columns": self.columns,
            "rows": [list(r) for r in self.rows],
            "truncated": self.truncated,
        }


def build_database(commits: Iterable[Commit]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.executescript(SCHEMA)
    commit_rows, file_rows = [], []
    for c in commits:
        commit_rows.append(
            (
                c.sha, c.short_sha, c.author, c.email, c.date.isoformat(),
                int(c.date.timestamp()), c.date.strftime("%Y-%m-%d"), c.subject,
                c.message, " ".join(c.parents), int(c.is_merge), c.insertions,
                c.deletions, len(c.files),
            )
        )
        file_rows.extend((c.sha, f.path, f.insertions, f.deletions) for f in c.files)
    conn.executemany(f"INSERT INTO commits VALUES ({','.join('?' * 14)})", commit_rows)
    conn.executemany("INSERT INTO files VALUES (?,?,?,?)", file_rows)
    conn.commit()
    return conn


def _authorizer(action, arg1, arg2, dbname, source):
    if action in _ALLOWED_ACTIONS:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def run_query(
    conn: sqlite3.Connection,
    query: str,
    max_rows: int = 1000,
    timeout: float = 5.0,
) -> QueryResult:
    """Run one read-only query against a database made by :func:`build_database`."""
    query = (query or "").strip().rstrip(";").strip()
    if not query:
        raise QueryError("empty query")
    deadline = time.monotonic() + timeout
    conn.set_authorizer(_authorizer)
    conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 10_000)
    try:
        cur = conn.execute(query)
        if cur.description is None:
            raise QueryError("only SELECT queries are allowed")
        columns = [d[0] for d in cur.description]
        rows = cur.fetchmany(max_rows + 1)
    except sqlite3.DatabaseError as exc:
        msg = str(exc)
        if "interrupted" in msg:
            msg = f"query timed out after {timeout:g}s"
        elif "not authorized" in msg:
            msg = "only read-only SELECT queries are allowed"
        raise QueryError(msg) from None
    except sqlite3.Warning as exc:  # e.g. "You can only execute one statement at a time."
        raise QueryError(str(exc)) from None
    except (OverflowError, ValueError) as exc:
        raise QueryError(str(exc)) from None
    finally:
        conn.set_authorizer(None)
        conn.set_progress_handler(None, 0)
    truncated = len(rows) > max_rows
    return QueryResult(columns, [tuple(r) for r in rows[:max_rows]], truncated)


def query_commits(commits: Iterable[Commit], query: str, **kwargs) -> QueryResult:
    """Convenience wrapper: build a throwaway database and run ``query`` on it."""
    conn = build_database(commits)
    try:
        return run_query(conn, query, **kwargs)
    finally:
        conn.close()


class SqlIndex:
    """Keeps one database per history snapshot so repeated queries are cheap."""

    def __init__(self):
        self._source: list[Commit] | None = None
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    def query(self, commits: list[Commit], query: str, **kwargs) -> QueryResult:
        with self._lock:
            if self._conn is None or commits is not self._source:
                if self._conn is not None:
                    self._conn.close()
                self._conn = build_database(commits)
                self._source = commits
            return run_query(self._conn, query, **kwargs)

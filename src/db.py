import sqlite3
from contextlib import contextmanager
from datetime import datetime
from textwrap import dedent
from uuid import uuid4

from src.settings import DB_PATH


AUTH_TOKEN_TABLE_DEF = dedent("""
    CREATE TABLE IF NOT EXISTS auth_token(
        id INTEGER PRIMARY KEY NOT NULL,
        token CHAR(36) UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expired_at TIMESTAMP DEFAULT NULL
    )
""")
AUTH_TOKEN_TABLE_DELETE = r"DELETE FROM auth_token"
AUTH_TOKEN_TABLE_EXPIRE = r"UPDATE auth_token SET expired_at = ? WHERE id = ?"
AUTH_TOKEN_TABLE_INSERT = r"INSERT INTO auth_token (token) VALUES (?)"
AUTH_TOKEN_TABLE_SELECT = r"SELECT * FROM auth_token"
AUTH_TOKEN_TABLE_SELECT_NTH = r"SELECT * FROM auth_token WHERE id = ?"
AUTH_TOKEN_TABLE_SELECT_NTH_CUSTOM = "SELECT token, expired_at FROM auth_token WHERE token = ?"


get_uuid = lambda: str(uuid4())
now = lambda: datetime.now().isoformat()


@contextmanager
def sqlite_connect(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        yield cursor
    finally:
        conn.commit()
        cursor.close()
        conn.close()


class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self._conn = None
        self._cursor = None

    def __enter__(self):
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._cursor = self._conn.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._conn.commit()
        self._cursor.close()
        self._conn.close()

    def query(self, *args, **kwargs):
        self._cursor.execute(*args, **kwargs)

        query = args[0].upper().strip()

        if any(query.startswith(stmt) for stmt in (
            "INSERT", "DELETE", "UPDATE"
        )):
            self._conn.commit()
            return self._cursor.lastrowid
        elif query.startswith("SELECT") and "WHERE" in query:
            return self._cursor.fetchone()
        elif query.startswith("SELECT"):
            return self._cursor.fetchall()


class AuthDb:
    def __init__(self, db):
        self._db = db

    @property
    def db(self):
        return self._db

    def init(self):
        self.db.query(AUTH_TOKEN_TABLE_DEF)

    def new_token(self):
        return self.db.query(AUTH_TOKEN_TABLE_INSERT, [get_uuid()])

    def clear(self):
        return self.db.query(AUTH_TOKEN_TABLE_DELETE)

    def expire(self, _id):
        return self.db.query(AUTH_TOKEN_TABLE_EXPIRE, [now(), _id])

    def all(self):
        yield from self.db.query(AUTH_TOKEN_TABLE_SELECT)

    def get(self, _id):
        return self.db.query(AUTH_TOKEN_TABLE_SELECT_NTH, [_id])

    def get_by_token(self, token):
        return self.db.query(AUTH_TOKEN_TABLE_SELECT_NTH_CUSTOM, [token])

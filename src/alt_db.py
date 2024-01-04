import sqlite3
import threading
import time
from functools import lru_cache, wraps
from queue import Queue


WAIT_TIMEOUT = 1  # 1 second


@lru_cache(maxsize=100)
def cached_query(db, query, params=tuple()):
    return db.execute_read_query(query, params)


def with_retry(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        retries = 3
        while retries:
            try:
                return func(*args, **kwargs)
            except sqlite3.OperationalError:
                retries -= 1
                time.sleep(WAIT_TIMEOUT)
        raise Exception("Database connection failed after retries")
    return wrapper


def thread_safe_operation(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with threading.Lock():
            return func(*args, **kwargs)
    return wrapper


@with_retry
def robust_connection(db_path):
    return sqlite3.connect(db_path)


class SQLiteDB:
    def __init__(self, db_path, pool_size=5):
        self.db_path = db_path
        self.pool = Queue(maxsize=pool_size)
        self.pool_size = pool_size

        self._initialize_db()
        self._populate_connection_pool()

    def _initialize_db(self):
        # set WAL (Write-Ahead Logging) mode
        # allows higher concurrency
        # by letting reads occur concurrently with writes
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            # set busy timeout to 5000 milliseconds
            # handle scenarios where the database is locked
            # this makes db wait before throwing a "database is locked" error
            conn.execute("PRAGMA busy_timeout=5000;")

    def _populate_connection_pool(self):
         for _ in range(self.pool_size):
            self.pool.put(
                sqlite3.connect(self.db_path, check_same_thread=False)
            )

    def get_connection(self):
        return self.pool.get()

    def release_connection(self, connection):
        self.pool.put(connection)

    @thread_safe_operation
    def execute_read_query(self, query, params=tuple()):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()
        finally:
            self.release_connection(conn)
        return results

    @thread_safe_operation
    def execute_write_query(self, thing, method=None, **kwargs):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if method is not None and hasattr(cursor, method):
                fn = getattr(cursor, method)
            else:
                fn = cursor.execute
            fn(thing, **kwargs)
            conn.commit()
            cursor.close()
        finally:
            self.release_connection(conn)


class Database(SQLiteDB):
    def get_table_names(self):
        query = "SELECT name FROM sqlite_master WHERE type='table'"
        return [t[0] for t in self.execute_read_query(query)]

    def clear_all_tables(self):
        for table_name in self.get_table_names():
            query = f"DELETE FROM {table_name}"
            self.execute_write_query(query)

    def display_rows(self, table_name):
        query = f"SELECT * FROM {table_name}"
        for row in self.execute_read_query(query):
            print(row)

    def setup(self, filepath):
        with open(filepath) as f:
            self.execute_write_query(f.read(), method="executescript")


def init_db(db_path, init_script_path=None):
    db = Database(db_path)
    db.clear_all_tables()
    if init_script_path is not None:
        db.setup(init_script_path)
    return db

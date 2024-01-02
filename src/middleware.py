import sqlite3
from datetime import datetime

import falcon

from src.db import AuthDb, Database
from src.settings import CUSTOM_AUTH_HEADER, DATE_FMT


class AuthMiddleware:
    def __init__(self, db_path):
        self.db_path = db_path

    def process_request(self, req, resp):
        token = req.get_header(CUSTOM_AUTH_HEADER)
        if token is None:
            raise falcon.HTTPForbidden(description="Access denied")

        if not self._validate_token(token):
            raise falcon.HTTPForbidden(description="Invalid or expired token")

    def is_invalid(self, expired_at):
        return datetime.strptime(expired_at, DATE_FMT) < datetime.now()

    def _validate_token(self, token):
        try:
            with Database(self.db_path) as db:
                auth_db = AuthDb(db)
                row = auth_db.get_by_token(token)
                if row:
                    _, expired_at = row
                    if expired_at and self.is_invalid(expired_at):
                        return False
                    return True
        except sqlite3.Error as e:
            print("Database error:", e)
        return False

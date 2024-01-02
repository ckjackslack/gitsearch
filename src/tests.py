from unittest import TestCase

from src.db import AuthDb, Database
from src.settings import DB_PATH
from src.utils import add_prefix_to_filename


class AuthDbTestCase(TestCase):
    def _cast_test(self, obj, _type):
        try:
            _type(obj)
        except (TypeError, ValueError):
            self.fail(f"Cannot cast into {_type!r}!")

    def test_auth_db(self):
        test_db_path = add_prefix_to_filename(DB_PATH, "test_")

        # TODO: mock database object
        with Database(test_db_path) as db:
            auth_db = AuthDb(db)
            auth_db.init()

            _id = 1

            self.assertEqual(auth_db.new_token(), 1)

            rows = list(auth_db.all())
            self.assertEqual(len(rows), 1)

            self._cast_test(rows[0], dict)

            self.assertEqual(auth_db.expire(_id), 1)

            first_row = auth_db.get(_id)
            self._cast_test(first_row, tuple)
            token = first_row[1]

            row = auth_db.get_by_token(token)
            self._cast_test(row, tuple)

            self.assertEqual(auth_db.clear(), 1)


if __name__ == "__main__":
    unittest.main()
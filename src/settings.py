import os


AVAILABLE_FIELDS = ("author", "since", "until")
BASE_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
    )
)
BRANCH_NAME = "master"
CUSTOM_AUTH_HEADER = "X-Auth-Token"
DATE_FMT = "%Y-%m-%dT%H:%M:%S.%f"
DB_FILE = "database.db"
DB_PATH = os.path.abspath(
    os.path.join(BASE_PATH, DB_FILE)
)
DEFAULT_PAGE = 1
NOT_FOUND = "unknown"
PAGE_SIZE = 10
REPO_PATH = "/home/ckjackslack/Projects/aoc2023"
STATIC_PATH = os.path.join(BASE_PATH, "static")
TEMPLATE_PATH = os.path.join(BASE_PATH, "templates")
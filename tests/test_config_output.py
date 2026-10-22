import pytest

from conftest import make_commit
from gitsearch.config import Config, ConfigError
from gitsearch.models import FileChange
from gitsearch.output import commit_details, commit_line, groups_text, page_text, table_text
from gitsearch.search import paginate


def test_config_defaults():
    cfg = Config.from_env({})
    assert cfg.repo == "." and cfg.ref == "HEAD" and cfg.token is None and cfg.port == 8000


def test_config_env_then_overrides():
    env = {"GITSEARCH_REPO": "/r", "GITSEARCH_REF": "dev", "GITSEARCH_PORT": "9000",
           "GITSEARCH_TOKEN": "", "GITSEARCH_SQL_TIMEOUT": "1.5"}
    cfg = Config.from_env(env, ref="main", port=None)
    assert (cfg.repo, cfg.ref, cfg.port, cfg.token, cfg.sql_timeout) == ("/r", "main", 9000, None, 1.5)


@pytest.mark.parametrize(
    "env,overrides",
    [({"GITSEARCH_PORT": "http"}, {}), ({}, {"port": 0}), ({}, {"max_commits": 0}),
     ({}, {"sql_timeout": -1}), ({"GITSEARCH_SQL_MAX_ROWS": "0"}, {})],
)
def test_config_invalid(env, overrides):
    with pytest.raises(ConfigError):
        Config.from_env(env, **overrides)


def test_commit_line_and_details():
    c = make_commit(message="A very long subject " * 5 + "\n\nbody",
                    files=(FileChange("a.py", 10, 2), FileChange("b.bin", None, None)))
    line = commit_line(c)
    assert line.startswith("aaaaaaa  2024-01-01  Alice") and line.endswith("+10/-2")
    assert len(line) <= 72 and "…" in line
    details = commit_details(c)
    assert "Author: Alice <alice@example.com>" in details
    assert "    body" in details and "b.bin  (binary)" in details
    assert "2 file(s), +10 -2" in details


def test_page_and_groups_text(commits):
    assert page_text(paginate([], 1, 5)) == "No commits found."
    text = page_text(paginate(commits, 2, 5))
    assert text.endswith("-- page 2/3, 12 matching commit(s)")
    assert groups_text([]) == "No commits found."
    assert groups_text([("Alice", [1, 2]), ("Bo", [1])]) == "Alice       2\nBo          1"


def test_table_text():
    out = table_text(["a", "long_name"], [(1, None), ("x\ny", 2.5)])
    assert out.splitlines() == [
        "a    long_name",
        "---  ---------",
        "1    NULL",
        "x y  2.5",
        "(2 rows)",
    ]
    assert table_text(["n"], [(1,)]).endswith("(1 row)")

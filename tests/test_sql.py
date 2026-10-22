import pytest

from gitsearch.sql import QueryError, SqlIndex, build_database, query_commits, run_query


def test_commits_table(commits):
    r = query_commits(commits, "SELECT COUNT(*), SUM(is_merge) FROM commits")
    assert r.columns == ["COUNT(*)", "SUM(is_merge)"]
    assert r.rows == [(12, 1)]


def test_group_by_and_order(commits):
    r = query_commits(
        commits,
        "SELECT author, COUNT(*) AS n FROM commits GROUP BY author ORDER BY author",
    )
    assert r.rows == [("Alice", 4), ("Bob", 4), ("alice", 4)]


def test_join_files_and_null_for_binary(commits):
    r = query_commits(
        commits,
        "SELECT c.short_sha, f.insertions FROM commits c JOIN files f ON f.sha = c.sha "
        "WHERE f.path LIKE '%.png' ORDER BY c.timestamp DESC",
    )
    assert len(r.rows) == 3 and all(ins is None for _, ins in r.rows)


def test_day_column_and_cte(commits):
    r = query_commits(
        commits,
        "WITH x AS (SELECT day FROM commits WHERE day >= '2024-02-20') SELECT * FROM x;",
    )
    assert r.rows == [("2024-03-01",), ("2024-02-25",), ("2024-02-20",)]


def test_max_rows_truncates(commits):
    r = query_commits(commits, "SELECT sha FROM commits", max_rows=5)
    assert len(r.rows) == 5 and r.truncated
    assert r.to_dict()["truncated"] is True


@pytest.mark.parametrize(
    "query",
    [
        "DELETE FROM commits",
        "UPDATE commits SET author = 'x'",
        "INSERT INTO files VALUES ('a','b',1,1)",
        "DROP TABLE commits",
        "CREATE TABLE t(x)",
        "PRAGMA table_info(commits)",
        "ATTACH DATABASE 'evil.db' AS evil",
    ],
)
def test_writes_and_side_effects_rejected(commits, query, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    conn = build_database(commits)
    with pytest.raises(QueryError, match="read-only"):
        run_query(conn, query)
    assert run_query(conn, "SELECT COUNT(*) FROM commits").rows == [(12,)]
    assert not (tmp_path / "evil.db").exists()


@pytest.mark.parametrize("query", ["", "   ", ";", "SELEC 1", "SELECT 1; SELECT 2", "SELECT nope FROM commits"])
def test_bad_queries(commits, query):
    with pytest.raises(QueryError):
        query_commits(commits, query)


def test_runaway_query_times_out(commits):
    q = "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT max(x) FROM c"
    with pytest.raises(QueryError, match="timed out"):
        query_commits(commits, q, timeout=0.2)


def test_authorizer_removed_after_query(commits):
    conn = build_database(commits)
    run_query(conn, "SELECT 1")
    conn.execute("CREATE TABLE scratch(x)")  # would be denied if the authorizer leaked


def test_sql_index_rebuilds_only_for_new_history(commits):
    idx = SqlIndex()
    assert idx.query(commits, "SELECT COUNT(*) FROM commits").rows == [(12,)]
    first_conn = idx._conn
    idx.query(commits, "SELECT 1")
    assert idx._conn is first_conn
    assert idx.query(commits[:3], "SELECT COUNT(*) FROM commits").rows == [(3,)]
    assert idx._conn is not first_conn

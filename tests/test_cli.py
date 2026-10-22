import json
import io

import pytest

from gitsearch.cli import main


@pytest.fixture
def run(sample_repo, capsys):
    def _run(*args, repo=True):
        argv = list(args)
        if repo:
            argv[1:1] = ["-C", str(sample_repo.path)]
        code = main(argv)
        out, err = capsys.readouterr()
        return code, out, err

    return _run


def test_help_and_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "Search and query the commit history" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["--version"])
    assert capsys.readouterr().out.startswith("gitsearch ")


def test_no_command_is_usage_error(capsys):
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_log_default(run):
    code, out, _ = run("log")
    assert code == 0
    lines = out.splitlines()
    assert "Merge branch 'feature'" in lines[0]
    assert lines[-1] == "-- page 1/1, 5 matching commit(s)"


def test_log_filters(run):
    code, out, _ = run("log", "--author", "alice", "--merges", "no")
    assert "Fix parser bug" in out and "Initial commit" in out and "Merge" not in out
    _, out, _ = run("log", "-q", "TOKENIZER")
    assert "Add parser" in out and "1 matching" in out
    _, out, _ = run("log", "--path", "zażółć")
    assert "Feature work" in out
    _, out, _ = run("log", "--since", "2024-02-01", "--until", "2024-02-10")
    assert "Fix parser bug" in out and "Feature work" in out and "2 matching" in out
    _, out, _ = run("log", "--author", "nobody")
    assert out.strip() == "No commits found."


def test_log_paging_and_all(run):
    _, out, _ = run("log", "-n", "2", "--page", "3")
    assert "Initial commit" in out and out.strip().endswith("page 3/3, 5 matching commit(s)")
    _, out, _ = run("log", "--all", "-n", "1")
    assert out.count("\n") == 6


def test_log_group_by(run):
    _, out, _ = run("log", "--group-by", "author")
    assert out.splitlines()[0].split() == ["Alice", "Smith", "3"]
    _, out, _ = run("log", "-g", "month", "--json")
    assert json.loads(out) == [{"key": "2024-02", "count": 3}, {"key": "2024-01", "count": 2}]


def test_log_json(run):
    _, out, _ = run("log", "--json", "-n", "1")
    data = json.loads(out)
    assert data["total"] == 5 and data["pages"] == 5
    assert data["commits"][0]["is_merge"] is True


def test_show(run, sample_repo):
    sha = sample_repo.git("rev-parse", "main~1")
    code, out, _ = run("show", sha[:8])
    assert code == 0 and out.startswith(f"commit {sha}") and "data.bin  (binary)" in out
    _, out, _ = run("show", sha[:8], "--json")
    assert json.loads(out)["sha"] == sha
    code, _, err = run("show", "deadbeef")
    assert code == 1 and "no commit matching" in err


def test_sql(run):
    code, out, _ = run("sql", "SELECT author, COUNT(*) AS n FROM commits GROUP BY author ORDER BY n DESC, author")
    assert code == 0
    assert out.splitlines()[2].split() == ["Alice", "Smith", "3"]
    assert out.strip().endswith("(3 rows)")
    _, out, _ = run("sql", "--json", "SELECT path FROM files WHERE insertions IS NULL")
    assert json.loads(out)["rows"] == [["data.bin"]]
    _, out, _ = run("sql", "--max-rows", "2", "SELECT sha FROM commits")
    assert "(truncated to 2 rows)" in out


def test_sql_from_stdin(run, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("SELECT COUNT(*) AS n FROM commits;\n"))
    _, out, _ = run("sql", "-")
    assert out.splitlines()[2] == "5"


def test_schema(run):
    _, out, _ = run("schema", repo=False)
    assert out.startswith("commits(sha, short_sha,") and "files(sha, path" in out


@pytest.mark.parametrize(
    "args,code,msg",
    [
        (["log", "--since", "01/02/2024"], 2, "YYYY-MM-DD"),
        (["sql", "DROP TABLE commits"], 2, "read-only"),
        (["show", "xyz"], 2, "hex"),
        (["log", "-r", "nope"], 1, "unknown revision"),
    ],
)
def test_errors(run, args, code, msg):
    rc, _, err = run(*args)
    assert rc == code and msg in err and "Traceback" not in err


def test_bad_repo_path(tmp_path, capsys):
    assert main(["log", "-C", str(tmp_path)]) == 1
    assert "not a git repository" in capsys.readouterr().err


def test_env_repo_and_bad_env(sample_repo, monkeypatch, capsys):
    monkeypatch.setenv("GITSEARCH_REPO", str(sample_repo.path))
    monkeypatch.setenv("GITSEARCH_REF", "feature")
    assert main(["log"]) == 0
    assert "3 matching" in capsys.readouterr().out
    monkeypatch.setenv("GITSEARCH_MAX_COMMITS", "lots")
    assert main(["log"]) == 2
    assert "GITSEARCH_MAX_COMMITS" in capsys.readouterr().err


@pytest.mark.parametrize("bad", [["log", "--page", "0"], ["log", "-n", "x"], ["log", "-g", "colour"]])
def test_argparse_validation(bad, capsys):
    with pytest.raises(SystemExit) as exc:
        main(bad)
    assert exc.value.code == 2

import pytest
from falcon import testing

from gitsearch.config import Config
from gitsearch.repo import CommitStore, GitRepository
from gitsearch.web import create_app, create_app_from_env


@pytest.fixture
def store(sample_repo):
    return CommitStore(GitRepository(str(sample_repo.path)), "main")


@pytest.fixture
def client(store):
    return testing.TestClient(create_app(store, Config()))


def test_index_and_static(client):
    r = client.simulate_get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert '<div class="container">' in r.text and "/static/app.js" in r.text
    for path in ("/static/app.js", "/static/main.css", "/static/libs/vue.min.js", "/static/libs/bulma.min.css"):
        assert client.simulate_get(path).status_code == 200, path
    assert client.simulate_get("/static/nope.js").status_code == 404
    assert client.simulate_get("/static/../app.py").status_code == 404


def test_info(client, store):
    data = client.simulate_get("/api/info").json
    assert data["commits"] == 5 and data["ref"] == "main" and data["auth"] is False
    assert data["head"] == store.head and "commits" in data["tables"]


def test_commits_paginated(client):
    data = client.simulate_get("/api/commits", params={"per_page": 2, "page": 2}).json
    assert data["total"] == 5 and data["pages"] == 3 and data["page"] == 2
    assert [c["subject"] for c in data["commits"]] == ["Fix parser bug", "Add parser"]


def test_commits_filters(client):
    data = client.simulate_get("/api/commits", params={"author": "bob"}).json
    assert [c["subject"] for c in data["commits"]] == ["Add parser"]
    data = client.simulate_get("/api/commits", params={"q": "parser", "merges": "no"}).json
    assert data["total"] == 2
    data = client.simulate_get("/api/commits", params={"since": "2024-02-04", "until": ""}).json
    assert data["total"] == 2
    data = client.simulate_get("/api/commits", params={"path": "data.bin"}).json
    assert data["commits"][0]["files"][0] == {"path": "data.bin", "insertions": None, "deletions": None}


def test_commits_group_by(client):
    data = client.simulate_get("/api/commits", params={"group_by": "author"}).json
    assert data["total"] == 5
    assert data["groups"][0] == {"key": "Alice Smith", "count": 3, "insertions": 4, "deletions": 1}


@pytest.mark.parametrize(
    "params",
    [{"page": "x"}, {"page": "0"}, {"per_page": "1000"}, {"since": "nope"},
     {"group_by": "colour"}, {"merges": "maybe"}],
)
def test_commits_bad_params_are_400(client, params):
    r = client.simulate_get("/api/commits", params=params)
    assert r.status_code == 400 and r.json["description"]


def test_single_commit(client, sample_repo):
    sha = sample_repo.git("rev-parse", "feature")
    r = client.simulate_get(f"/api/commits/{sha[:6]}")
    assert r.status_code == 200 and r.json["author"] == "Carol"
    assert client.simulate_get("/api/commits/ffffff").status_code == 404
    assert client.simulate_get("/api/commits/zz").status_code == 400


def test_sql_get_and_post(client):
    r = client.simulate_get("/api/sql", params={"q": "SELECT COUNT(*) AS n FROM commits"})
    assert r.json == {"columns": ["n"], "rows": [[5]], "truncated": False}
    r = client.simulate_post("/api/sql", json={"query": "SELECT day FROM commits WHERE is_merge"})
    assert r.json["rows"] == [["2024-02-20"]]


@pytest.mark.parametrize(
    "kwargs",
    [{"json": {"query": "DELETE FROM commits"}}, {"json": {"query": ""}}, {"json": ["x"]},
     {"body": "not json", "headers": {"Content-Type": "application/json"}}, {}],
)
def test_sql_bad_requests(client, kwargs):
    r = client.simulate_post("/api/sql", **kwargs)
    assert r.status_code == 400


def test_sql_row_limit_from_config(store):
    client = testing.TestClient(create_app(store, Config(sql_max_rows=2)))
    r = client.simulate_get("/api/sql", params={"q": "SELECT sha FROM commits"})
    assert len(r.json["rows"]) == 2 and r.json["truncated"] is True


def test_token_auth(store):
    client = testing.TestClient(create_app(store, Config(token="s3cret")))
    assert client.simulate_get("/").status_code == 200  # UI shell stays public
    assert client.simulate_get("/static/app.js").status_code == 200
    assert client.simulate_get("/api/info").status_code == 401
    assert client.simulate_get("/api/info", headers={"X-Auth-Token": "wrong"}).status_code == 401
    assert client.simulate_get("/api/info", headers={"X-Auth-Token": "s3cret"}).json["auth"] is True
    r = client.simulate_get("/api/commits", headers={"Authorization": "Bearer s3cret"})
    assert r.status_code == 200


def test_git_error_is_503(sample_repo):
    store = CommitStore(GitRepository(str(sample_repo.path)), "no-such-branch")
    client = testing.TestClient(create_app(store))
    r = client.simulate_get("/api/commits")
    assert r.status_code == 503 and "unknown revision" in r.json["description"]


def test_app_from_env(sample_repo, monkeypatch):
    monkeypatch.setenv("GITSEARCH_REPO", str(sample_repo.path))
    monkeypatch.setenv("GITSEARCH_REF", "feature")
    client = testing.TestClient(create_app_from_env())
    assert client.simulate_get("/api/info").json["commits"] == 3

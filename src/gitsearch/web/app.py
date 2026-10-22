"""HTTP layer. Thin: parse parameters, call the pure core, serialise.

Endpoints::

    GET  /                    web UI
    GET  /static/...          UI assets
    GET  /api/info            repository, ref, head sha, number of commits
    GET  /api/commits         search: author, since, until, q, path, merges,
                              page, per_page, group_by
    GET  /api/commits/{sha}   one commit (sha prefix >= 4 chars)
    GET  /api/sql?q=...       read-only SQL over the history
    POST /api/sql             same, JSON body {"query": "..."}
"""

from __future__ import annotations

import hmac
from pathlib import Path

import falcon

from ..config import Config
from ..repo import CommitStore, GitError, GitRepository
from ..search import CommitFilter, SearchError, filter_commits, find_commit, group_commits, paginate
from ..sql import TABLES, QueryError, SqlIndex

STATIC_DIR = Path(__file__).parent / "static"
AUTH_HEADER = "X-Auth-Token"
MAX_PER_PAGE = 100


class TokenAuth:
    """Optional shared-token auth for /api/* (the UI shell itself stays public)."""

    def __init__(self, token: str):
        self.token = token

    def process_request(self, req, resp):
        if not req.path.startswith("/api/"):
            return
        given = req.get_header(AUTH_HEADER)
        auth = req.get_header("Authorization") or ""
        if given is None and auth.lower().startswith("bearer "):
            given = auth[7:].strip()
        if not given or not hmac.compare_digest(given.encode(), self.token.encode()):
            raise falcon.HTTPUnauthorized(
                title="Unauthorized",
                description=f"missing or invalid {AUTH_HEADER} header",
            )


class InfoResource:
    def __init__(self, store: CommitStore, auth_required: bool):
        self.store = store
        self.auth_required = auth_required

    def on_get(self, req, resp):
        commits = self.store.commits()
        resp.media = {
            "repo": self.store.repo.path,
            "ref": self.store.ref,
            "head": self.store.head,
            "commits": len(commits),
            "auth": self.auth_required,
            "group_keys": ["author", "email", "day", "month", "year"],
            "tables": TABLES,
        }


class CommitsResource:
    def __init__(self, store: CommitStore):
        self.store = store

    def on_get(self, req, resp):
        params = {k: req.get_param(k) for k in ("author", "since", "until", "q", "path", "merges")}
        flt = CommitFilter.from_params(params)
        matching = filter_commits(self.store.commits(), flt)

        group_by = req.get_param("group_by")
        if group_by:
            groups = group_commits(matching, group_by)
            resp.media = {
                "group_by": group_by,
                "total": len(matching),
                "groups": [
                    {
                        "key": key,
                        "count": len(items),
                        "insertions": sum(c.insertions for c in items),
                        "deletions": sum(c.deletions for c in items),
                    }
                    for key, items in groups
                ],
            }
            return

        page_no = req.get_param_as_int("page", min_value=1, default=1)
        per_page = req.get_param_as_int("per_page", min_value=1, max_value=MAX_PER_PAGE, default=10)
        page = paginate(matching, page_no, per_page)
        resp.media = {
            "total": page.total,
            "page": page.page,
            "per_page": page.per_page,
            "pages": page.pages,
            "commits": [c.to_dict() for c in page.items],
        }


class CommitResource:
    def __init__(self, store: CommitStore):
        self.store = store

    def on_get(self, req, resp, sha):
        commit = find_commit(self.store.commits(), sha)
        if commit is None:
            raise falcon.HTTPNotFound(description=f"no commit matching {sha!r}")
        resp.media = commit.to_dict()


class SqlResource:
    def __init__(self, store: CommitStore, config: Config):
        self.store = store
        self.config = config
        self.index = SqlIndex()

    def _run(self, resp, query):
        if not query or not str(query).strip():
            raise falcon.HTTPBadRequest(description="missing query")
        result = self.index.query(
            self.store.commits(),
            str(query),
            max_rows=self.config.sql_max_rows,
            timeout=self.config.sql_timeout,
        )
        resp.media = result.to_dict()

    def on_get(self, req, resp):
        self._run(resp, req.get_param("q"))

    def on_post(self, req, resp):
        body = req.get_media(default_when_empty=None)
        if not isinstance(body, dict):
            raise falcon.HTTPBadRequest(description='expected JSON body {"query": "..."}')
        self._run(resp, body.get("query"))


class IndexResource:
    def on_get(self, req, resp):
        resp.content_type = falcon.MEDIA_HTML
        resp.text = (STATIC_DIR / "index.html").read_text(encoding="utf-8")


def _bad_request(req, resp, ex, params):
    raise falcon.HTTPBadRequest(description=str(ex))


def _git_error(req, resp, ex, params):
    raise falcon.HTTPServiceUnavailable(title="Git error", description=str(ex))


def create_app(store: CommitStore, config: Config | None = None) -> falcon.App:
    config = config or Config()
    middleware = [TokenAuth(config.token)] if config.token else []
    app = falcon.App(middleware=middleware)
    app.add_error_handler(SearchError, _bad_request)
    app.add_error_handler(QueryError, _bad_request)
    app.add_error_handler(GitError, _git_error)

    app.add_route("/", IndexResource())
    app.add_static_route("/static", str(STATIC_DIR))
    app.add_route("/api/info", InfoResource(store, bool(config.token)))
    app.add_route("/api/commits", CommitsResource(store))
    app.add_route("/api/commits/{sha}", CommitResource(store))
    app.add_route("/api/sql", SqlResource(store, config))
    return app


def create_app_from_env() -> falcon.App:
    """App factory for external WSGI servers, configured via ``GITSEARCH_*`` env vars.

    e.g. ``GITSEARCH_REPO=/path/to/repo gunicorn 'gitsearch.web:create_app_from_env()'``
    """
    config = Config.from_env()
    store = CommitStore(GitRepository(config.repo), config.ref, config.max_commits)
    return create_app(store, config)

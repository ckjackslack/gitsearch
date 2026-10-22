"""Command line interface: ``gitsearch {log,show,sql,schema,serve}``."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from . import __version__
from .config import Config, ConfigError
from .output import commit_details, groups_text, page_text, table_text
from .repo import CommitStore, GitError, GitRepository
from .search import (
    GROUP_KEYS,
    CommitFilter,
    SearchError,
    filter_commits,
    find_commit,
    group_commits,
    paginate,
)
from .sql import TABLES, QueryError, query_commits

EPILOG = """\
examples:
  gitsearch log --author alice --since 2024-01-01 -q fix
  gitsearch log --group-by month
  gitsearch show 2ef7a4b
  gitsearch sql "SELECT author, COUNT(*) FROM commits GROUP BY author"
  gitsearch serve --repo ~/src/project --port 8000

environment: GITSEARCH_REPO, GITSEARCH_REF, GITSEARCH_MAX_COMMITS, GITSEARCH_TOKEN,
GITSEARCH_HOST, GITSEARCH_PORT, GITSEARCH_SQL_TIMEOUT, GITSEARCH_SQL_MAX_ROWS
(command line options take precedence)."""


def _positive_int(value: str) -> int:
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {value!r}") from None
    if n < 1:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {value!r}")
    return n


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    g = common.add_argument_group("repository")
    g.add_argument("-C", "--repo", help="path to the git repository (default: current dir)")
    g.add_argument("-r", "--ref", help="branch, tag or commit to read history from (default: HEAD)")
    g.add_argument("--max-commits", type=_positive_int, metavar="N",
                   help="only load the newest N commits")

    parser = argparse.ArgumentParser(
        prog="gitsearch",
        description="Search and query the commit history of a local git repository.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    p = sub.add_parser("log", parents=[common], aliases=["search"],
                       help="search commits by author, date, message, path")
    p.add_argument("-a", "--author", help="substring of author name or email")
    p.add_argument("--since", metavar="YYYY-MM-DD", help="commits on or after this day")
    p.add_argument("--until", metavar="YYYY-MM-DD", help="commits on or before this day")
    p.add_argument("-q", "--grep", dest="q", metavar="TEXT",
                   help="substring of the commit message, or a sha prefix")
    p.add_argument("-p", "--path", help="substring of a changed file path")
    p.add_argument("--merges", choices=["any", "only", "no"], default="any",
                   help="include merge commits (any), only merges, or no merges")
    p.add_argument("-g", "--group-by", choices=list(GROUP_KEYS),
                   help="print commit counts per group instead of commits")
    p.add_argument("--page", type=_positive_int, default=1)
    p.add_argument("-n", "--per-page", type=_positive_int, default=20)
    p.add_argument("--all", action="store_true", help="print all matches (no paging)")
    p.add_argument("--json", action="store_true", help="output JSON")
    p.set_defaults(func=cmd_log)

    p = sub.add_parser("show", parents=[common], help="show one commit by sha prefix")
    p.add_argument("sha", help="commit sha or unique prefix (>= 4 chars)")
    p.add_argument("--json", action="store_true", help="output JSON")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("sql", parents=[common], help="run a read-only SQL query over the history")
    p.add_argument("query", help='SELECT statement, or "-" to read it from stdin')
    p.add_argument("--max-rows", type=_positive_int, help="row limit (default 1000)")
    p.add_argument("--timeout", type=float, help="query time limit in seconds (default 5)")
    p.add_argument("--json", action="store_true", help="output JSON")
    p.set_defaults(func=cmd_sql)

    p = sub.add_parser("schema", help="print the tables available to `gitsearch sql`")
    p.set_defaults(func=cmd_schema)

    p = sub.add_parser("serve", parents=[common], help="run the web UI and JSON API")
    p.add_argument("--host", help="interface to bind (default 127.0.0.1)")
    p.add_argument("--port", type=int, help="port (default 8000)")
    p.add_argument("--token", help="require this token in the X-Auth-Token header for /api/*")
    p.set_defaults(func=cmd_serve)
    return parser


def _config(args: argparse.Namespace, **extra) -> Config:
    return Config.from_env(
        repo=getattr(args, "repo", None),
        ref=getattr(args, "ref", None),
        max_commits=getattr(args, "max_commits", None),
        **extra,
    )


def _store(cfg: Config) -> CommitStore:
    return CommitStore(GitRepository(cfg.repo), cfg.ref, cfg.max_commits)


def _print_json(data) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_log(args) -> int:
    cfg = _config(args)
    flt = CommitFilter.from_params(
        {"author": args.author, "since": args.since, "until": args.until,
         "q": args.q, "path": args.path, "merges": args.merges}
    )
    matching = filter_commits(_store(cfg).commits(), flt)
    if args.group_by:
        groups = group_commits(matching, args.group_by)
        if args.json:
            _print_json([{"key": k, "count": len(v)} for k, v in groups])
        else:
            print(groups_text(groups))
        return 0
    per_page = max(1, len(matching)) if args.all else args.per_page
    page = paginate(matching, 1 if args.all else args.page, per_page)
    if args.json:
        _print_json({"total": page.total, "page": page.page, "pages": page.pages,
                     "commits": [c.to_dict() for c in page.items]})
    else:
        print(page_text(page))
    return 0


def cmd_show(args) -> int:
    commit = find_commit(_store(_config(args)).commits(), args.sha)
    if commit is None:
        print(f"gitsearch: no commit matching {args.sha!r}", file=sys.stderr)
        return 1
    if args.json:
        _print_json(commit.to_dict())
    else:
        print(commit_details(commit))
    return 0


def cmd_sql(args) -> int:
    cfg = _config(args, sql_max_rows=args.max_rows, sql_timeout=args.timeout)
    query = sys.stdin.read() if args.query == "-" else args.query
    result = query_commits(_store(cfg).commits(), query,
                           max_rows=cfg.sql_max_rows, timeout=cfg.sql_timeout)
    if args.json:
        _print_json(result.to_dict())
    else:
        print(table_text(result.columns, result.rows))
        if result.truncated:
            print(f"(truncated to {cfg.sql_max_rows} rows)")
    return 0


def cmd_schema(args) -> int:
    for name, cols in TABLES.items():
        print(f"{name}({', '.join(cols)})")
    return 0


def cmd_serve(args) -> int:  # pragma: no cover - blocking network server
    from wsgiref.simple_server import WSGIRequestHandler, make_server

    from .web import create_app

    cfg = _config(args, host=args.host, port=args.port, token=args.token)
    store = _store(cfg)
    commits = store.commits()  # fail fast on a bad repo / ref
    app = create_app(store, cfg)

    class QuietHandler(WSGIRequestHandler):
        def log_message(self, fmt, *a):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % a))

    try:
        server = make_server(cfg.host, cfg.port, app, handler_class=QuietHandler)
    except OSError as exc:
        print(f"gitsearch: cannot listen on {cfg.host}:{cfg.port}: {exc.strerror}", file=sys.stderr)
        return 1
    auth = " (token required for /api)" if cfg.token else ""
    print(f"Serving {store.repo.path} @ {cfg.ref} ({len(commits)} commits) "
          f"on http://{cfg.host}:{cfg.port}/{auth}  - Ctrl+C to stop", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (SearchError, QueryError, ConfigError) as exc:
        print(f"gitsearch: error: {exc}", file=sys.stderr)
        return 2
    except GitError as exc:
        print(f"gitsearch: git error: {exc}", file=sys.stderr)
        return 1
    except BrokenPipeError:  # e.g. `gitsearch log --all | head`
        return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

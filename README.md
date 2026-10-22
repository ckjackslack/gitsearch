# gitsearch

Search and query the commit history of a local git repository from the command line,
a JSON API or a small web UI.

- **Search** commits by author/email, date range, message text or sha prefix, changed
  file path, merge/non-merge; page through results or group them by author, email,
  day, month or year.
- **Query with SQL**: the history is loaded into an in-memory SQLite database
  (`commits` and `files` tables) and you can run any read-only `SELECT` against it.
- **Web UI** (Vue 2 + Bulma, no build step) with a Search tab and an SQL tab, backed by
  a Falcon JSON API with optional token auth.

This started as a 2024 prototype (Falcon + GitPython + a pyparsing SQL grammar) with a
hard-coded repository path; it has been rebuilt as an installable package. See the git
history for the original.

## Install

Requires Python >= 3.10 and the `git` executable on `PATH`.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'     # or: pip install .
```

The only runtime dependency is [Falcon](https://falcon.readthedocs.io/) (used by the web
server). Tested with Falcon 4.4 on Python 3.13.

## Usage

```
gitsearch [--version] COMMAND ...

  log (search)  search commits by author, date, message, path
  show          show one commit by sha prefix
  sql           run a read-only SQL query over the history
  schema        print the tables available to `gitsearch sql`
  serve         run the web UI and JSON API
```

Every command that reads history takes `-C/--repo PATH` (default: current directory),
`-r/--ref REF` (branch, tag or commit; default `HEAD`) and `--max-commits N`.
Run `gitsearch COMMAND --help` for all options.

### Searching (examples run against this repository)

```console
$ gitsearch log -r master
e0b6fe7  2024-01-04  ckjackslack         added new stuff  +298/-0
2ef7a4b  2024-01-02  ckjackslack         lot of stuff  +684/-0
-- page 1/1, 2 matching commit(s)

$ gitsearch log -g day
2026-10-22       3
2024-01-04       1
2024-01-02       1

$ gitsearch show 2ef7a4b
commit 2ef7a4b0e19f3662a8c6de8f0fe42d77ff3beae3
Author: ckjackslack <ckjackslack@gmail.com>
Date:   2024-01-02T23:59:25+01:00

    lot of stuff

  .gitignore  +3 -0
  requirements.txt  +8 -0
  ...
```

Filters (all optional, combined with AND, case-insensitive):

| option | matches |
|---|---|
| `-a/--author TEXT` | substring of author name or email |
| `--since YYYY-MM-DD`, `--until YYYY-MM-DD` | author date, inclusive, in the commit's own timezone |
| `-q/--grep TEXT` | substring of the full commit message, or a sha prefix |
| `-p/--path TEXT` | substring of any changed file path |
| `--merges any\|only\|no` | merge commits |

Output: `--page N`, `-n/--per-page N` (default 20), `--all`, `-g/--group-by
author|email|day|month|year`, `--json`.

### SQL

```console
$ gitsearch schema
commits(sha, short_sha, author, email, date, timestamp, day, subject, message, parents, is_merge, insertions, deletions, files_changed)
files(sha, path, insertions, deletions)

$ gitsearch sql -r master "SELECT c.short_sha, f.path, f.insertions FROM commits c JOIN files f ON f.sha = c.sha WHERE f.path LIKE 'src/%' ORDER BY f.insertions DESC LIMIT 3"
short_sha  path               insertions
---------  -----------------  ----------
e0b6fe7    src/sql_parser.py  169
e0b6fe7    src/alt_db.py      128
2ef7a4b    src/db.py          102
(3 rows)
```

- `date` is ISO 8601 with offset, `day` is `YYYY-MM-DD` in the author's timezone,
  `timestamp` is unix time; `files.insertions/deletions` are `NULL` for binary files;
  `parents` is a space-separated list.
- Only one `SELECT` / `WITH ... SELECT` statement is accepted. Writes, `PRAGMA`,
  `ATTACH` etc. are rejected by an SQLite authorizer; queries are aborted after
  `--timeout` seconds (default 5) and limited to `--max-rows` rows (default 1000).
- Pass `-` as the query to read it from stdin; `--json` for machine-readable output.

### Web UI and API

```console
$ gitsearch serve --repo ~/src/project --port 8000 [--token SECRET]
Serving /home/me/src/project @ HEAD (1234 commits) on http://127.0.0.1:8000/  - Ctrl+C to stop
```

Open `http://127.0.0.1:8000/`. The history is cached per ref and reloaded automatically
when the ref moves (new commits). Endpoints:

| endpoint | description |
|---|---|
| `GET /api/info` | repo path, ref, head sha, commit count, table schema |
| `GET /api/commits` | params `author`, `since`, `until`, `q`, `path`, `merges`, `page`, `per_page` (<= 100) or `group_by` |
| `GET /api/commits/{sha}` | one commit by sha prefix (>= 4 hex chars) |
| `GET /api/sql?q=...` / `POST /api/sql` `{"query": "..."}` | read-only SQL, returns `{columns, rows, truncated}` |

```console
$ curl -s -H 'X-Auth-Token: s3cret' 'localhost:8765/api/commits?group_by=month'
{"group_by": "month", "total": 3, "groups": [{"key": "2026-10", "count": 1, "insertions": 50, "deletions": 0}, {"key": "2024-01", "count": 2, "insertions": 982, "deletions": 0}]}
```

Bad parameters return `400` with a JSON `description`; git problems return `503`.
With a token configured, `/api/*` requires `X-Auth-Token: <token>` (or
`Authorization: Bearer <token>`); the UI page itself stays public and asks for the token.

The built-in server is the standard-library `wsgiref` server, fine for local use. For
anything else, use a real WSGI server with the env-configured factory, e.g.:

```bash
GITSEARCH_REPO=/path/to/repo gunicorn 'gitsearch.web:create_app_from_env()'
```

## Configuration

Command-line options override environment variables, which override defaults:

| variable | default | |
|---|---|---|
| `GITSEARCH_REPO` | `.` | repository path |
| `GITSEARCH_REF` | `HEAD` | branch / tag / commit |
| `GITSEARCH_MAX_COMMITS` | all | only load the newest N commits |
| `GITSEARCH_TOKEN` | none | require this token for `/api/*` |
| `GITSEARCH_HOST`, `GITSEARCH_PORT` | `127.0.0.1`, `8000` | `serve` address |
| `GITSEARCH_SQL_TIMEOUT`, `GITSEARCH_SQL_MAX_ROWS` | `5`, `1000` | SQL limits |

## Design

```
src/gitsearch/
  models.py   Commit / FileChange dataclasses (+ to_dict)
  gitlog.py   pure parser for `git log --format=... --numstat` output
  repo.py     runs git in a subprocess (injectable runner); CommitStore caches per ref sha
  search.py   pure filtering, pagination, grouping, sha-prefix lookup
  sql.py      in-memory SQLite build + sandboxed read-only query execution
  config.py   defaults <- GITSEARCH_* env <- CLI overrides
  output.py   pure text rendering for the CLI (commit lines, tables)
  cli.py      argparse front-end
  web/        Falcon app (thin resources over the core) + static UI
```

Side effects live only in `repo.py`, `cli.py` and `web/`; everything else is pure and
unit-tested directly. History is read with one `git log` call per ref change instead of
GitPython, which keeps the dependency list to Falcon alone.

## Tests

```bash
.venv/bin/python -m pytest
```

Tests build throwaway repositories in `tmp_path` (with `HOME` and git global config
isolated), exercise the CLI through `main()` and the API through Falcon's `TestClient`.
No network access is needed.

## Known limitations

- Loads the whole history of one ref into memory (use `--max-commits` for huge repos);
  one repository per server.
- Renames are reported as delete + add (`--no-renames`); merge commits show no file
  stats (git's default for `--numstat`).
- Date filters are day-granular; text filters are plain substrings (no regex).
- The JavaScript UI was not exercised in a real browser here (the HTML/JS/CSS are
  served and the API it calls is tested); `serve` was run manually with `curl`.
- Falcon 3.x should work (`falcon>=3.1`) but only 4.4 was tested.

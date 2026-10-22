# gitsearch

> **DRAFT** - initial assessment of the prototype. To be finished after the rework.

## What this seems to be

A small web app for **searching the commit history of a local git repository**.
A Falcon (WSGI) JSON API reads commits with GitPython and returns them as JSON
(author, sha, date, message, per-file insertions/deletions); a Vue 2 + Bulma page
offers a search form (author, date range, keyword) and renders the matching commits.

The last commit ("added new stuff") adds two unwired experiments that hint at where it
was heading: a pyparsing grammar for `SELECT ... FROM ... WHERE ... GROUP BY ... ORDER BY
... LIMIT` queries (`src/sql_parser.py`) and a pooled SQLite wrapper (`src/alt_db.py`) -
i.e. "query your commit history with SQL".

## Current state (honest assessment)

What works:
- `GET /commits` returns the newest commits of a hard-coded branch, paginated with
  `page` / `per_page` - **if** the auth middleware is bypassed.
- `sql_parser.py` parses its own example queries (it runs them at import time).

What is broken or missing:
- **Filtering is not implemented**: `author`, `since`, `until` are collected and then
  dropped (`# TODO: add filtering`); the UI's keyword field is never sent.
- **Auth blocks everything**: the token middleware rejects every request without an
  `X-Auth-Token` header - including the HTML page and static files - and there is no way
  to create a token (the frontend never sends one either).
- `group_by` crashes (500): the grouped dict is fed back into the list formatter.
- Non-integer `page`/`per_page` crash with an unhandled `ValueError` (500).
- Hard-coded, machine-specific settings: repository path
  `/home/ckjackslack/Projects/aoc2023`, branch `master`, DB path next to the sources.
- The SQL parser and SQLite pool are not connected to anything; the parser only
  validates syntax, it cannot execute a query.
- `src/__init__.py` monkey-patches `json.dumps` and `sys.path`; leftover experiments
  (`/test/{arg:custom}` route, `CustomConverter`, Jinja `double` filter).
- "Tests" are a single unittest that writes to a real `test_database.db` next to the
  sources (and references an unimported `unittest`). Not a package, no CLI; started via
  `start.sh` (gunicorn) and poked with `test.sh` (curl with a personal author name).
- No secrets committed; only the personal path / username above.

## TODO / to be finished

- Rebuild as an installable package with a CLI and a real web UI.
- Implement filtering (author, date range, keyword, path), grouping and pagination.
- Make "query commits with SQL" actually work.
- Configuration via CLI / env instead of hard-coded paths; optional auth that does not
  lock out the UI.
- pytest suite.

"""Pure parsing of ``git log`` output (no subprocesses here).

``repo.py`` runs ``git log`` with :data:`LOG_ARGS`; :func:`parse_log` turns the raw text
into :class:`~gitsearch.models.Commit` objects.
"""

from __future__ import annotations

import codecs
from datetime import datetime

from .models import Commit, FileChange

RECORD_SEP = "\x1e"
FIELD_SEP = "\x1f"

# sha, parents, author name, author email, author date (strict ISO 8601), raw body
LOG_FORMAT = RECORD_SEP + FIELD_SEP.join(["%H", "%P", "%an", "%ae", "%aI", "%B"]) + FIELD_SEP
LOG_ARGS = ["log", f"--format={LOG_FORMAT}", "--numstat", "--no-renames", "--no-color"]

_N_FIELDS = 6


class LogParseError(ValueError):
    """Raised when ``git log`` output does not have the expected shape."""


def unquote_path(path: str) -> str:
    """Undo git's C-style quoting of unusual paths (``"a\\tb"`` -> ``a<TAB>b``)."""
    if len(path) >= 2 and path.startswith('"') and path.endswith('"'):
        raw = codecs.escape_decode(path[1:-1].encode("utf-8"))[0]
        return raw.decode("utf-8", errors="replace")
    return path


def parse_numstat_line(line: str) -> FileChange:
    try:
        added, deleted, path = line.split("\t", 2)
    except ValueError:
        raise LogParseError(f"malformed numstat line: {line!r}") from None
    if added == "-" and deleted == "-":  # binary file
        return FileChange(unquote_path(path), None, None)
    try:
        return FileChange(unquote_path(path), int(added), int(deleted))
    except ValueError:
        raise LogParseError(f"malformed numstat line: {line!r}") from None


def parse_record(record: str) -> Commit:
    parts = record.split(FIELD_SEP, _N_FIELDS)
    if len(parts) != _N_FIELDS + 1:
        raise LogParseError(f"expected {_N_FIELDS} fields, got {len(parts) - 1}")
    sha, parents, author, email, date, body, numstat = parts
    try:
        when = datetime.fromisoformat(date.strip())
    except ValueError:
        raise LogParseError(f"bad date {date!r} in commit {sha}") from None
    files = tuple(
        parse_numstat_line(line) for line in numstat.splitlines() if line.strip()
    )
    return Commit(
        sha=sha.strip(),
        author=author,
        email=email,
        date=when,
        message=body.strip(),
        parents=tuple(parents.split()),
        files=files,
    )


def parse_log(text: str) -> list[Commit]:
    """Parse the full output of ``git <LOG_ARGS>`` into commits (newest first)."""
    return [parse_record(rec) for rec in text.split(RECORD_SEP) if rec.strip()]

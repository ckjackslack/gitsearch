"""Pure search logic: filtering, pagination and grouping of commits."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from .models import Commit


class SearchError(ValueError):
    """Invalid search parameters (bad date, unknown group key, bad page...)."""


def parse_date(value: str | None, name: str = "date") -> date | None:
    if value is None or not str(value).strip():
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        raise SearchError(f"{name} must be a date in YYYY-MM-DD format, got {value!r}") from None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


@dataclass(frozen=True)
class CommitFilter:
    """All criteria are optional and combined with AND. Text matching is case-insensitive."""

    author: str | None = None  # substring of author name or email
    since: date | None = None  # inclusive, compared with the commit's local author date
    until: date | None = None  # inclusive
    text: str | None = None  # substring of the commit message, or a sha prefix
    path: str | None = None  # substring of any changed file path
    merges: bool | None = None  # True: only merges, False: no merges, None: both

    @classmethod
    def from_params(cls, params: Mapping[str, str | None]) -> "CommitFilter":
        """Build a filter from loosely-typed string parameters (CLI / query string)."""
        since = parse_date(params.get("since"), "since")
        until = parse_date(params.get("until"), "until")
        if since and until and since > until:
            raise SearchError("since must not be after until")
        merges_raw = _clean(params.get("merges"))
        merges = None
        if merges_raw is not None:
            lowered = merges_raw.lower()
            if lowered in ("only", "true", "1", "yes"):
                merges = True
            elif lowered in ("no", "false", "0", "none", "exclude"):
                merges = False
            elif lowered not in ("any", "all"):
                raise SearchError(f"merges must be one of only/no/any, got {merges_raw!r}")
        return cls(
            author=_clean(params.get("author")),
            since=since,
            until=until,
            text=_clean(params.get("q") or params.get("text")),
            path=_clean(params.get("path")),
            merges=merges,
        )

    def matches(self, commit: Commit) -> bool:
        if self.author:
            needle = self.author.lower()
            if needle not in commit.author.lower() and needle not in commit.email.lower():
                return False
        day = commit.date.date()
        if self.since and day < self.since:
            return False
        if self.until and day > self.until:
            return False
        if self.text:
            needle = self.text.lower()
            if needle not in commit.message.lower() and not commit.sha.startswith(needle):
                return False
        if self.path:
            needle = self.path.lower()
            if not any(needle in f.path.lower() for f in commit.files):
                return False
        if self.merges is not None and commit.is_merge != self.merges:
            return False
        return True


def filter_commits(commits: Iterable[Commit], flt: CommitFilter) -> list[Commit]:
    return [c for c in commits if flt.matches(c)]


def find_commit(commits: Iterable[Commit], sha_prefix: str) -> Commit | None:
    """Return the unique commit whose sha starts with ``sha_prefix`` (min. 4 chars)."""
    prefix = sha_prefix.strip().lower()
    if len(prefix) < 4 or any(c not in "0123456789abcdef" for c in prefix):
        raise SearchError("sha prefix must be at least 4 hex characters")
    found = [c for c in commits if c.sha.startswith(prefix)]
    if len(found) > 1:
        raise SearchError(f"ambiguous sha prefix {sha_prefix!r}")
    return found[0] if found else None


@dataclass(frozen=True)
class Page:
    items: list
    page: int
    per_page: int
    total: int

    @property
    def pages(self) -> int:
        return max(1, math.ceil(self.total / self.per_page))


def paginate(items: Sequence, page: int = 1, per_page: int = 10) -> Page:
    if page < 1:
        raise SearchError("page must be >= 1")
    if per_page < 1:
        raise SearchError("per_page must be >= 1")
    start = (page - 1) * per_page
    return Page(list(items[start : start + per_page]), page, per_page, len(items))


GROUP_KEYS: dict[str, Callable[[Commit], str]] = {
    "author": lambda c: c.author,
    "email": lambda c: c.email,
    "day": lambda c: c.date.strftime("%Y-%m-%d"),
    "month": lambda c: c.date.strftime("%Y-%m"),
    "year": lambda c: c.date.strftime("%Y"),
}
_DATE_KEYS = {"day", "month", "year"}


def group_commits(commits: Iterable[Commit], key: str) -> list[tuple[str, list[Commit]]]:
    """Group commits by ``key``. Date groups are newest first; others by size, then name."""
    try:
        keyfn = GROUP_KEYS[key]
    except KeyError:
        raise SearchError(
            f"unknown group key {key!r}; choose from {', '.join(GROUP_KEYS)}"
        ) from None
    groups: dict[str, list[Commit]] = {}
    for commit in commits:
        groups.setdefault(keyfn(commit), []).append(commit)
    if key in _DATE_KEYS:
        return sorted(groups.items(), key=lambda kv: kv[0], reverse=True)
    return sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0].lower()))

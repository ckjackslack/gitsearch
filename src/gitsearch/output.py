"""Pure text rendering for the CLI."""

from __future__ import annotations

from collections.abc import Sequence

from .models import Commit
from .search import Page


def _truncate(text: str, width: int) -> str:
    return text if len(text) <= width else text[: max(0, width - 1)] + "…"


def commit_line(c: Commit, width: int = 72) -> str:
    stats = f"+{c.insertions}/-{c.deletions}"
    head = f"{c.short_sha}  {c.date:%Y-%m-%d}  {_truncate(c.author, 18):<18}  "
    return head + _truncate(c.subject, width - len(head) - len(stats) - 2) + "  " + stats


def commit_details(c: Commit) -> str:
    lines = [
        f"commit {c.sha}" + ("  (merge)" if c.is_merge else ""),
        f"Author: {c.author} <{c.email}>",
        f"Date:   {c.date.isoformat()}",
        "",
        *("    " + line for line in c.message.splitlines()),
        "",
    ]
    for f in c.files:
        if f.insertions is None:
            lines.append(f"  {f.path}  (binary)")
        else:
            lines.append(f"  {f.path}  +{f.insertions} -{f.deletions}")
    lines.append(f"  {len(c.files)} file(s), +{c.insertions} -{c.deletions}")
    return "\n".join(lines)


def page_text(page: Page) -> str:
    if not page.total:
        return "No commits found."
    body = "\n".join(commit_line(c) for c in page.items) or "(page is empty)"
    return f"{body}\n-- page {page.page}/{page.pages}, {page.total} matching commit(s)"


def groups_text(groups: Sequence[tuple[str, Sequence[Commit]]]) -> str:
    if not groups:
        return "No commits found."
    width = max(len(k) for k, _ in groups)
    return "\n".join(f"{k:<{width}}  {len(v):>6}" for k, v in groups)


def table_text(columns: Sequence[str], rows: Sequence[Sequence], max_width: int = 60) -> str:
    """Render rows as an aligned plain-text table."""

    def cell(v) -> str:
        s = "NULL" if v is None else str(v)
        return _truncate(s.replace("\n", " "), max_width)

    cells = [[cell(v) for v in row] for row in rows]
    widths = [len(c) for c in columns]
    for row in cells:
        for i, v in enumerate(row):
            widths[i] = max(widths[i], len(v))
    fmt = lambda vals: "  ".join(v.ljust(w) for v, w in zip(vals, widths)).rstrip()
    out = [fmt(list(columns)), fmt(["-" * w for w in widths])]
    out.extend(fmt(r) for r in cells)
    out.append(f"({len(rows)} row{'s' if len(rows) != 1 else ''})")
    return "\n".join(out)

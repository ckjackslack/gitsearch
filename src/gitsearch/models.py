"""Plain data types shared by every layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class FileChange:
    """One file touched by a commit. ``None`` counts mean a binary file."""

    path: str
    insertions: int | None
    deletions: int | None

    def to_dict(self) -> dict:
        return {"path": self.path, "insertions": self.insertions, "deletions": self.deletions}


@dataclass(frozen=True)
class Commit:
    sha: str
    author: str
    email: str
    date: datetime  # author date, timezone-aware
    message: str
    parents: tuple[str, ...] = ()
    files: tuple[FileChange, ...] = field(default=())

    @property
    def short_sha(self) -> str:
        return self.sha[:7]

    @property
    def subject(self) -> str:
        return self.message.split("\n", 1)[0]

    @property
    def is_merge(self) -> bool:
        return len(self.parents) > 1

    @property
    def insertions(self) -> int:
        return sum(f.insertions or 0 for f in self.files)

    @property
    def deletions(self) -> int:
        return sum(f.deletions or 0 for f in self.files)

    def to_dict(self) -> dict:
        return {
            "sha": self.sha,
            "short_sha": self.short_sha,
            "author": self.author,
            "email": self.email,
            "date": self.date.isoformat(),
            "subject": self.subject,
            "message": self.message,
            "parents": list(self.parents),
            "is_merge": self.is_merge,
            "insertions": self.insertions,
            "deletions": self.deletions,
            "files": [f.to_dict() for f in self.files],
        }

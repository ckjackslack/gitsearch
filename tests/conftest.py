"""Shared fixtures: an isolated git environment and a small sample repository."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from gitsearch.models import Commit, FileChange


@pytest.fixture(autouse=True)
def isolated_git(tmp_path_factory, monkeypatch):
    """Never read the user's git config or home dir; clear GITSEARCH_* vars."""
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for key in list(os.environ):
        if key.startswith("GITSEARCH_"):
            monkeypatch.delenv(key)


class RepoBuilder:
    def __init__(self, path: Path):
        self.path = path
        path.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q", "-b", "main")

    def git(self, *args, author=("Tester", "tester@example.com"), date=None) -> str:
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": author[0],
            "GIT_AUTHOR_EMAIL": author[1],
            "GIT_COMMITTER_NAME": author[0],
            "GIT_COMMITTER_EMAIL": author[1],
        }
        if date:
            env["GIT_AUTHOR_DATE"] = date
            env["GIT_COMMITTER_DATE"] = date
        out = subprocess.run(["git", *args], cwd=self.path, env=env, check=True,
                             capture_output=True, text=True)
        return out.stdout.strip()

    def write(self, rel: str, content: str | bytes) -> None:
        p = self.path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content, encoding="utf-8")

    def commit(self, message: str, author, date: str) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message, author=author, date=date)
        return self.git("rev-parse", "HEAD")


ALICE = ("Alice Smith", "alice@example.com")
BOB = ("Bob Jones", "bob@example.org")
CAROL = ("Carol", "carol@example.net")


@pytest.fixture
def sample_repo(tmp_path) -> RepoBuilder:
    """main: init(Alice) -> parser(Bob) -> fix(Alice) -> merge of feature(Carol)."""
    r = RepoBuilder(tmp_path / "sample")
    r.write("README.md", "# Sample\n\nhello\n")
    r.commit("Initial commit", ALICE, "2024-01-01T10:00:00+01:00")
    r.write("src/parser.py", "def parse():\n    pass\n\n")
    r.commit("Add parser\n\nThe tokenizer comes later.", BOB, "2024-01-15T09:30:00+00:00")
    r.write("src/parser.py", "def parse():\n    return 1\n\n")
    r.write("data.bin", b"\x00\x01\x02binary\x00")
    r.commit("Fix parser bug", ALICE, "2024-02-03T23:30:00-05:00")
    r.git("checkout", "-q", "-b", "feature", "HEAD~1")
    r.write("docs/zażółć guide.md", "unicode path\n")
    r.commit("Feature work", CAROL, "2024-02-10T12:00:00+00:00")
    r.git("checkout", "-q", "main")
    r.git("merge", "-q", "--no-ff", "-m", "Merge branch 'feature'", "feature",
          author=ALICE, date="2024-02-20T08:00:00+00:00")
    return r


def make_commit(
    sha: str = "a" * 40,
    author: str = "Alice",
    email: str = "alice@example.com",
    when: str = "2024-01-01T12:00:00+00:00",
    message: str = "subject",
    parents: tuple[str, ...] = ("b" * 40,),
    files: tuple[FileChange, ...] = (FileChange("src/a.py", 3, 1),),
) -> Commit:
    return Commit(sha, author, email, datetime.fromisoformat(when), message, parents, files)


@pytest.fixture
def commits() -> list[Commit]:
    """Hand-built history for pure-logic tests (newest first)."""
    base = datetime(2024, 3, 1, 12, tzinfo=timezone.utc)
    out = []
    authors = [("Alice", "alice@x.io"), ("Bob", "bob@y.io"), ("alice", "al@z.io")]
    for i in range(12):
        name, email = authors[i % 3]
        when = (base - timedelta(days=5 * i)).isoformat()
        files = (FileChange(f"pkg/mod{i % 4}.py", i, i // 2),)
        if i % 5 == 0:
            files += (FileChange("assets/logo.png", None, None),)
        out.append(make_commit(
            sha=f"{i:02x}" * 20, author=name, email=email, when=when,
            message=f"Commit number {i}\n\nbody {'FIX' if i % 4 == 0 else 'feat'}",
            parents=(("c" * 40, "d" * 40) if i == 6 else ("e" * 40,)),
            files=files,
        ))
    return out

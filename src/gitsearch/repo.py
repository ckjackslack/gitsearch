"""Side-effecting layer: run ``git`` in a subprocess and cache parsed history."""

from __future__ import annotations

import os
import subprocess
import threading
from collections.abc import Callable, Sequence

from .gitlog import LOG_ARGS, parse_log
from .models import Commit

Runner = Callable[[Sequence[str], str], str]


class GitError(RuntimeError):
    """Any failure talking to git (bad path, unknown ref, git missing...)."""


def subprocess_runner(args: Sequence[str], cwd: str) -> str:
    """Run git and return stdout; raise :class:`GitError` with git's message on failure."""
    env = {**os.environ, "LC_ALL": "C", "GIT_PAGER": "cat"}
    try:
        proc = subprocess.run(
            ["git", "-c", "core.quotepath=off", *args],
            cwd=cwd,
            env=env,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        raise GitError("git executable not found on PATH") from None
    if proc.returncode != 0:
        msg = proc.stderr.decode("utf-8", "replace").strip() or f"git exited with {proc.returncode}"
        raise GitError(msg)
    return proc.stdout.decode("utf-8", "replace")


class GitRepository:
    def __init__(self, path: str, runner: Runner = subprocess_runner):
        self.path = os.path.abspath(os.path.expanduser(path))
        self._run = runner
        if not os.path.isdir(self.path):
            raise GitError(f"not a directory: {self.path}")
        try:
            self._run(["rev-parse", "--git-dir"], self.path)
        except GitError:
            raise GitError(f"not a git repository: {self.path}") from None

    @staticmethod
    def _check_ref(ref: str) -> None:
        if not ref or ref.startswith("-") or any(c.isspace() for c in ref):
            raise GitError(f"invalid ref: {ref!r}")

    def resolve(self, ref: str = "HEAD") -> str:
        """Return the commit sha ``ref`` points to."""
        self._check_ref(ref)
        try:
            out = self._run(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], self.path)
        except GitError:
            out = ""
        sha = out.strip()
        if not sha:
            raise GitError(f"unknown revision {ref!r} (empty repository or no such branch?)")
        return sha

    def log(self, ref: str = "HEAD", max_count: int | None = None) -> list[Commit]:
        """All commits reachable from ``ref``, newest first."""
        sha = self.resolve(ref)
        args = list(LOG_ARGS)
        if max_count:
            args.append(f"--max-count={int(max_count)}")
        args.append(sha)
        return parse_log(self._run(args, self.path))


class CommitStore:
    """Caches the parsed history of one ref and reloads it when the ref moves."""

    def __init__(self, repo: GitRepository, ref: str = "HEAD", max_count: int | None = None):
        self.repo = repo
        self.ref = ref
        self.max_count = max_count
        self._lock = threading.Lock()
        self._sha: str | None = None
        self._commits: list[Commit] = []

    def commits(self) -> list[Commit]:
        with self._lock:
            sha = self.repo.resolve(self.ref)
            if sha != self._sha:
                self._commits = self.repo.log(sha, self.max_count)
                self._sha = sha
            return self._commits

    @property
    def head(self) -> str | None:
        return self._sha

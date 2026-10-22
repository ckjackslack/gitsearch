import pytest

from conftest import ALICE, RepoBuilder
from gitsearch.repo import CommitStore, GitError, GitRepository


def test_log_reads_real_repository(sample_repo):
    repo = GitRepository(str(sample_repo.path))
    commits = repo.log("main")
    assert [c.subject for c in commits] == [
        "Merge branch 'feature'", "Feature work", "Fix parser bug", "Add parser", "Initial commit",
    ]
    merge, feature, fix, parser, init = commits
    assert merge.is_merge and merge.files == ()
    assert feature.author == "Carol"
    assert [f.path for f in feature.files] == ["docs/zażółć guide.md"]
    assert {f.path: (f.insertions, f.deletions) for f in fix.files} == {
        "data.bin": (None, None), "src/parser.py": (1, 1),
    }
    assert parser.message == "Add parser\n\nThe tokenizer comes later."
    assert fix.date.isoformat() == "2024-02-03T23:30:00-05:00"
    assert init.parents == () and init.email == "alice@example.com"


def test_log_other_ref_and_max_count(sample_repo):
    repo = GitRepository(str(sample_repo.path))
    assert [c.subject for c in repo.log("feature")] == ["Feature work", "Add parser", "Initial commit"]
    assert len(repo.log("main", max_count=2)) == 2
    assert repo.resolve("main") == sample_repo.git("rev-parse", "main")


def test_not_a_directory(tmp_path):
    with pytest.raises(GitError, match="not a directory"):
        GitRepository(str(tmp_path / "missing"))


def test_not_a_repository(tmp_path):
    with pytest.raises(GitError, match="not a git repository"):
        GitRepository(str(tmp_path))


def test_empty_repository(tmp_path):
    RepoBuilder(tmp_path / "empty")
    repo = GitRepository(str(tmp_path / "empty"))
    with pytest.raises(GitError, match="unknown revision"):
        repo.log()


@pytest.mark.parametrize("ref", ["nope", "", "--all", "a b"])
def test_bad_refs(sample_repo, ref):
    with pytest.raises(GitError):
        GitRepository(str(sample_repo.path)).resolve(ref)


def test_store_caches_until_ref_moves(sample_repo):
    store = CommitStore(GitRepository(str(sample_repo.path)), "main")
    first = store.commits()
    assert store.commits() is first
    sample_repo.write("new.txt", "x\n")
    sample_repo.commit("Another one", ALICE, "2024-03-01T00:00:00+00:00")
    second = store.commits()
    assert second is not first and second[0].subject == "Another one"
    assert store.head == second[0].sha


def test_fake_runner_and_git_missing(tmp_path):
    calls = []

    def runner(args, cwd):
        calls.append(list(args))
        if args[0] == "rev-parse" and args[1] == "--git-dir":
            return ".git\n"
        raise GitError("boom")

    repo = GitRepository(str(tmp_path), runner=runner)
    with pytest.raises(GitError, match="unknown revision"):
        repo.resolve("HEAD")
    assert calls[0] == ["rev-parse", "--git-dir"]


def test_subprocess_runner_without_git(tmp_path, monkeypatch):
    from gitsearch.repo import subprocess_runner

    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(GitError, match="not found"):
        subprocess_runner(["status"], str(tmp_path))

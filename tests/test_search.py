from datetime import date

import pytest

from conftest import make_commit
from gitsearch.models import FileChange
from gitsearch.search import (
    CommitFilter,
    SearchError,
    filter_commits,
    find_commit,
    group_commits,
    paginate,
    parse_date,
)


def test_empty_filter_matches_everything(commits):
    assert filter_commits(commits, CommitFilter()) == commits


def test_author_matches_name_or_email_case_insensitive(commits):
    names = {c.author for c in filter_commits(commits, CommitFilter(author="ALICE"))}
    assert names == {"Alice", "alice"}
    assert all(c.email == "bob@y.io" for c in filter_commits(commits, CommitFilter(author="y.io")))


def test_date_range_is_inclusive(commits):
    # commits are 5 days apart starting 2024-03-01 going back
    got = filter_commits(commits, CommitFilter(since=date(2024, 2, 20), until=date(2024, 3, 1)))
    assert [c.date.date() for c in got] == [date(2024, 3, 1), date(2024, 2, 25), date(2024, 2, 20)]


def test_date_uses_commit_local_timezone():
    late = make_commit(when="2024-02-03T23:30:00-05:00")  # 2024-02-04 in UTC
    assert CommitFilter(until=date(2024, 2, 3)).matches(late)
    assert not CommitFilter(since=date(2024, 2, 4)).matches(late)


def test_text_matches_message_or_sha_prefix(commits):
    assert len(filter_commits(commits, CommitFilter(text="fix"))) == 3
    assert filter_commits(commits, CommitFilter(text="0505")) == [commits[5]]


def test_path_and_merges(commits):
    assert len(filter_commits(commits, CommitFilter(path="LOGO"))) == 3
    assert filter_commits(commits, CommitFilter(merges=True)) == [commits[6]]
    assert len(filter_commits(commits, CommitFilter(merges=False))) == 11


def test_filters_combine_with_and(commits):
    got = filter_commits(commits, CommitFilter(author="bob", path="mod1"))
    assert got and all(c.author == "Bob" and "mod1" in c.files[0].path for c in got)


def test_from_params_parses_and_cleans():
    f = CommitFilter.from_params(
        {"author": "  ", "since": "2024-01-01", "until": "", "q": " fix ", "merges": "no"}
    )
    assert f == CommitFilter(author=None, since=date(2024, 1, 1), text="fix", merges=False)
    assert CommitFilter.from_params({"merges": "only"}).merges is True
    assert CommitFilter.from_params({"merges": "any"}).merges is None


@pytest.mark.parametrize(
    "params",
    [{"since": "2024-13-01"}, {"until": "tomorrow"}, {"since": "2024-02-02", "until": "2024-01-01"},
     {"merges": "maybe"}],
)
def test_from_params_rejects_bad_input(params):
    with pytest.raises(SearchError):
        CommitFilter.from_params(params)


def test_parse_date_empty():
    assert parse_date(None) is None and parse_date("") is None


def test_paginate(commits):
    p = paginate(commits, page=2, per_page=5)
    assert p.items == commits[5:10] and p.total == 12 and p.pages == 3
    assert paginate(commits, page=3, per_page=5).items == commits[10:]
    assert paginate(commits, page=9, per_page=5).items == []
    assert paginate([], 1, 10).pages == 1
    with pytest.raises(SearchError):
        paginate(commits, page=0)
    with pytest.raises(SearchError):
        paginate(commits, per_page=0)


def test_group_by_author_sorted_by_size_then_name(commits):
    groups = group_commits(commits, "author")
    assert [(k, len(v)) for k, v in groups] == [("Alice", 4), ("alice", 4), ("Bob", 4)]


def test_group_by_month_newest_first(commits):
    groups = group_commits(commits, "month")
    keys = [k for k, _ in groups]
    assert keys == sorted(keys, reverse=True) and keys[0] == "2024-03"
    assert sum(len(v) for _, v in groups) == len(commits)


def test_group_unknown_key(commits):
    with pytest.raises(SearchError, match="unknown group key"):
        group_commits(commits, "colour")


def test_find_commit(commits):
    assert find_commit(commits, "0303") is commits[3]
    assert find_commit(commits, "ffff") is None
    with pytest.raises(SearchError):
        find_commit(commits, "abc")
    with pytest.raises(SearchError):
        find_commit(commits, "zzzz")
    twins = [make_commit(sha="abcd1" + "0" * 35), make_commit(sha="abcd2" + "0" * 35)]
    with pytest.raises(SearchError, match="ambiguous"):
        find_commit(twins, "abcd")


def test_commit_to_dict_binary_counts():
    c = make_commit(files=(FileChange("a", 2, 1), FileChange("b.png", None, None)))
    d = c.to_dict()
    assert d["insertions"] == 2 and d["deletions"] == 1
    assert d["files"][1] == {"path": "b.png", "insertions": None, "deletions": None}
    assert d["short_sha"] == "a" * 7

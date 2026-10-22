from datetime import datetime, timedelta

import pytest

from gitsearch.gitlog import (
    FIELD_SEP as F,
    RECORD_SEP as R,
    LogParseError,
    parse_log,
    parse_numstat_line,
    parse_record,
    unquote_path,
)
from gitsearch.models import FileChange


def record(sha="a" * 40, parents="b" * 40, name="Ann", email="ann@x", date="2024-01-02T03:04:05+02:00",
           body="Subject\n\nBody line\n", numstat="\n3\t1\tsrc/x.py\n-\t-\timg.png\n"):
    return R + F.join([sha, parents, name, email, date, body]) + F + numstat


def test_parse_single_record():
    (c,) = parse_log(record())
    assert c.sha == "a" * 40
    assert c.parents == ("b" * 40,)
    assert c.author == "Ann" and c.email == "ann@x"
    assert c.date == datetime.fromisoformat("2024-01-02T03:04:05+02:00")
    assert c.date.utcoffset() == timedelta(hours=2)
    assert c.message == "Subject\n\nBody line"
    assert c.subject == "Subject"
    assert c.files == (FileChange("src/x.py", 3, 1), FileChange("img.png", None, None))
    assert (c.insertions, c.deletions) == (3, 1)


def test_parse_multiple_records_and_merge_and_root():
    text = record(sha="1" * 40, parents=f"{'2' * 40} {'3' * 40}", numstat="\n") + record(
        sha="4" * 40, parents="", numstat="\n1\t0\ta\n"
    )
    merge, root = parse_log(text)
    assert merge.is_merge and merge.files == ()
    assert root.parents == () and not root.is_merge


def test_parse_empty_output():
    assert parse_log("") == []
    assert parse_log("\n") == []


def test_message_with_tabs_and_unicode():
    (c,) = parse_log(record(body="Zażółć\tgęślą\n", numstat=""))
    assert c.message == "Zażółć\tgęślą"


def test_numstat_quoted_path():
    fc = parse_numstat_line('1\t2\t"we\\tird\\"name.txt"')
    assert fc == FileChange('we\tird"name.txt', 1, 2)


def test_unquote_utf8_octal_escapes():
    assert unquote_path('"\\305\\274.txt"') == "ż.txt"
    assert unquote_path("plain.txt") == "plain.txt"


@pytest.mark.parametrize("line", ["garbage", "x\ty\tpath", "1\t2"])
def test_bad_numstat(line):
    with pytest.raises(LogParseError):
        parse_numstat_line(line)


def test_bad_record_shape_and_date():
    with pytest.raises(LogParseError):
        parse_record("only" + F + "two")
    with pytest.raises(LogParseError):
        parse_log(record(date="yesterday"))

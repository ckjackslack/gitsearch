import math
import os
from collections import defaultdict
from datetime import datetime

from src.settings import NOT_FOUND
from src.typedefs import GroupKey


class Paginator:
    def __init__(self, items, page_size=10):
        assert page_size > 0
        assert isinstance(items, list)

        self.items = items

        self._current_page = 1
        self._page_size = page_size
        self.__size = len(items)

    @property
    def current_page(self):
        return self._current_page

    @property
    def page_size(self):
        return self._page_size

    @property
    def no_of_pages(self):
        return max(1, math.ceil(self.__size / self.page_size))

    @property
    def pages_list(self):
        return list(range(1, self.no_of_pages + 1))

    def get_page(self, page):
        assert 0 < page <= self.no_of_pages
        self._current_page = page
        offset = (self.current_page - 1) * self.page_size
        return self.items[offset:offset+self.page_size]

    def iterate_over_pages(self):
        for n in self.pages_list:
            yield self.get_page(n)


def format_commits(commits):
    return [
    {
        "author": commit.author,
        "commit": commit.hexsha,
        "date": str(datetime.fromtimestamp(commit.authored_date)),
        "message": commit.message.strip(),
        "files": [
            (file, data["insertions"], data["deletions"])
            for file, data
            in commit.stats.files.items()
        ]
    }
    for commit
    in commits
]


def group_by(items, key: GroupKey):
    grouped = defaultdict(list)
    for item in items:
        prop = None
        if type(key) is str:
            prop = getattr(item, key, NOT_FOUND)
        elif callable(key):
            prop = key(item)
        if prop is not None:
            grouped[prop].append(item)
    return grouped


def add_prefix_to_filename(filepath, prefix):
    path, ext = os.path.splitext(filepath)
    d_name = os.path.dirname(path)
    f_name = os.path.basename(path)
    return os.path.join(d_name, f"{prefix}{f_name}{ext}")
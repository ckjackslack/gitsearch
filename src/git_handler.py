from git import (
    GitCommandError,
    Repo,
)

from src.settings import AVAILABLE_FIELDS, BRANCH_NAME
from src.typedefs import GroupKey
from src.utils import group_by


class GitRepoHandler:
    def __init__(self, repo_path):
        try:
            self.repo = Repo(repo_path)
        except GitCommandError:
            raise ValueError("Invalid Git repository path")

    def get_commits(self, filter_options=None, page=1, per_page=10):
        kwargs = {}
        if filter_options is not None:
            for field in AVAILABLE_FIELDS:
                if field in filter_options:
                    kwargs[field] = filter_options[field]

        # TODO: add filtering
        start_index = (page - 1) * per_page
        return list(
            self.repo.iter_commits(
                BRANCH_NAME,
                skip=start_index,
                max_count=per_page,
            )
        )

    def group_commits(self, commits, key: GroupKey):
        return group_by(commits, key)
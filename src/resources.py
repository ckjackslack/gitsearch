import os
import mimetypes
from urllib.parse import urlparse

import falcon

from src.environment import jinja_env
from src.settings import (
    AVAILABLE_FIELDS,
    DEFAULT_PAGE,
    PAGE_SIZE,
)
from src.utils import (
    format_commits,
)


class CommitResource:
    def __init__(self, repo_handler):
        self.repo_handler = repo_handler

    def on_get(self, req, resp):
        filter_options = {}
        for param in AVAILABLE_FIELDS:
            filter_options[param] = req.get_param(param)

        page = int(req.get_param("page", default=DEFAULT_PAGE))
        per_page = int(req.get_param("per_page", default=PAGE_SIZE))

        try:
            commits = self.repo_handler.get_commits(filter_options, page, per_page)
            group_by = req.get_param("group_by")
            if group_by:
                commits = self.repo_handler.group_commits(commits, group_by)
            resp.media = format_commits(commits)
        except Exception as e:
            resp.status = falcon.HTTP_500
            resp.media = {
                "error": "An error occurred while processing your request",
            }


class HomeResource:
    def on_get(self, req, resp):
        resp.media = {
            "message": "Welcome to the Git Commit Utility API",
        }


class StaticFileHandler:
    PREFIX = "/static/"

    def __init__(self, document_root):
        self.document_root = os.path.abspath(document_root)

    def on_get(self, req, resp):
        path = urlparse(req.uri).path
        path = path.replace(self.PREFIX, "")

        file_path = os.path.abspath(
            os.path.join(self.document_root, path)
        )

        if not file_path.startswith(self.document_root):
            raise falcon.HTTPForbidden()

        if os.path.isfile(file_path):
            content_type = (
                mimetypes.guess_type(file_path)[0]
                or "application/octet-stream"
            )
            resp.content_type = content_type
            with open(file_path, "rb") as f:
                resp.text = f.read()
        else:
            raise falcon.HTTPNotFound()


class TemplateResource:
    def on_get(self, req, resp):
        template = jinja_env.get_template("pages/index.html")
        data = {
            "title": "Git Commit Utility",
            "heading": "Git Commits Search",
        }
        html_content = template.render(**data)

        resp.content_type = falcon.MEDIA_HTML
        resp.text = html_content
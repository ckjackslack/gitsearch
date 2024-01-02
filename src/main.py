#!/bin/python3
from falcon import App

from src.converters import CustomConverter
from src.git_handler import GitRepoHandler
from src.middleware import AuthMiddleware
from src.resources import (
    CommitResource,
    HomeResource,
    StaticFileHandler,
    TemplateResource,
)
from src.settings import (
    DB_PATH,
    REPO_PATH,
    STATIC_PATH,
)


app = App(
    middleware=[
        AuthMiddleware(DB_PATH),
    ],
)
app.router_options.converters["custom"] = CustomConverter

static = StaticFileHandler(STATIC_PATH)
app.add_sink(static.on_get, static.PREFIX)

app.add_route("/", HomeResource())

git_handler = GitRepoHandler(REPO_PATH)
app.add_route("/commits", CommitResource(git_handler))
app.add_route("/front", TemplateResource())

class DummyResource:
    def on_get(self, req, resp, **kwargs):
        print(kwargs)

app.add_route("/test/{arg:custom}", DummyResource())

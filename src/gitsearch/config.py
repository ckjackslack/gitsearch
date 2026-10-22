"""Configuration: defaults <- environment variables <- CLI arguments."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

ENV_PREFIX = "GITSEARCH_"


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    repo: str = "."
    ref: str = "HEAD"
    max_commits: int | None = None  # only load the newest N commits
    token: str | None = None  # if set, /api/* requires it
    host: str = "127.0.0.1"
    port: int = 8000
    sql_timeout: float = 5.0
    sql_max_rows: int = 1000

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, **overrides) -> "Config":
        """Read ``GITSEARCH_*`` variables, then apply non-None ``overrides``."""
        env = os.environ if env is None else env
        values: dict = {}

        def get(name: str) -> str | None:
            raw = env.get(ENV_PREFIX + name.upper())
            return raw if raw not in (None, "") else None

        def as_number(name: str, conv):
            raw = get(name)
            if raw is None:
                return None
            try:
                return conv(raw)
            except ValueError:
                raise ConfigError(f"{ENV_PREFIX}{name.upper()} must be a number, got {raw!r}") from None

        for name in ("repo", "ref", "token", "host"):
            if (v := get(name)) is not None:
                values[name] = v
        for name, conv in (("max_commits", int), ("port", int), ("sql_timeout", float),
                           ("sql_max_rows", int)):
            if (v := as_number(name, conv)) is not None:
                values[name] = v
        values.update({k: v for k, v in overrides.items() if v is not None})
        cfg = cls(**values)
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.max_commits is not None and self.max_commits < 1:
            raise ConfigError("max_commits must be >= 1")
        if not 0 < self.port < 65536:
            raise ConfigError("port must be between 1 and 65535")
        if self.sql_timeout <= 0:
            raise ConfigError("sql_timeout must be > 0")
        if self.sql_max_rows < 1:
            raise ConfigError("sql_max_rows must be >= 1")

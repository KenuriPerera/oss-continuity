"""Repository source abstraction shared by the GitHub and local backends."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


class SourceError(Exception):
    """The repository could not be analysed at all."""


class SourceUnavailable(SourceError):
    """One kind of data (for example commit history) is not available."""


@dataclass(frozen=True)
class Commit:
    identity: str  # stable key: GitHub login, or e-mail address
    name: str  # display name
    date: datetime


@dataclass(frozen=True)
class Release:
    tag: str
    date: datetime | None
    kind: str  # "release" (GitHub release) or "tag"


_BOT_RE = re.compile(
    r"(\[bot\]|^dependabot|^renovate|^github-actions|^pre-commit-ci|^snyk-bot|-bot$|^bot$)",
    re.IGNORECASE,
)


def is_bot(identity: str, name: str = "") -> bool:
    return bool(_BOT_RE.search(identity or "") or _BOT_RE.search(name or ""))


_VERSION_TAG = re.compile(r"^(?:[A-Za-z][\w.-]*[-_/@])?v?\d+(?:\.\d+)*(?:[-+.]?[0-9A-Za-z.]+)?$")


def prefer_version_tags(releases: list[Release]) -> list[Release]:
    """Drop non-version tags (e.g. '2.1.x' branch markers, 'latest') when version tags exist."""
    versions = [r for r in releases if _VERSION_TAG.match(r.tag) and not r.tag.lower().endswith((".x", "-x"))]
    return versions or releases


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class RepoSource(ABC):
    """Read-only view of a repository: file tree, file contents, history, releases."""

    kind = "unknown"

    def __init__(self, display_name: str, location: str) -> None:
        self.display_name = display_name
        self.location = location
        self.commits_truncated = False
        self._paths: list[str] | None = None
        self._index: dict[str, str] = {}
        self._cache: dict[str, str | None] = {}

    # -- backend hooks -------------------------------------------------
    @abstractmethod
    def _list_paths(self) -> list[str]: ...

    @abstractmethod
    def _read(self, path: str) -> str | None: ...

    @abstractmethod
    def commits(self, since: datetime) -> list[Commit]:
        """Commits (newest first, merges excluded) since the given time."""

    @abstractmethod
    def releases(self) -> list[Release]:
        """Releases or tags, newest first."""

    def facts(self) -> dict[str, Any]:
        return {}

    # -- shared helpers ------------------------------------------------
    def paths(self) -> list[str]:
        if self._paths is None:
            self._paths = sorted(set(self._list_paths()))
            self._index = {p.lower(): p for p in self._paths}
        return self._paths

    def find(self, *candidates: str) -> list[str]:
        """Return existing paths matching any candidate (case-insensitive, exact)."""
        self.paths()
        out: list[str] = []
        for cand in candidates:
            hit = self._index.get(cand.lower())
            if hit and hit not in out:
                out.append(hit)
        return out

    def match(self, pattern: str) -> list[str]:
        """Return paths fully matching a regular expression (case-insensitive)."""
        rx = re.compile(pattern, re.IGNORECASE)
        return [p for p in self.paths() if rx.fullmatch(p)]

    def read_text(self, path: str) -> str | None:
        if path not in self._cache:
            self._cache[path] = self._read(path)
        return self._cache[path]

"""Analyse a public (or token-accessible) GitHub repository through the REST API.

Only the standard library is used. File contents are fetched from
raw.githubusercontent.com, which does not count against the API rate limit.
Set GITHUB_TOKEN (or GH_TOKEN) to raise the limit or read private repositories.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from . import __version__
from .source import Commit, Release, RepoSource, SourceError, SourceUnavailable, parse_iso

API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"
MAX_READ_BYTES = 512 * 1024

# (url, headers) -> (status, lower-cased headers, body)
HttpGet = Callable[[str, dict], "tuple[int, dict, bytes]"]

_SLUG_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9._-]+$")
_URL_RE = re.compile(r"^(?:https?://|git@)?(?:www\.)?github\.com[/:]([^/\s]+)/([^/\s]+?)(?:\.git)?(?:/.*)?$")


def parse_github_target(target: str) -> str | None:
    """Return 'owner/repo' for a slug or GitHub URL, otherwise None."""
    target = target.strip()
    m = _URL_RE.match(target)
    if m:
        target = f"{m.group(1)}/{m.group(2)}"
    return target if _SLUG_RE.match(target) else None


def urllib_get(url: str, headers: dict) -> tuple[int, dict, bytes]:
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=30) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
    except HTTPError as exc:
        hdrs = {k.lower(): v for k, v in (exc.headers or {}).items()}
        return exc.code, hdrs, exc.read() or b""
    except URLError as exc:
        raise SourceError(f"network error contacting GitHub: {exc.reason}") from exc


class GitHubSource(RepoSource):
    kind = "github"

    def __init__(
        self,
        slug: str,
        token: str | None = None,
        max_commits: int = 300,
        http_get: HttpGet | None = None,
    ) -> None:
        super().__init__(display_name=slug, location=f"https://github.com/{slug}")
        self.slug = slug
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        self.max_commits = max(1, max_commits)
        self._get = http_get or urllib_get
        self._meta: dict[str, Any] | None = None
        self.tree_truncated = False
        self.api_calls = 0

    # -- HTTP ----------------------------------------------------------
    def _headers(self) -> dict:
        h = {"User-Agent": f"oss-continuity/{__version__}", "Accept": "application/vnd.github+json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _api(self, path: str, allow_404: bool = False) -> Any:
        status, headers, body = self._get(API + path, self._headers())
        self.api_calls += 1
        if status == 200:
            return json.loads(body.decode("utf-8") or "null")
        if status == 404 and allow_404:
            return None
        if status == 404:
            raise SourceError(
                f"GitHub repository '{self.slug}' was not found (for private repositories set GITHUB_TOKEN)"
            )
        if status == 409:
            raise SourceUnavailable("the repository is empty")
        if status in (403, 429):
            if headers.get("x-ratelimit-remaining") == "0" or status == 429:
                raise SourceError("GitHub API rate limit exceeded; set GITHUB_TOKEN to raise the limit")
            raise SourceError(f"GitHub API denied access to {path} (HTTP {status})")
        raise SourceError(f"GitHub API error for {path} (HTTP {status})")

    # -- metadata ------------------------------------------------------
    @property
    def meta(self) -> dict[str, Any]:
        if self._meta is None:
            self._meta = self._api(f"/repos/{self.slug}")
            full = self._meta.get("full_name")
            if full:
                self.slug = full
                self.display_name = full
                self.location = f"https://github.com/{full}"
        return self._meta

    @property
    def branch(self) -> str:
        return self.meta.get("default_branch") or "main"

    def facts(self) -> dict[str, Any]:
        m = self.meta
        return {
            "default_branch": self.branch,
            "archived": bool(m.get("archived")),
            "stars": m.get("stargazers_count"),
            "forks": m.get("forks_count"),
            "open_issues": m.get("open_issues_count"),
            "file_tree_truncated": self.tree_truncated,
            "github_api_calls": self.api_calls,
        }

    # -- RepoSource ----------------------------------------------------
    def _list_paths(self) -> list[str]:
        branch = quote(self.branch, safe="")
        data = self._api(f"/repos/{self.slug}/git/trees/{branch}?recursive=1")
        self.tree_truncated = bool(data.get("truncated"))
        return [e["path"] for e in data.get("tree", []) if e.get("type") == "blob"]

    def _read(self, path: str) -> str | None:
        url = f"{RAW}/{self.slug}/{quote(self.branch, safe='/')}/{quote(path, safe='/')}"
        status, _, body = self._get(url, self._headers())
        if status != 200 or len(body) > MAX_READ_BYTES:
            return None
        return body.decode("utf-8", errors="replace")

    def commits(self, since: datetime) -> list[Commit]:
        stamp = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        commits: list[Commit] = []
        page = 1
        while len(commits) < self.max_commits:
            batch = self._api(f"/repos/{self.slug}/commits?since={stamp}&per_page=100&page={page}")
            if not batch:
                break
            for item in batch:
                if len(item.get("parents") or []) > 1:
                    continue  # merge commit
                info = (item.get("commit") or {}).get("author") or {}
                login = (item.get("author") or {}).get("login")
                name = info.get("name") or login or "unknown"
                identity = login or (info.get("email") or name).lower()
                when = parse_iso(info.get("date"))
                if when is not None:
                    commits.append(Commit(identity=identity, name=name, date=when))
            if len(batch) < 100:
                break
            page += 1
        else:
            self.commits_truncated = True
        if len(commits) > self.max_commits:
            commits = commits[: self.max_commits]
            self.commits_truncated = True
        return commits

    def releases(self) -> list[Release]:
        rels = self._api(f"/repos/{self.slug}/releases?per_page=30") or []
        out = [
            Release(
                tag=r["tag_name"],
                date=parse_iso(r.get("published_at") or r.get("created_at")),
                kind="release",
            )
            for r in rels
            if not r.get("draft")
        ]
        if out:
            return out
        tags = self._api(f"/repos/{self.slug}/tags?per_page=30") or []
        result: list[Release] = []
        for i, t in enumerate(tags):
            date = None
            if i == 0:  # only resolve the newest tag's date to save API calls
                sha = (t.get("commit") or {}).get("sha")
                if sha:
                    c = self._api(f"/repos/{self.slug}/commits/{sha}", allow_404=True) or {}
                    info = (c.get("commit") or {}).get("committer") or {}
                    date = parse_iso(info.get("date"))
            result.append(Release(tag=t["name"], date=date, kind="tag"))
        return result

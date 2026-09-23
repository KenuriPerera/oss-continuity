"""Analyse a repository checked out on the local filesystem."""

from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

from .source import Commit, Release, RepoSource, SourceUnavailable, parse_iso

SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".tox",
    ".nox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    "target",
    ".idea",
    ".next",
    ".gradle",
}
MAX_READ_BYTES = 512 * 1024
_REMOTE_RE = re.compile(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$")


class LocalSource(RepoSource):
    kind = "local"

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root).resolve()
        super().__init__(display_name=self.root.name, location=str(self.root))
        self._repo_error: str | None = None
        remote = self._remote_slug()
        if remote:
            self.display_name = remote

    def _list_paths(self) -> list[str]:
        out: list[str] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            rel_dir = Path(dirpath).relative_to(self.root)
            for name in filenames:
                out.append((rel_dir / name).as_posix())
        return out

    def _read(self, path: str) -> str | None:
        target = self.root / path
        try:
            if target.stat().st_size > MAX_READ_BYTES:
                return None
            return target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    def _git(self, *args: str) -> str:
        self._ensure_repo_root()
        return self._run_git(*args)

    def _ensure_repo_root(self) -> None:
        """Only use git data when this directory is itself the repository root.

        Otherwise a plain folder inside another repository (e.g. a home directory
        that is accidentally a git repo) would be reported with the parent's history.
        """
        if self._repo_error is None:
            try:
                top = Path(self._run_git("rev-parse", "--show-toplevel").strip()).resolve()
            except SourceUnavailable as exc:
                self._repo_error = str(exc)
            else:
                same = os.path.normcase(str(top)) == os.path.normcase(str(self.root))
                self._repo_error = (
                    ""
                    if same
                    else (f"not the root of a git repository (it is inside the repository at {top})")
                )
        if self._repo_error:
            raise SourceUnavailable(self._repo_error)

    def _run_git(self, *args: str) -> str:
        try:
            proc = subprocess.run(
                ["git", "-C", str(self.root), *args],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise SourceUnavailable("git is not installed") from exc
        if proc.returncode != 0:
            msg = proc.stderr.strip().splitlines()
            raise SourceUnavailable(msg[-1].removeprefix("fatal: ") if msg else "not a git repository")
        return proc.stdout

    def _remote_slug(self) -> str | None:
        try:
            url = self._git("remote", "get-url", "origin").strip()
        except SourceUnavailable:
            return None
        m = _REMOTE_RE.search(url)
        return m.group(1) if m else None

    def commits(self, since: datetime) -> list[Commit]:
        out = self._git(
            "log",
            "--no-merges",
            f"--since={since.isoformat()}",
            "--format=%aN%x1f%aE%x1f%aI",
        )
        commits: list[Commit] = []
        for line in out.splitlines():
            parts = line.split("\x1f")
            if len(parts) != 3:
                continue
            name, email, date = parts
            when = parse_iso(date)
            if when is None:
                continue
            commits.append(Commit(identity=(email or name).lower(), name=name, date=when))
        return commits

    def releases(self) -> list[Release]:
        out = self._git(
            "for-each-ref",
            "--sort=-creatordate",
            "--format=%(refname:short)\x1f%(creatordate:iso-strict)",
            "refs/tags",
        )
        rels: list[Release] = []
        for line in out.splitlines():
            tag, _, date = line.partition("\x1f")
            if tag:
                rels.append(Release(tag=tag, date=parse_iso(date), kind="tag"))
        return rels

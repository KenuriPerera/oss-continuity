from __future__ import annotations

import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from oss_continuity.analyzers.common import Context

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


def write_files(root: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


@pytest.fixture
def ctx() -> Context:
    return Context(now=NOW)


@pytest.fixture
def make_repo(tmp_path):
    def _make(files: dict[str, str]) -> Path:
        return write_files(tmp_path, files)

    return _make


requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def git(root: Path, *args: str, env: dict | None = None) -> None:
    import os

    full_env = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        **(env or {}),
    }
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, env=full_env)


def commit_as(root: Path, name: str, email: str, when: str, message: str) -> None:
    with (root / "log.txt").open("a", encoding="utf-8") as fh:
        fh.write(message + "\n")
    git(root, "add", "-A")
    env = {
        "GIT_AUTHOR_NAME": name,
        "GIT_AUTHOR_EMAIL": email,
        "GIT_AUTHOR_DATE": when,
        "GIT_COMMITTER_NAME": name,
        "GIT_COMMITTER_EMAIL": email,
        "GIT_COMMITTER_DATE": when,
    }
    git(root, "commit", "-q", "-m", message, env=env)

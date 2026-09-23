"""Helpers shared by analyzers and draft generators."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..model import Check, Status
from ..source import RepoSource

DRAFT_MARKER = "<!-- oss-continuity:draft -->"
DOC_DIRS = ("", ".github/", "docs/", "doc/")
DOC_EXTS = ("", ".md", ".markdown", ".rst", ".txt", ".adoc")

MANIFESTS = {
    "pyproject.toml": "Python project (pyproject)",
    "setup.py": "Python project (setuptools)",
    "setup.cfg": "Python project (setuptools config)",
    "requirements.txt": "Python requirements",
    "package.json": "Node.js package",
    "Cargo.toml": "Rust crate (Cargo)",
    "go.mod": "Go module",
    "pom.xml": "Java project (Maven)",
    "build.gradle": "JVM project (Gradle)",
    "build.gradle.kts": "JVM project (Gradle Kotlin DSL)",
    "Gemfile": "Ruby project (Bundler)",
    "composer.json": "PHP project (Composer)",
    "CMakeLists.txt": "C/C++ project (CMake)",
    "mix.exs": "Elixir project (Mix)",
    "pubspec.yaml": "Dart/Flutter project",
    "Makefile": "Make targets",
    "justfile": "just recipes",
    "Taskfile.yml": "Task runner",
    "tox.ini": "tox environments",
    "noxfile.py": "nox sessions",
    "Dockerfile": "Docker image",
    "docker-compose.yml": "Docker Compose services",
    "compose.yaml": "Docker Compose services",
}

_MD_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_UNDERLINE = re.compile(r"^([=\-~^\"`'*+#])\1{2,}\s*$")


@dataclass
class Context:
    now: datetime
    window_days: int = 365
    recent_days: int = 90
    facts: dict[str, Any] = field(default_factory=dict)


def find_doc(source: RepoSource, basenames: Iterable[str], dirs: Iterable[str] = DOC_DIRS) -> list[str]:
    dirs = tuple(dirs)
    return source.find(*[d + b + e for d in dirs for b in basenames for e in DOC_EXTS])


def is_draft(source: RepoSource, path: str) -> bool:
    return DRAFT_MARKER in (source.read_text(path) or "")


def split_drafts(source: RepoSource, paths: Iterable[str]) -> tuple[list[str], list[str]]:
    real, drafts = [], []
    for p in paths:
        (drafts if is_draft(source, p) else real).append(p)
    return real, drafts


def iter_headings(text: str) -> list[str]:
    """Markdown ATX/setext and reStructuredText headings, ignoring fenced code."""
    lines = text.splitlines()
    out: list[str] = []
    in_fence = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _MD_HEADING.match(line)
        if m:
            out.append(m.group(1).strip())
            continue
        if i > 0 and _UNDERLINE.match(line):
            prev = lines[i - 1]
            if prev.strip() and not _UNDERLINE.match(prev) and not prev.startswith((" ", "\t")):
                out.append(prev.strip())
    return out


def narrative_docs(source: RepoSource) -> list[str]:
    """Prose documents worth scanning for section headings (drafts excluded)."""
    docs = source.match(r"readme(\.[a-z]+)?")
    docs += find_doc(
        source, ["CONTRIBUTING", "DEVELOPMENT", "DEVELOPING", "HACKING", "MAINTAINERS", "MAINTAINING"]
    )
    docs += source.match(r"docs?/[^/]+\.(md|markdown|rst|adoc|txt)")[:30]
    seen: list[str] = []
    for d in docs:
        if d not in seen and not is_draft(source, d):
            seen.append(d)
    return seen


def heading_evidence(source: RepoSource, docs: Iterable[str], rx: re.Pattern[str]) -> list[str]:
    ev: list[str] = []
    for path in docs:
        for heading in iter_headings(source.read_text(path) or ""):
            if rx.search(heading):
                ev.append(f'section "{heading}" in {path}')
    return ev


def workflow_files(source: RepoSource) -> list[str]:
    files = source.match(r"\.github/workflows/[^/]+\.ya?ml")
    files += source.find(
        ".gitlab-ci.yml",
        ".circleci/config.yml",
        ".travis.yml",
        "azure-pipelines.yml",
        "Jenkinsfile",
        "bitbucket-pipelines.yml",
        ".drone.yml",
        ".woodpecker.yml",
    )
    files += source.match(r"\.buildkite/[^/]+\.ya?ml")
    return files


def humanize_age(then: datetime, now: datetime) -> str:
    days = (now - then).days
    if days < 1:
        return "today"
    if days < 2:
        return "1 day ago"
    if days < 60:
        return f"{days} days ago"
    if days < 730:
        return f"{days // 30} months ago"
    return f"{days // 365} years ago"


def who(identity: str, name: str) -> str:
    if not name or identity == name:
        return identity
    if "@" in identity:
        return f"{name} <{identity}>"
    return f"{name} (@{identity})"


def file_check(
    source: RepoSource,
    cid: str,
    label: str,
    paths: list[str],
    *,
    missing_evidence: str,
    remediation: str,
    artifact: str | None = None,
    missing_status: Status = Status.FAIL,
    extra_evidence: list[str] | None = None,
) -> Check:
    """Pass if a real (non-draft) file exists, warn on drafts, else missing_status.

    ``extra_evidence`` (e.g. matching section headings) also counts as present.
    """
    real, drafts = split_drafts(source, paths)
    extra = extra_evidence or []
    if real or extra:
        return Check(
            cid,
            label,
            Status.PASS,
            "documented" if extra and not real else "found",
            [f"found: {p}" for p in real] + extra[:5],
        )
    if drafts:
        return Check(
            cid,
            label,
            Status.WARN,
            "draft only",
            [f"{p} is an unfinished OSS Continuity draft (still contains the draft marker)" for p in drafts],
            f"Complete {drafts[0]} and remove its draft marker.",
            artifact,
        )
    return Check(cid, label, missing_status, "missing", [missing_evidence], remediation, artifact)

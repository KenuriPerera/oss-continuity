"""Operational continuity: CI, secrets, dependency updates and tests."""

from __future__ import annotations

import re

from ..model import Check, Section, Status
from ..source import RepoSource
from .common import Context, workflow_files

_SECRET_RX = re.compile(r"secrets\.([A-Za-z_][A-Za-z0-9_]*)|secrets\[\s*['\"]([^'\"]+)['\"]\s*\]")
_IMPLICIT = {"GITHUB_TOKEN"}
_TEST_RX = (
    r"(.+/)?(tests?|__tests__|specs?)/.+"
    r"|.+(_test\.go|\.test\.[cm]?[jt]sx?|\.spec\.[cm]?[jt]sx?|_spec\.rb)"
    r"|(.+/)?(test_[^/]+|[^/]+_test)\.py"
    r"|(.+/)?tests?\.([cm]?[jt]sx?|py)"
)
DEPENDENCY_BOTS = (
    ".github/dependabot.yml",
    ".github/dependabot.yaml",
    "renovate.json",
    "renovate.json5",
    ".renovaterc",
    ".renovaterc.json",
    ".github/renovate.json",
    ".github/renovate.json5",
    ".gitlab/renovate.json",
)


def find_secrets(source: RepoSource) -> dict[str, list[str]]:
    """Map secret name -> CI files that reference it (implicit tokens excluded)."""
    out: dict[str, list[str]] = {}
    for path in workflow_files(source):
        for m in _SECRET_RX.finditer(source.read_text(path) or ""):
            name = m.group(1) or m.group(2)
            if name and name not in _IMPLICIT:
                out.setdefault(name, [])
                if path not in out[name]:
                    out[name].append(path)
    return out


def _documentation_corpus(source: RepoSource) -> list[str]:
    docs = source.match(r"[^/]+\.(md|markdown|rst|txt|adoc)")
    docs += source.match(r"(\.github|docs?)/.+\.(md|markdown|rst|txt|adoc)")
    return docs[:80]


def analyze(source: RepoSource, ctx: Context) -> Section:
    checks: list[Check] = []

    ci = workflow_files(source)
    checks.append(
        Check("ci", "CI configuration", Status.PASS, f"{len(ci)} file(s)", [f"found: {p}" for p in ci])
        if ci
        else Check(
            "ci",
            "CI configuration",
            Status.FAIL,
            "missing",
            ["no CI configuration detected"],
            "Add CI that builds and tests the project so a new maintainer can trust changes.",
        )
    )

    secrets = find_secrets(source)
    if not secrets:
        checks.append(
            Check(
                "secrets_documented",
                "CI secrets documented",
                Status.PASS,
                "none referenced",
                ["CI configuration references no custom secrets"],
            )
        )
    else:
        corpus = {p: source.read_text(p) or "" for p in _documentation_corpus(source)}
        documented, undocumented, ev = [], [], []
        for name, paths in sorted(secrets.items()):
            where = [p for p, text in corpus.items() if re.search(rf"\b{re.escape(name)}\b", text)]
            if where:
                documented.append(name)
                ev.append(f"{name} (used in {', '.join(paths)}) is mentioned in {', '.join(where[:3])}")
            else:
                undocumented.append(name)
                ev.append(f"{name} (used in {', '.join(paths)}) is not mentioned in any document")
        status = Status.PASS if not undocumented else Status.WARN if documented else Status.FAIL
        checks.append(
            Check(
                "secrets_documented",
                "CI secrets documented",
                status,
                f"{len(documented)} of {len(secrets)}",
                ev,
                None
                if status is Status.PASS
                else f"Document what each CI secret is, who owns it and how to rotate it "
                f"(undocumented: {', '.join(undocumented)}).",
                None if status is Status.PASS else "MAINTAINER.md",
            )
        )

    bots = source.find(*DEPENDENCY_BOTS)
    checks.append(
        Check(
            "dependency_updates",
            "Dependency update process",
            Status.PASS,
            "configured",
            [f"found: {p}" for p in bots],
        )
        if bots
        else Check(
            "dependency_updates",
            "Dependency update process",
            Status.WARN,
            "not configured",
            ["no Dependabot or Renovate configuration found"],
            "Configure Dependabot or Renovate so dependency updates don't rely on one person noticing.",
        )
    )

    tests = source.match(_TEST_RX)
    checks.append(
        Check(
            "tests", "Automated tests", Status.PASS, f"{len(tests)} file(s)", [f"e.g. {p}" for p in tests[:3]]
        )
        if tests
        else Check(
            "tests",
            "Automated tests",
            Status.WARN,
            "not detected",
            ["no test directories or test files found"],
            "Add tests so a new maintainer can change code with confidence.",
        )
    )
    return Section("operations", "Operational continuity", checks)

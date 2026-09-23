"""Release continuity: could someone else cut the next release?"""

from __future__ import annotations

import re

from ..model import Check, Section, Status
from ..source import RepoSource, SourceUnavailable, prefer_version_tags
from .common import (
    Context,
    file_check,
    find_doc,
    heading_evidence,
    humanize_age,
    narrative_docs,
    workflow_files,
)

PUBLISH_PATTERNS: list[tuple[str, str]] = [
    (r"pypa/gh-action-pypi-publish", "PyPI publish action"),
    (r"\btwine\s+upload\b", "twine upload"),
    (r"\b(poetry|flit|hatch|uv)\s+publish\b", "Python package publish"),
    (r"\b(npm|pnpm|yarn)\s+(npm\s+)?publish\b", "npm publish"),
    (r"changesets/action", "Changesets release"),
    (r"semantic-release", "semantic-release"),
    (r"release-please", "release-please"),
    (r"\bcargo\s+publish\b", "cargo publish"),
    (r"goreleaser", "GoReleaser"),
    (r"\bgem\s+push\b", "RubyGems push"),
    (r"\bdotnet\s+nuget\s+push\b", "NuGet push"),
    (r"\bmvn\b[^\n]*\bdeploy\b", "Maven deploy"),
    (r"\bgradlew?\b[^\n]*\bpublish", "Gradle publish"),
    (r"docker/build-push-action", "container image publish"),
    (r"softprops/action-gh-release", "GitHub release action"),
    (r"\bgh\s+release\s+create\b", "gh release create"),
]
_PUBLISH = [(re.compile(p, re.IGNORECASE), label) for p, label in PUBLISH_PATTERNS]

RELEASE_RX = re.compile(
    r"\b(releas(e|es|ing)( process| procedure| checklist)?|publishing|cutting a release|"
    r"making a release)\b",
    re.IGNORECASE,
)
CHANGELOG_NAMES = ["CHANGELOG", "CHANGES", "HISTORY", "NEWS", "RELEASE_NOTES", "RELEASE-NOTES"]


def detect_publishing(source: RepoSource) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in workflow_files(source):
        text = source.read_text(path) or ""
        for rx, label in _PUBLISH:
            if rx.search(text) and (path, label) not in found:
                found.append((path, label))
    return found


def analyze(source: RepoSource, ctx: Context) -> Section:
    checks: list[Check] = [_latest_release(source, ctx)]

    process_files = find_doc(
        source, ["RELEASE", "RELEASING", "RELEASE_PROCESS", "RELEASE-PROCESS", "PUBLISHING"]
    )
    process_files += source.match(r"docs?/[^/]*releas[^/]*\.(md|rst|adoc|txt)")
    checks.append(
        file_check(
            source,
            "release_process",
            "Release process documented",
            list(dict.fromkeys(process_files)),
            missing_evidence="No RELEASE/RELEASING document or release section in the docs",
            remediation="Write down how a release is cut and published (RELEASE.md).",
            artifact="RELEASE.md",
            extra_evidence=heading_evidence(source, narrative_docs(source), RELEASE_RX),
        )
    )

    publishing = detect_publishing(source)
    if publishing:
        checks.append(
            Check(
                "automated_release",
                "Automated release",
                Status.PASS,
                ", ".join(sorted({label for _, label in publishing})),
                [f"{label} in {path}" for path, label in publishing],
            )
        )
    else:
        checks.append(
            Check(
                "automated_release",
                "Automated release",
                Status.WARN,
                "not detected",
                ["no CI workflow was found that publishes packages or creates releases"],
                "Automate publishing in CI so releasing does not depend on one person's machine "
                "and credentials.",
                "RELEASE.md",
            )
        )

    checks.append(
        file_check(
            source,
            "changelog",
            "Changelog",
            find_doc(source, CHANGELOG_NAMES, dirs=("", "docs/")),
            missing_evidence="No CHANGELOG, CHANGES, HISTORY or NEWS file",
            remediation="Keep a changelog so a successor can see what changed between releases.",
            artifact="CHANGELOG.md",
            missing_status=Status.WARN,
        )
    )
    return Section("releases", "Release continuity", checks)


def _latest_release(source: RepoSource, ctx: Context) -> Check:
    label = "Latest release"
    try:
        rels = prefer_version_tags(source.releases())
    except SourceUnavailable as exc:
        return Check(
            "latest_release",
            label,
            Status.UNKNOWN,
            "unavailable",
            [f"release information unavailable: {exc}"],
        )
    if not rels:
        return Check(
            "latest_release",
            label,
            Status.FAIL,
            "none",
            ["no GitHub releases or git tags found"],
            "Tag a release so a successor knows which version is the last known-good one.",
        )
    newest = rels[0]
    kind = "GitHub release" if newest.kind == "release" else "tag"
    ev = [
        f"{len(rels)} release(s)/tag(s) found; newest: {kind} {newest.tag}"
        + (f" on {newest.date.date().isoformat()}" if newest.date else "")
    ]
    ctx.facts["latest_release"] = {
        "tag": newest.tag,
        "kind": newest.kind,
        "date": newest.date.isoformat() if newest.date else None,
    }
    if newest.date is None:
        return Check("latest_release", label, Status.INFO, newest.tag, ev)
    days = (ctx.now - newest.date).days
    status = Status.PASS if days <= 180 else Status.WARN if days <= 365 else Status.FAIL
    rem = (
        None
        if status is Status.PASS
        else (
            "The last release is old: confirm the release process still works, or say in "
            "CONTINUITY.md that the project is feature-complete."
        )
    )
    return Check(
        "latest_release",
        label,
        status,
        f"{humanize_age(newest.date, ctx.now)} ({newest.tag})",
        ev,
        rem,
        "CONTINUITY.md" if rem else None,
    )

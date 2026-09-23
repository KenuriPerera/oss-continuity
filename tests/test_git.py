from __future__ import annotations

from datetime import timedelta

from conftest import NOW, commit_as, git, requires_git

from oss_continuity.core import build_report
from oss_continuity.local import LocalSource
from oss_continuity.model import Status


def _date(days_ago: int) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat()


@requires_git
def test_single_dominant_committer_fails(tmp_path, ctx):
    git(tmp_path, "init", "-q")
    for i in range(6):
        commit_as(tmp_path, "Alice", "alice@example.com", _date(200 - i), f"a{i}")
    commit_as(tmp_path, "Bob", "bob@example.com", _date(10), "b1")
    commit_as(
        tmp_path, "dependabot[bot]", "49699333+dependabot[bot]@users.noreply.github.com", _date(5), "bump"
    )
    git(tmp_path, "tag", "v1.0.0")

    report = build_report(LocalSource(tmp_path), ctx)
    primary = report.check("primary_committers")
    assert primary.status is Status.FAIL
    assert primary.summary == "1 of 2"
    assert "MAINTAINER.md" in report.missing_artifacts()
    assert report.facts["bot_commits"] == 1

    recent = report.check("recent_committers")
    assert recent.status is Status.WARN and recent.summary == "1"

    assert report.check("latest_release").summary.endswith("(v1.0.0)")


@requires_git
def test_three_balanced_committers_pass(tmp_path, ctx):
    git(tmp_path, "init", "-q")
    for person in ("ann", "ben", "cai", "dee", "eli"):
        for i in range(2):
            commit_as(tmp_path, person.title(), f"{person}@example.com", _date(20 + i), f"{person}{i}")
    report = build_report(LocalSource(tmp_path), ctx)
    assert report.check("primary_committers").status is Status.PASS
    assert report.check("recent_committers").status is Status.PASS


@requires_git
def test_old_history_is_outside_window(tmp_path, ctx):
    git(tmp_path, "init", "-q")
    commit_as(tmp_path, "Old", "old@example.com", _date(800), "ancient")
    report = build_report(LocalSource(tmp_path), ctx)
    assert report.check("primary_committers").status is Status.FAIL
    assert report.check("recent_committers").status is Status.FAIL
    assert report.check("latest_release").status is Status.FAIL  # no tags


@requires_git
def test_folder_inside_another_repository_does_not_borrow_its_history(tmp_path, ctx):
    git(tmp_path, "init", "-q")
    git(tmp_path, "remote", "add", "origin", "https://github.com/someone/other-project.git")
    commit_as(tmp_path, "Parent", "parent@example.com", _date(3), "parent commit")
    child = tmp_path / "child"
    child.mkdir()

    report = build_report(LocalSource(child), ctx)
    assert report.repository == "child"
    check = report.check("primary_committers")
    assert check.status is Status.UNKNOWN
    assert "not the root of a git repository" in check.evidence[0]

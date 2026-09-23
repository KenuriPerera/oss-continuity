from __future__ import annotations

import json

import pytest
from conftest import NOW

from oss_continuity.core import build_report
from oss_continuity.github import API, RAW, GitHubSource, parse_github_target
from oss_continuity.model import Status
from oss_continuity.source import SourceError


class FakeGitHub:
    def __init__(self, routes: dict[str, tuple[int, object]], headers: dict | None = None):
        self.routes = routes
        self.headers = headers or {}
        self.calls: list[str] = []

    def __call__(self, url, headers):
        self.calls.append(url)
        for prefix, (status, body) in self.routes.items():
            if url.startswith(prefix):
                data = body if isinstance(body, bytes) else json.dumps(body).encode()
                return status, self.headers, data
        return 404, {}, b""


def _commit(login, name, date, parents=1):
    return {
        "author": {"login": login} if login else None,
        "commit": {"author": {"name": name, "email": f"{name.lower()}@x.org", "date": date}},
        "parents": [{}] * parents,
    }


def base_routes(commits=None, releases=None, tags=None):
    slug = "acme/widget"
    return {
        f"{API}/repos/{slug}/git/trees/": (
            200,
            {
                "truncated": False,
                "tree": [
                    {"path": "README.md", "type": "blob"},
                    {"path": "LICENSE", "type": "blob"},
                    {"path": ".github/workflows/release.yml", "type": "blob"},
                    {"path": "src", "type": "tree"},
                ],
            },
        ),
        f"{API}/repos/{slug}/commits?": (200, commits if commits is not None else []),
        f"{API}/repos/{slug}/releases": (200, releases or []),
        f"{API}/repos/{slug}/tags": (200, tags or []),
        f"{API}/repos/{slug}/commits/abc": (200, {"commit": {"committer": {"date": "2026-08-01T00:00:00Z"}}}),
        f"{API}/repos/{slug}": (
            200,
            {"full_name": slug, "default_branch": "main", "archived": False, "stargazers_count": 5},
        ),
        f"{RAW}/{slug}/main/README.md": (200, b"# Widget\n\n## Getting started\n"),
        f"{RAW}/{slug}/main/.github/workflows/release.yml": (200, b"- run: npm publish\n"),
    }


@pytest.mark.parametrize(
    "target,expected",
    [
        ("owner/repo", "owner/repo"),
        ("https://github.com/owner/repo", "owner/repo"),
        ("https://github.com/owner/repo.git", "owner/repo"),
        ("https://github.com/owner/repo/tree/main/src", "owner/repo"),
        ("git@github.com:owner/repo.git", "owner/repo"),
        ("github.com/owner/my.repo", "owner/my.repo"),
        ("not a repo", None),
        ("https://gitlab.com/owner/repo", None),
        ("a/b/c", None),
    ],
)
def test_parse_target(target, expected):
    assert parse_github_target(target) == expected


def test_github_analysis_end_to_end(ctx):
    commits = [
        _commit("alice", "Alice", "2026-08-20T00:00:00Z"),
        _commit("bob", "Bob", "2026-08-10T00:00:00Z"),
        _commit(None, "Carol", "2026-07-01T00:00:00Z"),
        _commit("alice", "Alice", "2026-08-15T00:00:00Z", parents=2),
    ]  # merge: ignored
    releases = [{"tag_name": "v2.0.0", "published_at": "2026-08-01T00:00:00Z", "draft": False}]
    fake = FakeGitHub(base_routes(commits=commits, releases=releases))
    report = build_report(GitHubSource("acme/widget", http_get=fake, token="t"), ctx)

    assert report.source == "github"
    assert report.check("readme").status is Status.PASS
    assert report.check("dev_setup").status is Status.PASS
    assert report.check("automated_release").summary == "npm publish"
    assert report.check("primary_committers").status is Status.WARN  # 2 of 3
    assert report.check("latest_release").status is Status.PASS
    assert report.facts["commits_analyzed"] == 3
    assert report.facts["stars"] == 5
    identities = {c["identity"] for c in report.facts["top_committers"]}
    assert identities == {"alice", "bob", "carol@x.org"}
    # file contents come from raw.githubusercontent.com, not the API
    assert any(u.startswith(RAW) for u in fake.calls)


def test_tag_fallback_when_no_releases(ctx):
    fake = FakeGitHub(
        base_routes(
            tags=[{"name": "v1.0", "commit": {"sha": "abc"}}, {"name": "v0.9", "commit": {"sha": "def"}}]
        )
    )
    report = build_report(GitHubSource("acme/widget", http_get=fake), ctx)
    check = report.check("latest_release")
    assert check.status is Status.PASS
    assert "(v1.0)" in check.summary


def test_commit_sampling_is_reported(ctx):
    page = [_commit(f"user{i}", f"User{i}", "2026-08-01T00:00:00Z") for i in range(100)]
    fake = FakeGitHub(base_routes(commits=page))
    source = GitHubSource("acme/widget", http_get=fake, max_commits=150)
    report = build_report(source, ctx)
    assert report.facts["commits_analyzed"] == 150
    assert report.facts["commits_truncated"] is True
    assert any("sampled" in e for e in report.check("primary_committers").evidence)


def test_not_found():
    source = GitHubSource("acme/missing", http_get=FakeGitHub({}))
    with pytest.raises(SourceError, match="not found"):
        source.paths()


def test_rate_limit_message():
    fake = FakeGitHub({API: (403, {"message": "rate limit"})}, headers={"x-ratelimit-remaining": "0"})
    with pytest.raises(SourceError, match="GITHUB_TOKEN"):
        GitHubSource("acme/widget", http_get=fake).paths()


def test_archived_is_reported(ctx):
    routes = base_routes()
    routes[f"{API}/repos/acme/widget"] = (
        200,
        {"full_name": "acme/widget", "default_branch": "main", "archived": True},
    )
    report = build_report(GitHubSource("acme/widget", http_get=FakeGitHub(routes)), ctx)
    assert report.check("archived").status is Status.INFO


def test_now_fixture_is_timezone_aware():
    assert NOW.tzinfo is not None

from __future__ import annotations

from oss_continuity.analyzers.common import DRAFT_MARKER, iter_headings
from oss_continuity.core import build_report
from oss_continuity.local import LocalSource
from oss_continuity.model import Status

WELL_DOCUMENTED = {
    "README.md": "# Project\n\n## Development\n\nRun `make test`.\n",
    "CONTRIBUTING.md": "# Contributing\n",
    "ARCHITECTURE.md": "# Architecture\n",
    "RELEASE.md": "# Releasing\n\nPublishing uses the PYPI_API_TOKEN secret, owned by the core team.\n",
    "CHANGELOG.md": "# Changelog\n",
    "LICENSE": "MIT\n",
    "SECURITY.md": "Report privately.\n",
    "CONTINUITY.md": "# Continuity\n",
    "MAINTAINERS.md": "- alice\n",
    ".github/CODEOWNERS": "# owners\n* @alice @bob\n",
    ".github/dependabot.yml": "version: 2\n",
    ".github/workflows/ci.yml": "jobs:\n  test:\n    steps:\n      - run: pytest\n",
    ".github/workflows/release.yml": (
        "jobs:\n  publish:\n    steps:\n"
        "      - uses: pypa/gh-action-pypi-publish@release/v1\n"
        "        with:\n          password: ${{ secrets.PYPI_API_TOKEN }}\n"
        "      - run: echo ${{ secrets.GITHUB_TOKEN }}\n"
    ),
    "tests/test_core.py": "def test(): pass\n",
    "src/pkg/__init__.py": "",
}


def statuses(report):
    return {c.id: c.status for c in report.all_checks()}


def test_empty_repository(tmp_path, ctx):
    report = build_report(LocalSource(tmp_path), ctx)
    s = statuses(report)
    assert s["readme"] is Status.FAIL
    assert s["license"] is Status.FAIL
    assert s["codeowners"] is Status.FAIL
    assert s["primary_committers"] is Status.UNKNOWN  # not a git repository
    assert s["latest_release"] is Status.UNKNOWN
    assert s["continuity_doc"] is Status.WARN
    missing = report.missing_artifacts()
    for artifact in ("CODEOWNERS", "MAINTAINER.md", "RELEASE.md", "LICENSE", "CONTINUITY.md"):
        assert artifact in missing
    assert report.actions()


def test_well_documented_repository(make_repo, ctx):
    report = build_report(LocalSource(make_repo(WELL_DOCUMENTED)), ctx)
    s = statuses(report)
    for cid in (
        "readme",
        "contributing",
        "dev_setup",
        "architecture",
        "continuity_doc",
        "maintainers_doc",
        "codeowners",
        "release_process",
        "automated_release",
        "changelog",
        "ci",
        "secrets_documented",
        "dependency_updates",
        "tests",
        "license",
        "security_policy",
    ):
        assert s[cid] is Status.PASS, (cid, report.check(cid))
    assert "CODEOWNERS" not in report.missing_artifacts()


def test_evidence_is_specific(make_repo, ctx):
    report = build_report(LocalSource(make_repo(WELL_DOCUMENTED)), ctx)
    assert any("README.md" in e and "Development" in e for e in report.check("dev_setup").evidence)
    assert any(".github/workflows/release.yml" in e for e in report.check("automated_release").evidence)


def test_codeowners_with_only_comments_warns(make_repo, ctx):
    repo = make_repo({"CODEOWNERS": "# * @someone\n\n# more comments\n"})
    check = build_report(LocalSource(repo), ctx).check("codeowners")
    assert check.status is Status.WARN
    assert check.summary == "no active rules"


def test_draft_marker_is_not_counted_as_done(make_repo, ctx):
    repo = make_repo(
        {
            "MAINTAINER.md": f"# Maintainers\n{DRAFT_MARKER}\n",
            "RELEASE.md": f"{DRAFT_MARKER}\n# Release Process\n",
            "DEVELOPMENT.md": f"{DRAFT_MARKER}\n# Development Setup\n",
        }
    )
    s = statuses(build_report(LocalSource(repo), ctx))
    assert s["maintainers_doc"] is Status.WARN
    assert s["release_process"] is Status.WARN
    assert s["dev_setup"] is Status.WARN


def test_undocumented_secret(make_repo, ctx):
    repo = make_repo(
        {
            ".github/workflows/deploy.yml": (
                "env:\n  A: ${{ secrets.DEPLOY_KEY }}\n  B: ${{ secrets['NPM_TOKEN'] }}\n"
            ),
            "README.md": "Deploys need DEPLOY_KEY.\n",
        }
    )
    check = build_report(LocalSource(repo), ctx).check("secrets_documented")
    assert check.status is Status.WARN
    assert check.summary == "1 of 2"
    assert "NPM_TOKEN" in check.remediation


def test_all_secrets_undocumented_fails(make_repo, ctx):
    repo = make_repo({".github/workflows/x.yml": "k: ${{ secrets.SIGNING_KEY }}\n"})
    assert build_report(LocalSource(repo), ctx).check("secrets_documented").status is Status.FAIL


def test_tooling_without_docs_warns(make_repo, ctx):
    repo = make_repo({"README.md": "# X\n## Usage\n", "package.json": "{}"})
    check = build_report(LocalSource(repo), ctx).check("dev_setup")
    assert check.status is Status.WARN and check.summary == "tooling only"


def test_headings_inside_code_fences_are_ignored():
    text = "# Title\n```bash\n# Development\n```\nSetup\n=====\n"
    assert iter_headings(text) == ["Title", "Setup"]


def test_rst_headings(make_repo, ctx):
    repo = make_repo({"README.rst": "Project\n=======\n\nArchitecture\n------------\n"})
    assert build_report(LocalSource(repo), ctx).check("architecture").status is Status.PASS


def test_case_insensitive_file_names(make_repo, ctx):
    repo = make_repo({"readme.md": "x", "license": "MIT", ".github/security.md": "x", "test.js": "x"})
    s = statuses(build_report(LocalSource(repo), ctx))
    assert s["readme"] is s["license"] is s["security_policy"] is s["tests"] is Status.PASS


def test_skipped_directories(make_repo, ctx):
    repo = make_repo({"node_modules/dep/CONTRIBUTING.md": "x", "node_modules/dep/test/a.js": "x"})
    s = statuses(build_report(LocalSource(repo), ctx))
    assert s["contributing"] is Status.FAIL
    assert s["tests"] is Status.WARN


def test_json_shape(make_repo, ctx):
    data = build_report(LocalSource(make_repo(WELL_DOCUMENTED)), ctx).to_dict()
    assert data["schema_version"] == 1
    assert set(data) >= {
        "repository",
        "summary",
        "continuity",
        "missing_handoff_artifacts",
        "actions",
        "sections",
        "facts",
    }
    assert data["continuity"]["codeowners"] == "pass"


def test_existing_artifact_is_not_reported_missing(make_repo, ctx):
    # MAINTAINERS.md (alias) exists, but CI secret is undocumented and points at MAINTAINER.md
    repo = make_repo({"MAINTAINERS.md": "- alice\n", ".github/workflows/x.yml": "${{ secrets.KEY }}"})
    report = build_report(LocalSource(repo), ctx)
    assert report.check("secrets_documented").artifact == "MAINTAINER.md"
    assert "MAINTAINER.md" not in report.missing_artifacts()
    assert any("KEY" in a for a in report.actions())


def test_prefer_version_tags():
    from oss_continuity.source import Release, prefer_version_tags

    tags = [Release(t, None, "tag") for t in ("2.1.x", "latest", "v2.2.0", "pkg@1.4.0", "1.0rc1")]
    assert [r.tag for r in prefer_version_tags(tags)] == ["v2.2.0", "pkg@1.4.0", "1.0rc1"]
    only_odd = [Release("nightly", None, "tag")]
    assert prefer_version_tags(only_odd) == only_odd

from __future__ import annotations

import json

from conftest import write_files
from test_analysis import WELL_DOCUMENTED

from oss_continuity.analyzers.common import DRAFT_MARKER
from oss_continuity.cli import main
from oss_continuity.core import build_report
from oss_continuity.local import LocalSource
from oss_continuity.model import Status


def test_analyze_json(tmp_path, capsys):
    write_files(tmp_path, {"README.md": "# x\n"})
    assert main(["analyze", str(tmp_path), "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["continuity"]["readme"] == "pass"


def test_analyze_text_and_markdown(tmp_path, capsys):
    write_files(tmp_path, {"README.md": "# x\n"})
    main(["analyze", str(tmp_path), "--no-emoji", "--verbose"])
    out = capsys.readouterr().out
    assert "OSS Continuity Report" in out and "[xx]" in out and "found: README.md" in out
    main(["analyze", str(tmp_path), "--format", "markdown"])
    md = capsys.readouterr().out
    assert "## Maintainer continuity" in md and "| Status | Check |" in md


def test_output_file(tmp_path):
    out = tmp_path / "report.md"
    assert main(["analyze", str(tmp_path), "-f", "markdown", "-o", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("# OSS Continuity Report")


def test_check_exit_codes(tmp_path, capsys):
    assert main(["check", str(tmp_path)]) == 1  # empty repo has failures
    assert main(["check", str(tmp_path), "--fail-on", "never"]) == 0


def test_check_passes_on_warnings_by_default(tmp_path):
    repo = write_files(tmp_path, dict(WELL_DOCUMENTED))
    (repo / "CONTINUITY.md").unlink()  # -> warn only
    # not a git repo: history checks are "unknown", which never fails the check
    assert main(["check", str(repo)]) == 0
    assert main(["check", str(repo), "--fail-on", "warn"]) == 1


def test_bad_target(capsys):
    assert main(["analyze", "definitely not a target"]) == 2
    assert "neither a local directory" in capsys.readouterr().err


def test_init_creates_drafts_without_inventing(tmp_path, capsys):
    write_files(tmp_path, {"README.md": "# x\n", "package.json": '{"scripts": {"test": "vitest"}}'})
    assert main(["init", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "created" in out and "LICENSE" in out  # LICENSE listed as not generated

    release = (tmp_path / "RELEASE.md").read_text(encoding="utf-8")
    assert DRAFT_MARKER in release
    assert "does not currently contain enough information" in release
    assert "Needs maintainer input" in release

    dev = (tmp_path / "DEVELOPMENT.md").read_text(encoding="utf-8")
    assert "`test`" in dev and "package.json" in dev

    codeowners = (tmp_path / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
    assert all(line.startswith("#") or not line.strip() for line in codeowners.splitlines())
    assert not (tmp_path / "LICENSE").exists()


def test_drafts_are_reported_as_unfinished(tmp_path):
    write_files(tmp_path, {"README.md": "# x\n"})
    main(["init", str(tmp_path)])
    report = build_report(LocalSource(tmp_path))
    for cid in ("maintainers_doc", "release_process", "architecture", "continuity_doc", "contributing"):
        assert report.check(cid).status is Status.WARN, cid
        assert report.check(cid).summary == "draft only"
    assert report.check("codeowners").summary == "no active rules"


def test_init_never_overwrites_without_force(tmp_path, capsys):
    write_files(tmp_path, {"RELEASE.md": f"{DRAFT_MARKER}\nmine\n"})
    main(["init", str(tmp_path), "--only", "RELEASE.md"])
    assert (tmp_path / "RELEASE.md").read_text(encoding="utf-8").endswith("mine\n")
    assert "skipped (exists)" in capsys.readouterr().out
    main(["init", str(tmp_path), "--only", "RELEASE.md", "--force"])
    assert "Release Process" in (tmp_path / "RELEASE.md").read_text(encoding="utf-8")


def test_init_dry_run_writes_nothing(tmp_path, capsys):
    main(["init", str(tmp_path), "--dry-run"])
    assert "would create" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


def test_release_draft_uses_evidence(tmp_path):
    write_files(
        tmp_path,
        {
            ".github/workflows/publish.yml": "- uses: pypa/gh-action-pypi-publish@release/v1\n"
            "  env: {T: '${{ secrets.PYPI_TOKEN }}'}\n",
            "CHANGES.md": "x",
            "pyproject.toml": "[project]\n",
        },
    )
    main(["init", str(tmp_path), "--only", "RELEASE.md,CONTINUITY.md,MAINTAINER.md"])
    release = (tmp_path / "RELEASE.md").read_text(encoding="utf-8")
    assert "PyPI publish action in `.github/workflows/publish.yml`" in release
    assert "`CHANGES.md`" in release and "`pyproject.toml`" in release
    assert "PYPI_TOKEN" in (tmp_path / "CONTINUITY.md").read_text(encoding="utf-8")
    assert "PYPI_TOKEN" in (tmp_path / "MAINTAINER.md").read_text(encoding="utf-8")

"""Knowledge continuity: could a newcomer understand, build and change the project?"""

from __future__ import annotations

import re

from ..model import Check, Section, Status
from ..source import RepoSource
from .common import (
    MANIFESTS,
    Context,
    file_check,
    find_doc,
    heading_evidence,
    narrative_docs,
    split_drafts,
)

DEV_RX = re.compile(
    r"\b(develop(ment|ing|er setup|er guide)?|getting started|set ?up|setting up|"
    r"local (dev|development|environment)|build(ing)? from source|install(ing|ation)? from source|"
    r"hacking|running (the )?tests|contributing code)\b",
    re.IGNORECASE,
)
ARCH_RX = re.compile(
    r"\b(architecture|internals|design overview|project (structure|layout)|"
    r"code (structure|layout|organi[sz]ation)|repository (structure|layout)|how it works)\b",
    re.IGNORECASE,
)


def analyze(source: RepoSource, ctx: Context) -> Section:
    docs = narrative_docs(source)
    checks: list[Check] = [
        file_check(
            source,
            "readme",
            "README",
            source.match(r"readme(\.[a-z]+)?"),
            missing_evidence="No README in the repository root",
            remediation="Add a README describing what the project does and how to use it.",
            artifact="README.md",
        ),
        file_check(
            source,
            "contributing",
            "Contribution guide",
            find_doc(source, ["CONTRIBUTING"]),
            missing_evidence="No CONTRIBUTING file in the root, .github/, docs/ or doc/",
            remediation="Add CONTRIBUTING.md explaining how changes are proposed, reviewed and merged.",
            artifact="CONTRIBUTING.md",
        ),
        _dev_setup(source, docs),
        _architecture(source, docs),
        file_check(
            source,
            "continuity_doc",
            "Continuity / handoff plan",
            source.find(
                "CONTINUITY.md",
                ".github/CONTINUITY.md",
                "docs/CONTINUITY.md",
                "continuity.yaml",
                "continuity.yml",
                ".continuity.yaml",
                ".continuity.yml",
            ),
            missing_evidence="No CONTINUITY.md or continuity.yaml found",
            remediation="Add CONTINUITY.md: project status, who can take over, and which "
            "accounts and credentials a successor needs.",
            artifact="CONTINUITY.md",
            missing_status=Status.WARN,
        ),
    ]
    return Section("knowledge", "Knowledge continuity", checks)


def _dev_setup(source: RepoSource, docs: list[str]) -> Check:
    files = find_doc(source, ["DEVELOPMENT", "DEVELOPING", "DEVELOPER", "HACKING"])
    files += source.find(".devcontainer.json", ".devcontainer/devcontainer.json")
    real, drafts = split_drafts(source, files)
    headings = heading_evidence(source, docs, DEV_RX)
    if real or headings or drafts:
        return file_check(
            source,
            "dev_setup",
            "Development setup",
            files,
            missing_evidence="",
            remediation="",
            artifact="DEVELOPMENT.md",
            extra_evidence=headings,
        )
    tooling = source.find(*MANIFESTS)
    if tooling:
        return Check(
            "dev_setup",
            "Development setup",
            Status.WARN,
            "tooling only",
            [f"build tooling found ({', '.join(tooling)}) but no written setup instructions"],
            "Write down how to set up a development environment and run the tests "
            "(DEVELOPMENT.md or a section in CONTRIBUTING.md).",
            "DEVELOPMENT.md",
        )
    return Check(
        "dev_setup",
        "Development setup",
        Status.FAIL,
        "missing",
        ["no setup documentation, devcontainer or recognised build tooling found"],
        "Document how to build the project and run its tests.",
        "DEVELOPMENT.md",
    )


def _architecture(source: RepoSource, docs: list[str]) -> Check:
    files = find_doc(source, ["ARCHITECTURE", "DESIGN", "INTERNALS"])
    files += source.match(r"(docs?/)?(adr|adrs|decisions|architecture)/[^/]+\.(md|rst|adoc|txt)")[:3]
    files += source.match(r"docs?/(architecture|design|internals)[^/]*\.(md|rst|adoc|txt)")
    return file_check(
        source,
        "architecture",
        "Architecture documented",
        list(dict.fromkeys(files)),
        missing_evidence="No ARCHITECTURE/DESIGN document, ADR directory or architecture section found",
        remediation="Describe the main components and how they fit together in ARCHITECTURE.md.",
        artifact="ARCHITECTURE.md",
        extra_evidence=heading_evidence(source, docs, ARCH_RX),
    )

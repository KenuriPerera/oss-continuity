"""Governance: licence and security policy a successor must honour."""

from __future__ import annotations

from ..model import Section, Status
from ..source import RepoSource
from .common import Context, file_check, find_doc


def analyze(source: RepoSource, ctx: Context) -> Section:
    licenses = source.match(r"(licen[cs]e|copying)([-._][^/]*)?") + source.match(r"licenses?/.+")[:3]
    checks = [
        file_check(
            source,
            "license",
            "License",
            licenses,
            missing_evidence="No LICENSE or COPYING file in the repository root",
            remediation="Choose and add a license (https://choosealicense.com); without one, "
            "nobody else may legally continue the project.",
            artifact="LICENSE",
        ),
        file_check(
            source,
            "security_policy",
            "Security policy",
            find_doc(source, ["SECURITY"]),
            missing_evidence="No SECURITY policy in the root, .github/, docs/ or doc/",
            remediation="Add SECURITY.md with a private way to report vulnerabilities.",
            artifact="SECURITY.md",
            missing_status=Status.WARN,
        ),
    ]
    return Section("governance", "Governance", checks)

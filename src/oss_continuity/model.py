"""Data model for continuity reports.

A report is a list of sections, each holding checks. Every check carries a
status, a short human-readable result, the evidence it was derived from and,
when something is missing, a remediation and the handoff artifact that would
resolve it. There is deliberately no aggregate score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_VERSION = 1


class Status(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    INFO = "info"
    UNKNOWN = "unknown"


# Each handoff artifact is "present" when the check that looks for it passes.
# Other checks may point at an artifact as the place to record something
# (e.g. a backup maintainer in MAINTAINER.md) without the artifact being missing.
ARTIFACT_OWNERS = {
    "README.md": "readme",
    "CONTRIBUTING.md": "contributing",
    "DEVELOPMENT.md": "dev_setup",
    "ARCHITECTURE.md": "architecture",
    "CONTINUITY.md": "continuity_doc",
    "MAINTAINER.md": "maintainers_doc",
    "CODEOWNERS": "codeowners",
    "RELEASE.md": "release_process",
    "CHANGELOG.md": "changelog",
    "LICENSE": "license",
    "SECURITY.md": "security_policy",
}

# Lower number = more severe. Used for ordering actions and --fail-on.
SEVERITY = {
    Status.FAIL: 0,
    Status.WARN: 1,
    Status.UNKNOWN: 2,
    Status.INFO: 3,
    Status.PASS: 4,
}


@dataclass
class Check:
    id: str
    label: str
    status: Status
    summary: str = ""
    evidence: list[str] = field(default_factory=list)
    remediation: str | None = None
    artifact: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "status": self.status.value,
            "summary": self.summary,
            "evidence": list(self.evidence),
            "remediation": self.remediation,
            "artifact": self.artifact,
        }


@dataclass
class Section:
    id: str
    title: str
    checks: list[Check]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "checks": [c.to_dict() for c in self.checks],
        }


@dataclass
class Report:
    repository: str
    source: str
    location: str
    generated_at: str
    tool_version: str
    sections: list[Section]
    facts: dict[str, Any] = field(default_factory=dict)

    def all_checks(self) -> list[Check]:
        return [c for s in self.sections for c in s.checks]

    def check(self, check_id: str) -> Check | None:
        for c in self.all_checks():
            if c.id == check_id:
                return c
        return None

    def counts(self) -> dict[str, int]:
        out = {s.value: 0 for s in Status}
        for c in self.all_checks():
            out[c.status.value] += 1
        return out

    def _problems(self) -> list[Check]:
        problems = [c for c in self.all_checks() if c.status in (Status.FAIL, Status.WARN)]
        return sorted(problems, key=lambda c: SEVERITY[c.status])

    def artifact_present(self, artifact: str) -> bool:
        owner = self.check(ARTIFACT_OWNERS.get(artifact, ""))
        return owner is not None and owner.status is Status.PASS

    def missing_artifacts(self) -> list[str]:
        seen: list[str] = []
        for c in self._problems():
            if c.artifact and c.artifact not in seen and not self.artifact_present(c.artifact):
                seen.append(c.artifact)
        return seen

    def actions(self) -> list[str]:
        seen: list[str] = []
        for c in self._problems():
            if c.remediation and c.remediation not in seen:
                seen.append(c.remediation)
        return seen

    def worst_severity(self) -> int:
        return min((SEVERITY[c.status] for c in self.all_checks()), default=SEVERITY[Status.PASS])

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "tool": {"name": "oss-continuity", "version": self.tool_version},
            "repository": self.repository,
            "source": self.source,
            "location": self.location,
            "generated_at": self.generated_at,
            "summary": self.counts(),
            "continuity": {c.id: c.status.value for c in self.all_checks()},
            "missing_handoff_artifacts": self.missing_artifacts(),
            "actions": self.actions(),
            "sections": [s.to_dict() for s in self.sections],
            "facts": self.facts,
        }

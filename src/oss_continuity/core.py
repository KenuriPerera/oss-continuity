"""Run all analyzers against a source and assemble a report."""

from __future__ import annotations

from datetime import datetime, timezone

from . import __version__
from .analyzers import ANALYZERS
from .analyzers.common import Context
from .model import Report
from .source import RepoSource


def build_report(source: RepoSource, ctx: Context | None = None) -> Report:
    ctx = ctx or Context(now=datetime.now(timezone.utc))
    sections = [module.analyze(source, ctx) for module in ANALYZERS]
    facts = {**source.facts(), **ctx.facts, "files_scanned": len(source.paths())}
    return Report(
        repository=source.display_name,
        source=source.kind,
        location=source.location,
        generated_at=ctx.now.replace(microsecond=0).isoformat(),
        tool_version=__version__,
        sections=sections,
        facts=facts,
    )

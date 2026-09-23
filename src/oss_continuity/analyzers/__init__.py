"""Continuity analyzers. Each module exposes ``analyze(source, ctx) -> Section``."""

from . import governance, knowledge, maintainers, operations, releases

ANALYZERS = (maintainers, knowledge, releases, operations, governance)

__all__ = ["ANALYZERS"]

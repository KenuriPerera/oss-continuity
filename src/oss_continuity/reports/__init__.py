"""Report renderers."""

from .json import render_json
from .markdown import render_markdown
from .text import render_text

FORMATS = ("text", "markdown", "json")


def render(report, fmt: str = "text", *, verbose: bool = False, emoji: bool = True) -> str:
    if fmt == "json":
        return render_json(report)
    if fmt == "markdown":
        return render_markdown(report, emoji=emoji)
    return render_text(report, verbose=verbose, emoji=emoji)


__all__ = ["FORMATS", "render", "render_json", "render_markdown", "render_text"]

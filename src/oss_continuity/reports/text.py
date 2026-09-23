from __future__ import annotations

from ..model import Report, Status

SYMBOLS = {Status.PASS: "✅", Status.WARN: "⚠️ ", Status.FAIL: "❌", Status.INFO: "ℹ️ ", Status.UNKNOWN: "❔"}
ASCII = {
    Status.PASS: "[ok]",
    Status.WARN: "[!!]",
    Status.FAIL: "[xx]",
    Status.INFO: "[i] ",
    Status.UNKNOWN: "[??]",
}
ICONS = {"maintainers": "🧑‍💻", "knowledge": "📚", "releases": "🚀", "operations": "🔧", "governance": "⚖️ "}


def summary_line(report: Report) -> str:
    counts = report.counts()
    parts = [
        f"{counts[s.value]} {s.value}"
        for s in (Status.PASS, Status.WARN, Status.FAIL, Status.UNKNOWN, Status.INFO)
        if counts[s.value]
    ]
    return " · ".join(parts)


def render_text(report: Report, *, verbose: bool = False, emoji: bool = True) -> str:
    sym = SYMBOLS if emoji else ASCII
    rule = ("─" if emoji else "-") * 52
    arrow = "→" if emoji else "->"
    width = max((len(c.label) for c in report.all_checks()), default=20) + 2

    lines = [
        "OSS Continuity Report",
        rule,
        "",
        f"Repository: {report.repository}",
        f"Source:     {report.source} ({report.location})",
        f"Generated:  {report.generated_at}",
        f"Checks:     {summary_line(report)}",
        "",
    ]
    for section in report.sections:
        icon = f"{ICONS.get(section.id, '')} " if emoji else ""
        lines.append(f"{icon}{section.title}")
        for c in section.checks:
            lines.append(f"   {sym[c.status]} {c.label.ljust(width)}{c.summary}")
            if verbose:
                lines.extend(f"         · {e}" for e in c.evidence)
        lines.append("")

    missing = report.missing_artifacts()
    lines.append(f"{'📦 ' if emoji else ''}Handoff readiness")
    lines.append(f"   Missing handoff items: {len(missing)}")
    lines.extend(f"     - {m}" for m in missing)
    lines.append("")

    actions = report.actions()
    if actions:
        lines.append("Recommended actions:")
        lines.extend(f"   {arrow} {a}" for a in actions)
    else:
        lines.append("No actions required.")
    if not verbose:
        lines += ["", "Run with --verbose to see the evidence behind each result."]
    return "\n".join(lines) + "\n"

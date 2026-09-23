"""Maintainer continuity: who carries the project, and is that written down?"""

from __future__ import annotations

from collections import Counter
from datetime import timedelta

from ..model import Check, Section, Status
from ..source import RepoSource, SourceUnavailable, is_bot
from .common import Context, file_check, find_doc, who


def _codeowners(source: RepoSource) -> Check:
    label = "CODEOWNERS configured"
    paths = source.find("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS")
    if not paths:
        return Check(
            "codeowners",
            label,
            Status.FAIL,
            "missing",
            ["No CODEOWNERS file in the root, .github/ or docs/"],
            "Add a CODEOWNERS file so review responsibility is explicit and survives turnover.",
            "CODEOWNERS",
        )
    path = paths[0]
    rules = [
        ln
        for ln in (source.read_text(path) or "").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    if not rules:
        return Check(
            "codeowners",
            label,
            Status.WARN,
            "no active rules",
            [f"{path} contains only comments"],
            f"Add real ownership rules to {path}.",
            "CODEOWNERS",
        )
    owners = sorted({tok for ln in rules for tok in ln.split()[1:] if "@" in tok})
    return Check(
        "codeowners",
        label,
        Status.PASS,
        f"{len(rules)} rule(s)",
        [f"{path}: {len(rules)} rule(s); owners: {', '.join(owners[:8]) or 'none listed'}"],
    )


def analyze(source: RepoSource, ctx: Context) -> Section:
    checks: list[Check] = []
    if source.facts().get("archived"):
        checks.append(
            Check(
                "archived",
                "Repository archived",
                Status.INFO,
                "yes",
                ["GitHub marks this repository as archived (read-only)"],
            )
        )

    since = ctx.now - timedelta(days=ctx.window_days)
    try:
        commits = source.commits(since)
        error = None
    except SourceUnavailable as exc:
        commits, error = None, str(exc)

    if commits is None:
        ev = [f"Commit history unavailable: {error}"]
        rem = "Run the analysis on a git clone or a GitHub repository to evaluate contributor activity."
        checks.append(
            Check("primary_committers", "Primary committers", Status.UNKNOWN, "unavailable", ev, rem)
        )
        checks.append(
            Check(
                "recent_committers",
                f"Active in last {ctx.recent_days} days",
                Status.UNKNOWN,
                "unavailable",
                ev,
                rem,
            )
        )
    else:
        checks.extend(_activity_checks(source, ctx, commits))

    maint = find_doc(source, ["MAINTAINERS", "MAINTAINER", "OWNERS", "GOVERNANCE"])
    checks.append(
        file_check(
            source,
            "maintainers_doc",
            "Maintainers documented",
            maint,
            missing_evidence="No MAINTAINERS, MAINTAINER, OWNERS or GOVERNANCE file found",
            remediation="List current maintainers, their responsibilities and a backup in MAINTAINER.md.",
            artifact="MAINTAINER.md",
        )
    )
    checks.append(_codeowners(source))
    return Section("maintainers", "Maintainer continuity", checks)


def _activity_checks(source: RepoSource, ctx: Context, commits: list) -> list[Check]:
    humans = [c for c in commits if not is_bot(c.identity, c.name)]
    counts = Counter(c.identity for c in humans)
    names: dict[str, str] = {}
    for c in humans:
        names.setdefault(c.identity, c.name)
    total = len(humans)
    window = ctx.window_days

    ctx.facts.update(
        commit_window_days=window,
        commits_analyzed=len(commits),
        bot_commits=len(commits) - total,
        commits_truncated=source.commits_truncated,
        top_committers=[
            {"identity": i, "name": names[i], "commits": n, "share": round(n / total, 3)}
            for i, n in counts.most_common(10)
        ],
    )
    note = (
        [f"only the {len(commits)} most recent commits were sampled (see --max-commits)"]
        if source.commits_truncated
        else []
    )
    checks: list[Check] = []

    if total == 0:
        checks.append(
            Check(
                "primary_committers",
                "Primary committers",
                Status.FAIL,
                "none",
                [f"No human commits in the last {window} days"] + note,
                "Confirm whether the project is still maintained and record its status in CONTINUITY.md.",
                "CONTINUITY.md",
            )
        )
    else:
        k = cum = 0
        for _, n in counts.most_common():
            k += 1
            cum += n
            if cum * 2 >= total:
                break
        status = Status.FAIL if k <= 1 else Status.WARN if k == 2 else Status.PASS
        ev = [
            f"{k} of {len(counts)} people authored at least half of the {total} human "
            f"commits in the last {window} days"
        ]
        ev += [f"{who(i, names[i])}: {n} commits ({n / total:.0%})" for i, n in counts.most_common(5)]
        rem = {
            Status.FAIL: "Knowledge is concentrated in one person: name a backup maintainer "
            "and record them in MAINTAINER.md.",
            Status.WARN: "Two people carry most of the work: name a backup maintainer and "
            "document who owns what in MAINTAINER.md.",
        }.get(status)
        checks.append(
            Check(
                "primary_committers",
                "Primary committers",
                status,
                f"{k} of {len(counts)}",
                ev + note,
                rem,
                "MAINTAINER.md" if rem else None,
            )
        )

    cutoff = ctx.now - timedelta(days=ctx.recent_days)
    recent = Counter(c.identity for c in humans if c.date >= cutoff)
    n = len(recent)
    status = Status.FAIL if n == 0 else Status.WARN if n == 1 else Status.PASS
    ev = [f"{who(i, names[i])}: {c} commit(s)" for i, c in recent.most_common(5)] or [
        f"No human commits since {cutoff.date().isoformat()}"
    ]
    if status is Status.FAIL:
        rem, art = (
            "Nobody has committed recently: record whether the project is active, "
            "maintenance-only or seeking maintainers in CONTINUITY.md.",
            "CONTINUITY.md",
        )
    elif status is Status.WARN:
        rem, art = (
            "Only one person is currently active: recruit or name a second maintainer.",
            "MAINTAINER.md",
        )
    else:
        rem, art = None, None
    checks.append(
        Check("recent_committers", f"Active in last {ctx.recent_days} days", status, str(n), ev, rem, art)
    )
    return checks

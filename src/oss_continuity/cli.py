"""Command-line interface: analyze, check and init."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .analyzers.common import Context
from .core import build_report
from .github import GitHubSource, parse_github_target
from .handoff import generate_drafts
from .local import LocalSource
from .model import SEVERITY, Report, Status
from .reports import FORMATS, render
from .source import RepoSource, SourceError

EXIT_OK, EXIT_CHECKS_FAILED, EXIT_ERROR = 0, 1, 2
FAIL_ON = {"fail": SEVERITY[Status.FAIL], "warn": SEVERITY[Status.WARN], "never": -1}


def resolve_source(target: str, max_commits: int = 300) -> RepoSource:
    if os.path.isdir(target):
        return LocalSource(target)
    slug = parse_github_target(target)
    if slug:
        return GitHubSource(slug, max_commits=max_commits)
    raise SourceError(f"'{target}' is neither a local directory nor a GitHub repository (owner/repo or URL)")


def _emoji_ok(stream) -> bool:
    try:
        "✅🧑‍💻".encode(getattr(stream, "encoding", None) or "ascii")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


def _report(args: argparse.Namespace, target: str) -> tuple[RepoSource, Report]:
    source = resolve_source(target, max_commits=args.max_commits)
    ctx = Context(now=datetime.now(timezone.utc), window_days=args.window_days, recent_days=args.recent_days)
    return source, build_report(source, ctx)


def _emit(args: argparse.Namespace, report: Report) -> None:
    to_file = bool(args.output)
    emoji = not args.no_emoji and (to_file or _emoji_ok(sys.stdout))
    text = render(report, args.format, verbose=args.verbose, emoji=emoji)
    if to_file:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(text)


def cmd_analyze(args: argparse.Namespace) -> int:
    _, report = _report(args, args.target)
    _emit(args, report)
    return EXIT_OK


def cmd_check(args: argparse.Namespace) -> int:
    _, report = _report(args, args.target)
    _emit(args, report)
    threshold = FAIL_ON[args.fail_on]
    return EXIT_CHECKS_FAILED if report.worst_severity() <= threshold else EXIT_OK


def cmd_init(args: argparse.Namespace) -> int:
    source, report = _report(args, args.target)
    if args.output_dir:
        out_dir = Path(args.output_dir)
    elif isinstance(source, LocalSource):
        out_dir = source.root
    else:
        out_dir = Path("continuity-drafts") / report.repository.replace("/", "__")
    only = [s.strip() for s in args.only.split(",")] if args.only else None
    results = generate_drafts(source, report, out_dir, only=only, force=args.force, dry_run=args.dry_run)
    if not results:
        print("No handoff artifacts are missing; nothing to generate.")
        return EXIT_OK
    labels = {
        "created": "created",
        "overwritten": "overwritten",
        "would-create": "would create",
        "exists": "skipped (exists)",
        "unsupported": "not generated",
    }
    for r in results:
        where = f" {r.path}" if r.path else ""
        note = f": {r.note}" if r.note else ""
        print(f"{labels[r.action]:<18}{r.artifact}{where}{note}")
    if any(r.action in ("created", "overwritten") for r in results):
        print(
            "\nDrafts contain only evidence-backed facts plus questions marked "
            "'Needs maintainer input'.\nThey are reported as 'draft only' until a maintainer "
            "completes them and removes the draft marker."
        )
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oss-continuity",
        description="Could someone else take over this open-source project? "
        "Evidence-based maintainer handoff analysis.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--max-commits", type=int, default=300, help="GitHub only: maximum commits to sample (default: 300)"
    )
    common.add_argument(
        "--window-days", type=int, default=365, help="history window for contributor analysis (default: 365)"
    )
    common.add_argument(
        "--recent-days", type=int, default=90, help="window for 'recently active' (default: 90)"
    )

    output = argparse.ArgumentParser(add_help=False)
    output.add_argument("--format", "-f", choices=FORMATS, default="text")
    output.add_argument("--output", "-o", help="write the report to a file instead of stdout")
    output.add_argument("--verbose", "-v", action="store_true", help="show evidence (text format)")
    output.add_argument("--no-emoji", action="store_true", help="ASCII-only output")

    p = sub.add_parser(
        "analyze",
        parents=[common, output],
        help="analyse a GitHub repository (owner/repo or URL) or a local path",
    )
    p.add_argument("target")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser(
        "check", parents=[common, output], help="analyse and exit non-zero on problems (for CI)"
    )
    p.add_argument("target", nargs="?", default=".")
    p.add_argument(
        "--fail-on",
        choices=list(FAIL_ON),
        default="fail",
        help="exit 1 if any check is at this level or worse (default: fail)",
    )
    p.set_defaults(func=cmd_check)

    p = sub.add_parser(
        "init", parents=[common], help="generate draft handoff documents for missing artifacts"
    )
    p.add_argument("target", nargs="?", default=".")
    p.add_argument(
        "--output-dir",
        help="where to write drafts (default: the repository itself "
        "for local paths, ./continuity-drafts/<repo> for GitHub)",
    )
    p.add_argument("--only", help="comma-separated artifacts to generate, e.g. RELEASE.md,CODEOWNERS")
    p.add_argument("--force", action="store_true", help="overwrite existing files")
    p.add_argument("--dry-run", action="store_true", help="show what would be written")
    p.set_defaults(func=cmd_init)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except SourceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except KeyboardInterrupt:
        return 130

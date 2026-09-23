# oss-continuity

**If the current maintainer disappeared tomorrow, could someone else actually take over this project?**

`oss-continuity` inspects a GitHub repository or a local checkout and reports, with evidence,
whether the information a successor would need is actually written down: who maintains it,
how it is built, how it is released, which credentials CI depends on, and what is missing.
It can then generate **draft handoff documents** that contain only facts derived from the
repository plus explicit questions for the maintainer. It never invents answers.

```text
OSS Continuity Report
────────────────────────────────────────────────────

Repository: sindresorhus/slugify
Checks:     8 pass · 5 warn · 6 fail

🧑‍💻 Maintainer continuity
   ❌ Primary committers          1 of 2
   ✅ Active in last 90 days      2
   ❌ Maintainers documented      missing
   ❌ CODEOWNERS configured       missing

📚 Knowledge continuity
   ✅ README                      found
   ❌ Contribution guide          missing
   ⚠️  Development setup           tooling only
   ...

📦 Handoff readiness
   Missing handoff items: 8
```

## Why this exists

Existing tools answer different questions. The
[OpenSSF Criticality Score](https://github.com/ossf/criticality_score) estimates how *important*
a project is; the [OpenSSF Scorecard](https://github.com/ossf/scorecard) assesses its *security
posture*; bus-factor and health dashboards measure *activity*. None of them answers the practical
handoff question: is the knowledge needed to keep the project going recorded anywhere other than
in one person's head?

`oss-continuity` focuses narrowly on that question.

### Design principles

1. **No aggregate score.** A number like "87/100" hides what is actually missing. Every result is a
   status plus the evidence it came from (file paths, section headings, commit counts, workflow
   lines) and, when something is missing, a concrete remediation.
2. **Never invent information.** `init` writes drafts that contain only evidence-backed facts, each
   naming its source, and questions marked **Needs maintainer input**.
3. **Drafts don't count as done.** Generated drafts carry a marker comment. Until a maintainer
   completes the document and removes the marker, the check reports `draft only` rather than pass.
4. **Machine-readable output.** `--format json` gives a stable, versioned structure for CI,
   dashboards and other tools.
5. **Zero runtime dependencies.** Standard library only.

## Installation

```bash
pip install .            # from a clone of this repository
# or, once published:
pip install oss-continuity
```

Requires Python 3.9+. Local analysis of history needs `git` on your `PATH`.

## Usage

```bash
# Analyse a GitHub repository (slug or URL)
oss-continuity analyze owner/repository
oss-continuity analyze https://github.com/owner/repository --verbose   # show evidence

# Analyse a local checkout
oss-continuity analyze path/to/repo

# Other formats
oss-continuity analyze owner/repository --format json
oss-continuity analyze owner/repository --format markdown -o report.md

# CI gate: exit 1 when any check fails (or use --fail-on warn / never)
oss-continuity check .

# Generate draft handoff documents for whatever is missing
oss-continuity init .                          # writes into the repository
oss-continuity init owner/repository           # writes to ./continuity-drafts/owner__repository
oss-continuity init . --dry-run                # preview
oss-continuity init . --only RELEASE.md,CODEOWNERS
```

GitHub analysis uses the REST API (about 5 to 8 calls per repository; file contents come from
`raw.githubusercontent.com` and don't count against the limit). Unauthenticated use is limited to
60 API calls per hour, so for regular use set a token:

```bash
export GITHUB_TOKEN=ghp_...   # or GH_TOKEN; no scopes needed for public repositories
```

For large, busy repositories, analysing a local clone is often faster and uses full history.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success (for `check`: nothing at or above the `--fail-on` level) |
| 1 | `check` found a problem at or above the `--fail-on` level |
| 2 | The repository could not be analysed (not found, rate limited, bad target) |

## What is checked

| Area | Check ID | What it looks for |
|---|---|---|
| Maintainers | `primary_committers` | How many people author half of human commits in the window (bots excluded) |
| | `recent_committers` | Distinct human committers in the last 90 days |
| | `maintainers_doc` | `MAINTAINERS`, `MAINTAINER`, `OWNERS`, `GOVERNANCE` |
| | `codeowners` | `CODEOWNERS` with at least one active (non-comment) rule |
| Knowledge | `readme` | README in the root |
| | `contributing` | `CONTRIBUTING` in root, `.github/`, `docs/`, `doc/` |
| | `dev_setup` | `DEVELOPMENT`/`HACKING` docs, devcontainer, or a setup/development section heading |
| | `architecture` | `ARCHITECTURE`/`DESIGN` docs, ADR directories, or an architecture section heading |
| | `continuity_doc` | `CONTINUITY.md` or `continuity.yaml` |
| Releases | `latest_release` | Age of the newest GitHub release or git tag |
| | `release_process` | `RELEASE`/`RELEASING` docs or a release section heading |
| | `automated_release` | CI steps that publish (PyPI, npm, crates.io, GoReleaser, release-please, ...) |
| | `changelog` | `CHANGELOG`, `CHANGES`, `HISTORY`, `NEWS` |
| Operations | `ci` | GitHub Actions, GitLab CI, CircleCI, Travis, Azure, Jenkins, Buildkite, ... |
| | `secrets_documented` | Every `secrets.X` used in CI is mentioned in some document |
| | `dependency_updates` | Dependabot or Renovate configuration |
| | `tests` | Test directories or test files |
| Governance | `license` | `LICENSE` / `COPYING` |
| | `security_policy` | `SECURITY` policy |

Full details, thresholds and known limitations: [docs/checks.md](docs/checks.md).

### JSON output

```json
{
  "schema_version": 1,
  "repository": "owner/project",
  "summary": {"pass": 9, "warn": 4, "fail": 5, "info": 0, "unknown": 0},
  "continuity": {"codeowners": "fail", "release_process": "fail", "contributing": "pass"},
  "missing_handoff_artifacts": ["MAINTAINER.md", "CODEOWNERS", "RELEASE.md"],
  "actions": ["..."],
  "sections": [{"id": "maintainers", "checks": [{"id": "codeowners", "status": "fail",
                "evidence": ["..."], "remediation": "...", "artifact": "CODEOWNERS"}]}],
  "facts": {"top_committers": [], "latest_release": {}}
}
```

## GitHub Action

```yaml
jobs:
  continuity:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0          # full history, needed for contributor analysis
      - uses: KenuriPerera/oss-continuity@v0.1.0
        with:
          fail-on: never          # or "fail" / "warn" to gate PRs
```

The report is added to the job summary.

## Generated drafts

`init` currently has builders for `CONTINUITY.md`, `MAINTAINER.md`, `RELEASE.md`,
`DEVELOPMENT.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md` and `.github/CODEOWNERS` (all rules
commented out). It deliberately does **not** generate a `LICENSE`, `SECURITY.md`, `README.md` or
`CHANGELOG.md`: those require decisions or information that cannot be inferred.

A generated `RELEASE.md` for a repository without release evidence looks like this:

```markdown
# Release Process

> ⚠️ **Draft generated by OSS Continuity 0.1.0 on 2026-09-23.**

## What the repository shows

The repository does not currently contain enough information to determine the official
release procedure.

## Information required from maintainers

**Needs maintainer input**

- Who can publish releases?
- How are version numbers chosen?
- How is the changelog updated?
- Which CI workflow, or whose machine, publishes packages?
```

## Limitations

- Commit authorship is not maintainership. The tool reports who *committed*, not who has merge or
  release rights, and says so in its output.
- Documentation checks are heuristics based on file names and section headings. They detect that
  something is written down, not that it is correct. Use `--verbose` to see exactly what matched.
- GitHub analysis samples up to `--max-commits` recent commits (default 300); the output notes
  when sampling occurred.
- Squash-merge workflows attribute commits to PR authors, not to the maintainers who merged them.

## Roadmap

- **Phase 2:** machine-readable `continuity.yaml` standard, historical tracking, PR comments
- **Phase 3:** npm / PyPI / crates.io metadata (registry owners, publish history), dependency-level
  continuity across a project's dependency tree
- **Phase 4:** optional AI-assisted drafting where every generated statement links to evidence

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Development setup is in its *Development setup* section;
code structure is described in [ARCHITECTURE.md](ARCHITECTURE.md).

## License

MIT, see [LICENSE](LICENSE).

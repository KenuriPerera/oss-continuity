# Check reference

Every check returns one of five statuses:

| Status | Meaning |
|---|---|
| `pass` | Evidence found |
| `warn` | Partial evidence, an unfinished draft, or a gap that matters less for handoff |
| `fail` | The information a successor needs is missing |
| `unknown` | The data needed was unavailable (e.g. not a git repository); never fails `check` |
| `info` | Context only (e.g. repository archived, release without a date) |

File lookups are case-insensitive. Unless noted, documents are searched in the repository root,
`.github/`, `docs/` and `doc/`, with extensions `.md`, `.markdown`, `.rst`, `.txt`, `.adoc` or none.
Directories such as `node_modules`, `.venv`, `dist`, `build` and `target` are skipped locally.

**Section headings** are read from README, CONTRIBUTING, DEVELOPMENT/HACKING/MAINTAINERS documents
and up to 30 top-level files in `docs/`. Markdown ATX (`## Title`), setext and reStructuredText
headings are recognised; headings inside fenced code blocks are ignored.

**Drafts:** any file containing `<!-- oss-continuity:draft -->` is treated as an unfinished
draft. It never counts as `pass`; the check reports `warn` / `draft only` instead.

## Maintainer continuity

### `primary_committers`

The smallest number of people who together authored at least 50% of human (non-merge, non-bot)
commits in the analysis window (`--window-days`, default 365). This is a bus-factor
approximation.

- `pass`: 3 or more · `warn`: 2 · `fail`: 1, or no human commits in the window
- Bots: identities matching `[bot]`, `dependabot`, `renovate`, `github-actions`,
  `pre-commit-ci`, or ending in `-bot`.
- Identity: GitHub login when available, otherwise the lower-cased e-mail address. The same
  person committing with two e-mail addresses locally is counted twice (known limitation).
- GitHub: at most `--max-commits` (default 300) most recent commits are sampled; the evidence says
  when sampling happened.

### `recent_committers`

Distinct human committers in the last `--recent-days` (default 90).
`pass`: 2 or more · `warn`: 1 · `fail`: 0.

### `maintainers_doc`

`MAINTAINERS`, `MAINTAINER`, `OWNERS` or `GOVERNANCE`. Missing: `fail`.

### `codeowners`

`CODEOWNERS` in the root, `.github/` or `docs/` with at least one non-comment rule.
Only comments: `warn`. Missing: `fail`.

## Knowledge continuity

### `readme`
A README in the repository root. Missing: `fail`.

### `contributing`
A `CONTRIBUTING` document. Missing: `fail`.

### `dev_setup`
`pass` if any of: `DEVELOPMENT`, `DEVELOPING`, `DEVELOPER` or `HACKING` document; a devcontainer;
a heading matching *development, getting started, setup, local environment, building from source,
running tests* and similar. `warn` if only build tooling exists (e.g. `package.json`, `Makefile`,
`pyproject.toml`) with no written instructions. Otherwise `fail`.

### `architecture`
`pass` if any of: `ARCHITECTURE`, `DESIGN` or `INTERNALS` document; an ADR directory (`adr/`,
`decisions/`, `docs/adr/`, ...); a `docs/architecture*` or `docs/design*` file; a heading matching
*architecture, internals, project structure, code layout, how it works* and similar. Else `fail`.

### `continuity_doc`
`CONTINUITY.md` (root, `.github/`, `docs/`) or `continuity.yaml`. Missing: `warn`.

## Release continuity

### `latest_release`
Newest GitHub release (non-draft) or, if none, newest git tag.
`pass`: ≤ 180 days old · `warn`: ≤ 365 days · `fail`: older, or no releases/tags at all.
A tag without a resolvable date is reported as `info`.

### `release_process`
`RELEASE`, `RELEASING`, `RELEASE_PROCESS` or `PUBLISHING` document, a `docs/*releas*` file, or a
heading matching *release, releasing, release process, publishing, cutting a release*.
Missing: `fail`.

### `automated_release`
A CI file containing a recognised publishing step: PyPI publish action, `twine upload`,
`poetry/flit/hatch/uv publish`, `npm/pnpm/yarn publish`, Changesets, semantic-release,
release-please, `cargo publish`, GoReleaser, `gem push`, NuGet push, Maven deploy, Gradle publish,
Docker build-push, GitHub release actions or `gh release create`. Not found: `warn`.

### `changelog`
`CHANGELOG`, `CHANGES`, `HISTORY`, `NEWS` or `RELEASE_NOTES` in the root or `docs/`.
Missing: `warn`.

## Operational continuity

### `ci`
GitHub Actions workflows, `.gitlab-ci.yml`, CircleCI, Travis, Azure Pipelines, Jenkinsfile,
Bitbucket Pipelines, Drone, Woodpecker or Buildkite. Missing: `fail`.

### `secrets_documented`
Every `secrets.NAME` / `secrets['NAME']` referenced in CI (except the implicit `GITHUB_TOKEN`)
must appear as a whole word in at least one document (root-level documents plus `.github/` and
`docs/`, up to 80 files). None referenced: `pass`. Some documented: `warn`. None documented: `fail`.

### `dependency_updates`
Dependabot or Renovate configuration. Missing: `warn`.

### `tests`
Test directories (`test/`, `tests/`, `__tests__/`, `spec/`) or test files (`test_*.py`,
`*_test.py`, `*_test.go`, `*.test.js`, `*.spec.ts`, `*_spec.rb`, root `test.js`, ...).
Missing: `warn`.

## Governance

### `license`
`LICENSE`, `LICENCE` or `COPYING` (with any extension or suffix) in the root, or a `LICENSES/`
directory. Missing: `fail`.

### `security_policy`
A `SECURITY` document. Missing: `warn`.

## JSON output contract

`schema_version` is incremented on breaking changes. Check IDs are stable. Top-level keys:
`schema_version`, `tool`, `repository`, `source`, `location`, `generated_at`, `summary`
(counts per status), `continuity` (check ID → status), `missing_handoff_artifacts`, `actions`,
`sections` (full checks with evidence) and `facts` (committer breakdown, latest release,
GitHub metadata, sampling information).

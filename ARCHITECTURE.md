# Architecture

`oss-continuity` is a small, dependency-free Python package with a pipeline of four stages:

```text
target ──▶ Source ──▶ Analyzers ──▶ Report ──▶ Renderer (text / markdown / json)
                                        └────▶ Handoff draft generator (init)
```

## Components

| Module | Responsibility |
|---|---|
| `cli.py` | Argument parsing, target resolution, exit codes |
| `source.py` | `RepoSource` interface: file tree, file contents, commits, releases; case-insensitive lookup helpers |
| `local.py` | `LocalSource`: filesystem walk plus `git log` / `git for-each-ref` |
| `github.py` | `GitHubSource`: REST API for metadata, tree, commits and releases; file contents from `raw.githubusercontent.com`. The HTTP function is injectable for tests |
| `analyzers/` | One module per area (`maintainers`, `knowledge`, `releases`, `operations`, `governance`), each exposing `analyze(source, ctx) -> Section` |
| `analyzers/common.py` | Shared heuristics: doc lookup, heading extraction, draft detection, CI file discovery |
| `core.py` | Runs all analyzers and assembles a `Report` |
| `model.py` | `Status`, `Check`, `Section`, `Report` and the JSON contract |
| `reports/` | Renderers |
| `handoff.py` | Draft builders used by `init` |

## Key design decisions

- **Evidence over scores.** A `Check` always carries evidence strings. `Report` derives
  `missing_artifacts()` and `actions()` from checks; there is intentionally no aggregate score.
- **Sources are interchangeable.** Analyzers only use the `RepoSource` interface, so every check
  works identically on GitHub and local repositories. Missing data (e.g. no git history) raises
  `SourceUnavailable`, which analyzers turn into `unknown` rather than a failure.
- **Drafts are marked.** `handoff.py` embeds `DRAFT_MARKER`; `file_check()` downgrades marked files
  to `warn` / `draft only`, so generated files can't make a repository look healthier than it is.
- **No runtime dependencies.** `urllib` and `subprocess` only, which keeps installation trivial in
  CI and avoids supply-chain surface for a tool about project sustainability.
- **API economy.** One tree call replaces per-file existence checks; contents come from raw URLs,
  which are not rate limited like the API.

## Adding a new source (e.g. GitLab)

Implement `_list_paths`, `_read`, `commits` and `releases` on a `RepoSource` subclass and add
target detection in `cli.resolve_source`. No analyzer changes should be needed.

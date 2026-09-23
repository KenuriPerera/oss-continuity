# Contributing to oss-continuity

Thanks for helping. Bug reports, false positives/negatives from real repositories, and new
detection heuristics are especially welcome.

## Before you start

- For bugs, open an issue with the repository you analysed (if public), the command you ran,
  and the `--verbose` output.
- For new checks or larger changes, open an issue first so we can agree on the approach.
  New checks must produce **evidence**, not just a status, and must not add a numeric score.

## Development setup

Requirements: Python 3.9 or newer, and `git` (used for local history analysis and tests).

```bash
git clone https://github.com/KenuriPerera/oss-continuity.git
cd oss-continuity
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Running tests and linters

```bash
pytest                    # full test suite, no network access required
ruff check src tests      # lint
ruff format src tests     # format
oss-continuity check . --fail-on never --verbose   # dogfood on this repository
```

GitHub API behaviour is tested with a fake HTTP layer (`tests/test_github.py`), so the suite
never calls the real API.

## Adding a check

1. Pick the analyzer in `src/oss_continuity/analyzers/` that matches the area.
2. Return a `Check` with a stable `id`, a short `summary`, concrete `evidence`, and, for
   `warn`/`fail`, a `remediation` and the `artifact` that would resolve it.
3. Add tests with a small fixture repository (see `tests/test_analysis.py`).
4. Document the check in `docs/checks.md` and the table in `README.md`.

Check IDs are part of the JSON output contract: don't rename them without a changelog entry.

## Pull requests

- Keep PRs focused; include tests.
- Update `CHANGELOG.md` under *Unreleased*.
- By contributing you agree your work is licensed under the MIT license.

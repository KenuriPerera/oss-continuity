# Release Process

Releases are published to PyPI by `.github/workflows/release.yml` using PyPI
[trusted publishing](https://docs.pypi.org/trusted-publishers/) (OIDC). No long-lived API token is
stored in the repository.

## One-time setup (maintainer with PyPI access)

1. Create the `oss-continuity` project on PyPI (or a pending publisher).
2. Add a trusted publisher: owner/repository of this repo, workflow `release.yml`,
   environment `pypi`.
3. In GitHub repository settings, create an environment named `pypi` (optionally requiring
   reviewer approval).

## Cutting a release

1. Make sure `main` is green in CI.
2. Choose the version using [Semantic Versioning](https://semver.org/). While on `0.x`, breaking
   changes to the CLI or JSON output bump the minor version.
3. Update the version in both `pyproject.toml` and `src/oss_continuity/__init__.py`.
4. Move the *Unreleased* entries in `CHANGELOG.md` under the new version with today's date.
5. Commit: `git commit -am "Release vX.Y.Z"`.
6. Tag and push: `git tag vX.Y.Z && git push origin main vX.Y.Z`.
7. The release workflow builds, tests, publishes to PyPI and creates a GitHub release.

## If a release is broken

Yank it on PyPI (don't delete), fix forward with a patch release, and note it in the changelog.

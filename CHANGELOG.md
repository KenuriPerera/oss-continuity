# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-09-23

### Added

- `analyze`, `check` and `init` commands.
- GitHub (REST API) and local git repository sources.
- Checks for maintainer, knowledge, release, operational and governance continuity, each with
  evidence and remediation; no aggregate score.
- Text, Markdown and JSON (schema version 1) reports.
- Evidence-only draft generation for `CONTINUITY.md`, `MAINTAINER.md`, `RELEASE.md`,
  `DEVELOPMENT.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md` and `CODEOWNERS`; drafts are reported as
  unfinished until completed.
- Composite GitHub Action.

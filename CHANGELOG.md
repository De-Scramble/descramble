# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Quickstart activation instructions failed on Windows PowerShell: `source` is a bash builtin and is
  not a PowerShell command, so the first command a new user ran errored out. The README and
  `CONTRIBUTING.md` now give separate, clearly-labelled commands for bash/zsh, PowerShell
  (`Activate.ps1`), cmd (`activate.bat`) and Git Bash, plus notes on `python` vs `python3` and on
  PowerShell's script-execution policy. ([#1](https://github.com/De-Scramble/descramble/issues/1))

### Changed

- The `demo` command no longer prints the wall of expected model-training warnings that Splink emits
  on the small sample dataset, where some comparison levels are too rare to train every parameter.
  The behaviour was always correct but read as a fault. The warnings are replaced by one line stating
  how many were hidden and why, and `--verbose` still shows them in full. The filter is scoped to the
  `demo` command and matches only known-expected phrases from Splink's own loggers, so real runs and
  genuine warnings are untouched.

### Added

- Probabilistic record linkage using the Fellegi-Sunter model, via Splink on a DuckDB backend.
- Composite blocking rules that reduce the candidate comparison space from every-pair to a
  tractable subset, with a reported reduction ratio.
- Golden-record survivorship: each cluster of matched records is collapsed into one resolved
  record with a stable cluster identifier.
- An Apache Iceberg writer targeting a local SQLite-backed catalogue by default, so the pipeline
  runs end to end with no cloud account and no external service.
- A generic input reader for CSV and Parquet, with batch watermarking so re-running the pipeline
  over a growing input is idempotent.
- A synthetic sample dataset generator producing person-like records with deliberately injected
  duplicates — varied capitalisation, name typos, transpositions, and changed postcodes — so the
  linkage can be seen working immediately after install.
- A command-line interface: `descramble demo`, `descramble generate`, `descramble run`.
- The minimum test surface: linkage correctness, Iceberg write/read round-trip, and determinism.
- Continuous integration running the test suite on every push and pull request, plus a standing
  dependency-licence scan that re-verifies licence compatibility whenever dependencies change.

- A pinned, igraph-free dependency manifest installed with `--no-deps`, so the documented install
  path pulls no GPL-licensed software, enforced by a CI job that asserts igraph is absent and runs
  the full suite against that environment.

[Unreleased]: https://github.com/De-Scramble/descramble/commits/main

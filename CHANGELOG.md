# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

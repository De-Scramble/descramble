## What this changes

<!-- A sentence or two on what this does and why. Link the issue it addresses, if there is one. -->

Closes #

## Type of change

- [ ] Bug fix (does not change existing behaviour)
- [ ] New feature (adds behaviour)
- [ ] Breaking change (existing behaviour changes)
- [ ] Documentation only
- [ ] Build, CI, or tooling

## Checklist

- [ ] **Every commit is signed off** (`git commit -s`) — we use the DCO, not a CLA. See
      [CONTRIBUTING.md](../CONTRIBUTING.md).
- [ ] **Tests added or updated** for the behaviour this changes.
- [ ] **The full suite passes locally** (`pytest`). A red suite blocks the merge.
- [ ] The three core properties still hold: known duplicates still cluster, distinct records still
      do not merge, and the same input still produces the same golden records.
- [ ] Documentation updated, if user-facing behaviour changed.
- [ ] `CHANGELOG.md` updated under `[Unreleased]`, if user-facing behaviour changed.
- [ ] No credentials, secrets, real endpoints, or real personal data are included in this change —
      sample data is synthetic.
- [ ] Dependency changes, if any, are noted below with the licence of each added dependency.

## Effect on matching behaviour

<!-- If this changes comparisons, blocking rules, or thresholds, say so explicitly and give the
     before/after numbers from a demo run. Silent changes to match quality are the hardest kind of
     regression to catch. If nothing changes, write "none". -->

none

## How this was verified

<!-- Commands you ran and what you observed. -->

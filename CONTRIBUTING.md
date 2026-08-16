# Contributing to De-Scramble

Thanks for considering a contribution. De-Scramble is a genuinely open project: the core is free,
Apache-2.0 licensed, and is never gated or crippled to sell an upgrade. Contributions are welcome
from anyone.

By participating you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Sign-off is required (DCO, not a CLA)

We use the [Developer Certificate of Origin](https://developercertificate.org/) — **not** a
Contributor Licence Agreement. You keep the copyright to your work; you are simply certifying that
you have the right to submit it under the project's licence.

Certify it by adding a `Signed-off-by` line to every commit, which git will write for you:

```bash
git commit -s -m "feat: add a thing"
```

That produces a trailer like:

```
Signed-off-by: Your Name <your.email@example.com>
```

The name and address must be real and must match your git identity. Amend a commit you forgot to
sign off with `git commit --amend -s`, or fix a whole branch with
`git rebase --signoff main`.

We ask for no copyright assignment and no CLA. There is no paperwork beyond the sign-off line.

## Open an issue first for anything large

- **Bug fixes, docs, small improvements** — send a pull request directly.
- **New features, dependency changes, or anything that reshapes the pipeline** — please open an
  issue first so we can agree on the approach before you spend time on it. This is about respecting
  your effort, not gatekeeping.

## Getting set up

```bash
git clone https://github.com/De-Scramble/descramble.git
cd descramble
python -m venv .venv
```

Activate the environment with the command for your shell — `source` is not a PowerShell command, so
copying the wrong line is the most common first stumble:

| Shell | Command |
|---|---|
| macOS / Linux (bash, zsh) | `source .venv/bin/activate` |
| Windows (PowerShell) | `.venv\Scripts\Activate.ps1` |
| Windows (cmd.exe) | `.venv\Scripts\activate.bat` |
| Windows (Git Bash) | `source .venv/Scripts/activate` |

Then install:

```bash
pip install --no-deps -r requirements.txt
pip install --no-deps -e .
pip install --no-deps pytest==9.1.1 iniconfig==2.3.0 pluggy==1.6.0
```

If `python` is not found on macOS or Linux, use `python3`; on Windows, `py` works if `python` does not.

`--no-deps` is deliberate and load-bearing: it is what keeps the GPL-licensed `igraph` out of the
environment. Please do not "fix" it to a plain `pip install -e ".[dev]"` — that reintroduces igraph.
The reasoning is in the README under **Installing**, and a CI job enforces it.

If you add or change a dependency, update `requirements.txt` as well, since `--no-deps` means an
incomplete manifest produces an `ImportError` rather than a silent fallback.

Generate the sample data and run the pipeline end to end:

```bash
python -m descramble demo
```

## Running the tests

```bash
pytest
```

The suite must be green before a pull request can merge. Continuous integration runs it on every
push and pull request, and a red suite blocks the merge — this is deliberate and is not overridden
for convenience. If a test fails on your machine but passes in CI (or vice versa), say so in the
pull request rather than skipping the test.

Three properties are treated as non-negotiable, and every change is expected to keep them true:

1. **Linkage correctness** — records that describe the same person cluster together, and records
   that describe different people do not merge.
2. **Round-trip integrity** — what is written to the lakehouse reads back identically.
3. **Determinism** — the same input produces the same golden records, every run.

If your change alters matching behaviour, that is fine, but update the tests to describe the new
expected behaviour explicitly and explain the reasoning in the pull request.

## Pull request expectations

- Keep the change focused; one concern per pull request.
- Include tests for behaviour you add or change.
- Update the docs and `CHANGELOG.md` when user-facing behaviour changes.
- Every commit signed off (`-s`).
- Write commit subjects in the imperative mood, prefixed by type: `feat:`, `fix:`, `docs:`,
  `test:`, `refactor:`, `chore:`, `ci:`.

## Reporting a security problem

Do **not** open a public issue for a security vulnerability. Follow
[SECURITY.md](SECURITY.md) instead.

## Licence

Contributions are accepted under the [Apache Licence 2.0](LICENSE), the same licence that covers
the rest of the project.

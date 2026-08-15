# De-Scramble — Probabilistic Identity Resolution into an Apache Iceberg Lakehouse

A runnable reference implementation of Fellegi-Sunter record linkage (Splink) that resolves messy
person records into deduplicated golden records and publishes them to an Apache Iceberg lakehouse.

[![Licence: Apache-2.0](https://img.shields.io/badge/licence-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Runs locally](https://img.shields.io/badge/runs%20locally-no%20cloud%20required-brightgreen.svg)](#quickstart)

## What this is

A documented, tested, end-to-end example of the two techniques that sit underneath most
customer-data work: **probabilistic record linkage**, which finds the records that describe the same
person despite the data disagreeing about who they are, and a **lakehouse write pattern**, which
publishes the result so that many consumers can read it without copying it and without ever seeing a
half-written table.

It runs on your machine, in about a minute, with no cloud account and no running services. The
sample data is synthetic, so there is nothing to acquire before you can see it work.

## The problem it solves

Real data disagrees with itself. The same person arrives as:

| record_id | first_name | last_name | email | postcode | city |
|---|---|---|---|---|---|
| r0000042 | Katherine | Ravenscroft | `k.ravenscroft@example.com` | SW14 9QT | Brightwater |
| r0000043 | Kate | Ravenscroft | `K.Ravenscroft@Example.com` | SW14 9QT | Brightwater |
| r0000044 | Katherine | Ravenscrofr | `k.ravenscroft@example.com` | SW14 9QR | |

Exact matching finds none of this. `GROUP BY email` misses the capitalisation. Fuzzy-matching one
column at a time either misses the typo or merges strangers. And the obvious fix — compare every
record with every other — is quadratic: a million records is five hundred billion comparisons, which
is not a tuning problem but an arithmetic one.

The answer is to score the *evidence*, and to only score pairs worth scoring.

## Quickstart

```bash
git clone https://github.com/De-Scramble/descramble.git
cd descramble
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install --no-deps -r requirements.txt
pip install --no-deps .

python -m descramble demo
```

`--no-deps` is required rather than optional. It is what keeps GPL-licensed
software off your machine — see [Installing](#installing) for why.

`demo` generates a synthetic dataset with deliberate duplicates, resolves it, writes the golden
records to a local Iceberg table, and reports what it did:

```
Resolution complete
-------------------
  3,149 raw records -> 2,009 golden records
  574 duplicate clusters resolved, 1,140 redundant records merged away
  blocking considered 4,698 candidate pairs out of 4,956,526 possible (99.91% removed)
  match threshold 0.9
  written to Iceberg table at file://.../warehouse/descramble/golden_records
```

To run it against your own CSV or Parquet file — any file with the columns `record_id`,
`first_name`, `last_name`, `email`, `postcode`, `city`:

```bash
python -m descramble run --input path/to/your/records.csv
```

## Installing

```bash
pip install --no-deps -r requirements.txt
pip install --no-deps .
```

**Why `--no-deps`.** Splink, the linkage engine underneath De-Scramble, declares a hard dependency on
`igraph`, which is **GPL-licensed**. De-Scramble never uses igraph — it contains no igraph code,
Splink does not import it at import time, and clustering runs through the DuckDB
connected-components path. The full test suite and the end-to-end pipeline are verified to run with
igraph absent, producing identical results.

So `requirements.txt` is a complete, pinned manifest that omits igraph. `--no-deps` tells pip to
install exactly what is listed and resolve nothing further. It is necessary because pip has no way to
*exclude* a package: a constraints file pins versions, it cannot subtract one. A CI job rebuilds this
environment on every push, asserts igraph is neither installed nor importable, and runs the whole
suite against it.

Because `--no-deps` disables resolution, the manifest must stay complete — which is exactly what that
CI job is guarding.

**The honest caveat.** A plain `pip install descramble` or `pip install .`, with resolution enabled,
*will* install igraph. If you install that way, or if you add `splink` to your own project's
dependencies, you receive GPL-licensed code. This is stated plainly in [NOTICE](NOTICE), which
records what was measured and nothing more.

For development, add the test tooling the same way:

```bash
pip install --no-deps pytest==9.1.1 iniconfig==2.3.0 pluggy==1.6.0
```

## Architecture

```
   ┌──────────────┐     ┌───────────────────────────────────┐     ┌──────────────┐
   │  CSV/Parquet │     │      IDENTITY RESOLUTION          │     │   ICEBERG    │
   │   records    │────▶│                                   │────▶│  LAKEHOUSE   │
   │              │     │  blocking     candidate pairs     │     │              │
   │  batched +   │     │      ↓                            │     │  atomic      │
   │  watermarked │     │  comparison   m/u parameters      │     │  snapshot    │
   └──────────────┘     │      ↓        (EM-trained)        │     │  swap        │
                        │  scoring      match probability   │     └──────┬───────┘
                        │      ↓                            │            │
                        │  clustering   connected components│            ▼
                        │      ↓                            │     many independent
                        │  survivorship golden records      │      consumers, no
                        └───────────────────────────────────┘       data copies
```

## How it works

### Fellegi-Sunter, in plain terms

Stop asking "are these two records equal?" and ask instead: **how much more likely is this pattern of
agreement if the two records describe the same person than if they do not?**

For a candidate pair, each field is compared and reduced to a **comparison level** — exact, near,
different. The vector of those levels is the evidence. Each level carries two probabilities:

- **m** — the probability of seeing this level **given the records match**. People mistype their own
  surname, so exact agreement is likely but not certain.
- **u** — the probability of seeing this level **given they do not match**. Two unrelated people
  rarely share a surname, so this is small.

The ratio **m/u** is that level's Bayes factor: how much the observation should move your belief.
Multiply the factors across all fields, apply them to a prior about how often two randomly chosen
records match, and you get a posterior **match probability** for the pair.

Crucially, m and u are not guessed. **u** is estimated by sampling random pairs, which are
overwhelmingly non-matches. **m** is estimated by expectation-maximisation, alternating between
scoring pairs with the current parameters and re-estimating the parameters from those scores until
they stop moving.

Pairs above the threshold become edges in a graph, and each **connected component** of that graph is
one person.

### Blocking, and why it is the whole ballgame

Scoring every pair is quadratic and therefore impossible at any interesting scale. Blocking
generates candidate pairs only within groups that already agree on something cheap and selective.
De-Scramble uses five complementary rules:

| Rule | Catches | Blind to |
|---|---|---|
| `email` | the strong, common case | a mistyped address |
| `last_name` + `postcode` | a changed or mistyped email | a surname typo |
| `first_name` + `city` | a surname typo | a given-name typo, missing city |
| first 2 letters of both names | typos after the second character | typos in the first two |
| `postcode` | records where email *and* both names are damaged | a move plus a typo |

They are chosen for **complementary blind spots**, not individual strength: a pair missed by every
rule is never scored at all, so this list — not the model — sets the ceiling on recall.

On the bundled sample this reduces 4,956,526 possible pairs to **4,698 actually compared: a 99.91%
reduction**, turning an O(n²) problem into something that finishes while you watch.

### The Iceberg hub-and-spoke write

Writing resolved records as plain files has an ugly failure mode: a reader arriving mid-write sees a
directory that is half old and half new, with no way to tell.

Iceberg fixes this with indirection. A table is a set of immutable data files plus metadata naming
which files form the current **snapshot**. A write adds new files that nobody is reading, then swaps
a single metadata pointer — atomically. Every reader sees either the whole old snapshot or the whole
new one, never a mixture, and readers are never blocked by the writer.

That is what makes one table safely serve many consumers: write once, read from anywhere, no copies,
no partial reads.

## Sample results

Against the bundled synthetic dataset, whose ground truth is known by construction:

| Measure | Result |
|---|---|
| Input records | 3,149 |
| Golden records produced | 2,009 |
| Actual distinct people | 2,000 |
| Duplicate clusters resolved | 574 |
| Redundant records merged away | 1,140 |
| Pairwise precision | **0.989** |
| Pairwise recall | **0.984** |
| Pairwise F1 | **0.987** |
| Candidate pairs compared | 4,698 of 4,956,526 (99.91% removed) |

Precision and recall are reported together deliberately: merging nothing scores perfectly on
precision, merging everything scores perfectly on recall, and a system quoting only one of them is
telling you half the story. Both are asserted as floors in the test suite.

## Configuration

Everything has a working default. Copy `.env.example` to `.env`, or use flags:

| Setting | Environment variable | Default |
|---|---|---|
| Input file | `DESCRAMBLE_INPUT` | `data/sample_records.csv` |
| Warehouse directory | `DESCRAMBLE_WAREHOUSE` | `warehouse` |
| Match threshold | `DESCRAMBLE_THRESHOLD` | `0.9` |
| Random seed | `DESCRAMBLE_SEED` | `1729` |
| Catalogue / namespace / table | `DESCRAMBLE_CATALOG` / `_NAMESPACE` / `_TABLE` | `descramble` / `descramble` / `golden_records` |

**Tuning the threshold.** Raise it to merge less — fewer false merges, more duplicates left behind.
Lower it to merge more, with the opposite trade. There is no universally correct value: it depends
whether a wrongly-merged pair or a missed duplicate costs you more.

**Tuning blocking.** Rules live in `blocking_rules()` in `src/descramble/resolve.py`. Add rules to
raise recall; each one costs comparisons. On this dataset, adding a rule on a prefix of the email
local part lifts recall by roughly a further half a percent and costs about **five times** the
comparisons — a good illustration that blocking cost is paid in the pairs rules generate *together*.

**Using object storage instead of the local catalogue.** The local SQLite catalogue is a convenience
for getting started, not a limitation. Point `DESCRAMBLE_WAREHOUSE` at a bucket URI and supply a
catalogue URI for your catalogue implementation; credentials are read by PyIceberg from your normal
cloud configuration. No code changes.

## Design decisions and trade-offs

**Why Splink.** Fellegi-Sunter is well understood and, importantly, *explainable* — you can show why
two records matched, which matters when the answer affects a real person. Splink implements it over
a SQL engine, so the heavy work happens in the database rather than in Python loops.

**Why DuckDB.** The linkage workload is analytical: large scans, joins, aggregations, one process.
That is exactly DuckDB's shape, and it needs no server, which keeps the quickstart honest.

**Why Iceberg.** The atomic snapshot swap is the feature. Without it, publishing resolved records
means either a lock or a race.

**Why standardise email before matching.** Case is not identity. Normalising it costs one cheap rule
and repairs the email blocking rule, which is an equality test and would otherwise miss every pair
differing only by capitalisation. Leaving that to the probabilistic model spends its power on a
difference that a trivial rule settles outright.

**Why blank values become nulls.** Two records that merely *lack* a city would otherwise be scored as
agreeing on it — counting absence of evidence as evidence, and nudging strangers together.

**Why cluster identifiers are derived here.** Each cluster is identified by the smallest record
identifier it contains, making the identifier a function of membership alone. That keeps output
comparable across runs and across backends, instead of depending on whatever label the engine
happened to assign.

**Survivorship is plurality with a deterministic tie-break**, and its limitation is worth stating:
where a cluster has no majority, plurality has no real opinion and the tie-break is arbitrary but at
least stable. Where records carry trustworthy timestamps, recency would beat it.

## Testing

```bash
pip install --no-deps -r requirements.txt
pip install --no-deps .
pip install --no-deps pytest==9.1.1 iniconfig==2.3.0 pluggy==1.6.0
pytest
```

The suite asserts the three properties the project actually guarantees:

1. **Linkage correctness** — known duplicates cluster together, and distinct people do not merge.
2. **Round-trip integrity** — what is written to Iceberg reads back identically, with the declared schema.
3. **Determinism** — the same input produces the same golden records, every run.

Continuous integration runs it on Linux, Windows and macOS across Python 3.10–3.12 on every push and
pull request. A red suite blocks the merge.

## Contributing

Contributions are welcome. We use the [Developer Certificate of Origin](https://developercertificate.org/)
— sign commits with `git commit -s`. There is no CLA and no copyright assignment. See
[CONTRIBUTING.md](CONTRIBUTING.md), and [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

## Licence

Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

The core is free forever and is never gated, crippled, or limited to sell an upgrade; see the
open-core promise in [GOVERNANCE.md](GOVERNANCE.md).

Every dependency installed by the documented path is permissively licensed and compatible with
Apache-2.0; [NOTICE](NOTICE) lists all 46 with their licences, and records the one file-level
copyleft dependency (certifi, MPL-2.0) explicitly. It also records the igraph caveat described under
[Installing](#installing). Please read it before redistributing a built environment.

---

De-Scramble is operated and stewarded by **Deluge Limited**.

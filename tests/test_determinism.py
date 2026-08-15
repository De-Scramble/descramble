# SPDX-License-Identifier: Apache-2.0
"""Determinism.

Identity resolution decides which people exist as far as everything downstream
is concerned. If two runs over the same input disagree, then every consumer of
the output inherits that disagreement, and no result derived from it can be
reproduced or audited. Parameter estimation samples, so determinism here is a
property that has to be deliberately maintained — via a fixed seed and stable
ordering — rather than one that holds by accident.
"""

from __future__ import annotations

import pandas as pd
from pandas.testing import assert_frame_equal

from descramble.config import PipelineConfig
from descramble.golden import build_golden_records
from descramble.reader import read_records
from descramble.resolve import resolve_records
from descramble.sampledata import generate_records, write_csv

PEOPLE = 200
SEED = 1729


def _resolve(path, warehouse) -> pd.DataFrame:
    config = PipelineConfig(input_path=path, warehouse_dir=warehouse).validate()
    records = read_records(path)
    linkage = resolve_records(records, config)
    return build_golden_records(records, linkage.clusters)


def test_generation_is_reproducible(tmp_path):
    """The same seed produces byte-identical sample data."""
    first_rows, first_summary = generate_records(people=PEOPLE, seed=SEED)
    second_rows, second_summary = generate_records(people=PEOPLE, seed=SEED)

    assert first_rows == second_rows
    assert first_summary.truth == second_summary.truth

    first = write_csv(first_rows, tmp_path / "first.csv")
    second = write_csv(second_rows, tmp_path / "second.csv")
    assert first.read_bytes() == second.read_bytes()


def test_a_different_seed_produces_different_data():
    """The seed is actually being used — the reproducibility test means nothing otherwise."""
    rows, _ = generate_records(people=PEOPLE, seed=SEED)
    other, _ = generate_records(people=PEOPLE, seed=SEED + 1)
    assert rows != other


def test_same_input_produces_same_golden_records(tmp_path):
    """Two independent runs over identical input agree exactly."""
    rows, _ = generate_records(people=PEOPLE, seed=SEED)
    path = write_csv(rows, tmp_path / "records.csv")

    first = _resolve(path, tmp_path / "warehouse_one")
    second = _resolve(path, tmp_path / "warehouse_two")

    assert_frame_equal(first, second)


def test_cluster_identifiers_are_derived_from_membership(tmp_path):
    """Cluster identifiers are stable and meaningful, not run-dependent.

    Each identifier is the smallest record identifier in its cluster, so it is
    a function of the cluster's membership alone. That is what lets two runs —
    or two backends — produce comparable output.
    """
    rows, _ = generate_records(people=PEOPLE, seed=SEED)
    path = write_csv(rows, tmp_path / "records.csv")
    golden = _resolve(path, tmp_path / "warehouse")

    for row in golden.itertuples():
        members = row.source_record_ids.split(",")
        assert members == sorted(members), "member identifiers are not stably ordered"
        assert row.cluster_id == members[0], (
            "cluster identifier is not the smallest member identifier"
        )

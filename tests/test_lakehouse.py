# SPDX-License-Identifier: Apache-2.0
"""Iceberg write/read round-trip.

Resolution is only useful if the result survives publication intact. These
tests treat the lakehouse as a black box with a contract: what goes in comes
back out, unchanged, with the declared types, and re-running does not
accumulate duplicate generations of the same data.
"""

from __future__ import annotations

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from descramble.config import PipelineConfig
from descramble.golden import GOLDEN_COLUMNS
from descramble.lakehouse import GOLDEN_SCHEMA, Lakehouse


@pytest.fixture
def golden_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "cluster_id": "r0000001",
                "first_name": "Cordelia",
                "last_name": "Fenchurch",
                "email": "cordelia.fenchurch@example.com",
                "postcode": "AB12 3CD",
                "city": "Ashford",
                "source_record_count": 3,
                "source_record_ids": "r0000001,r0000002,r0000003",
            },
            {
                "cluster_id": "r0000004",
                "first_name": "Jasper",
                "last_name": "Wilberforce",
                "email": "j.wilberforce@example.net",
                "postcode": "ZX98 7YW",
                "city": "",
                "source_record_count": 1,
                "source_record_ids": "r0000004",
            },
        ],
        columns=list(GOLDEN_COLUMNS),
    ).astype({"source_record_count": "int64"})


@pytest.fixture
def lakehouse(tmp_path) -> Lakehouse:
    return Lakehouse(PipelineConfig(warehouse_dir=tmp_path / "warehouse").validate())


def test_written_records_read_back_identically(lakehouse, golden_frame):
    """The round-trip is lossless."""
    summary = lakehouse.write_golden_records(golden_frame)
    assert summary.rows_written == len(golden_frame)

    read_back = lakehouse.read_golden_records()
    assert_frame_equal(
        read_back.sort_values("cluster_id").reset_index(drop=True),
        golden_frame.sort_values("cluster_id").reset_index(drop=True),
        check_dtype=False,
    )


def test_declared_schema_is_what_lands_in_the_table(lakehouse, golden_frame):
    """Column names and types are the declared contract, not an inference.

    An inferred schema silently changes shape with the data, which turns a
    downstream consumer's working query into a broken one without any change
    on this side.
    """
    lakehouse.write_golden_records(golden_frame)
    arrow = lakehouse._table().scan().to_arrow()

    assert arrow.schema.names == list(GOLDEN_COLUMNS)
    for field in GOLDEN_SCHEMA:
        assert arrow.schema.field(field.name).type == field.type


def test_rerunning_replaces_rather_than_accumulates(lakehouse, golden_frame):
    """A repeated full run is idempotent.

    Re-resolving the same input is a restatement, not new information. The
    table should hold one authoritative set of golden records afterwards, not
    two overlapping copies — otherwise every retry silently doubles the data.
    """
    lakehouse.write_golden_records(golden_frame)
    lakehouse.write_golden_records(golden_frame)

    read_back = lakehouse.read_golden_records()
    assert len(read_back) == len(golden_frame)
    assert read_back["cluster_id"].is_unique


def test_each_write_creates_a_new_snapshot(lakehouse, golden_frame):
    """Writes are published as snapshots, which is what makes them atomic.

    A reader holds a snapshot for the duration of its scan, so it never
    observes a half-written table.
    """
    first = lakehouse.write_golden_records(golden_frame)
    second = lakehouse.write_golden_records(golden_frame)
    assert second.snapshot_count > first.snapshot_count


def test_appending_adds_to_the_existing_table(lakehouse, golden_frame):
    """Incremental batches append rather than replace."""
    lakehouse.write_golden_records(golden_frame)
    extra = golden_frame.copy()
    extra["cluster_id"] = ["r0000009", "r0000010"]
    extra["source_record_ids"] = ["r0000009", "r0000010"]
    extra["source_record_count"] = [1, 1]

    lakehouse.write_golden_records(extra, append=True)
    assert len(lakehouse.read_golden_records()) == len(golden_frame) + len(extra)

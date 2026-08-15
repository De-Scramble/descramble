# SPDX-License-Identifier: Apache-2.0
"""Input handling, watermarking, and configuration."""

from __future__ import annotations

import pandas as pd
import pytest

from descramble.config import PipelineConfig
from descramble.reader import (
    InputError,
    Watermark,
    iter_batches,
    read_records,
    select_new_records,
)
from descramble.sampledata import generate_records, write_csv

VALID_ROWS = [
    {"record_id": "r0000001", "first_name": "Esther", "last_name": "Braithwaite",
     "email": "e.braithwaite@example.com", "postcode": "AB1 2CD", "city": "Ashford"},
    {"record_id": "r0000002", "first_name": "Fergus", "last_name": "Danvers",
     "email": "fergus@example.net", "postcode": "ZZ9 9ZZ", "city": "Fenwick"},
]


def _write(tmp_path, rows, name="records.csv"):
    frame = pd.DataFrame(rows)
    path = tmp_path / name
    frame.to_csv(path, index=False)
    return path


def test_reads_csv(tmp_path):
    frame = read_records(_write(tmp_path, VALID_ROWS))
    assert len(frame) == 2
    assert list(frame.columns) == [
        "record_id", "first_name", "last_name", "email", "postcode", "city",
    ]


def test_reads_parquet(tmp_path):
    """Format is chosen from the extension; the pipeline is not CSV-only."""
    path = tmp_path / "records.parquet"
    pd.DataFrame(VALID_ROWS).to_parquet(path, index=False)
    assert len(read_records(path)) == 2


def test_values_are_read_as_text(tmp_path):
    """Leading zeros in a postcode survive.

    Identity fields are not quantities. Reading '01234' as an integer destroys
    it, and the damage shows up later as an unexplained failure to match.
    """
    rows = [dict(VALID_ROWS[0], postcode="01234"), VALID_ROWS[1]]
    frame = read_records(_write(tmp_path, rows))
    assert frame.loc[frame["record_id"] == "r0000001", "postcode"].iloc[0] == "01234"


def test_missing_file_is_reported_usefully(tmp_path):
    with pytest.raises(InputError, match="not found"):
        read_records(tmp_path / "absent.csv")


def test_missing_column_is_reported_by_name(tmp_path):
    rows = [{k: v for k, v in row.items() if k != "email"} for row in VALID_ROWS]
    with pytest.raises(InputError, match="email"):
        read_records(_write(tmp_path, rows))


def test_unsupported_format_is_rejected(tmp_path):
    path = tmp_path / "records.txt"
    path.write_text("nothing useful", encoding="utf-8")
    with pytest.raises(InputError, match="unsupported input format"):
        read_records(path)


def test_repeated_record_id_is_rejected(tmp_path):
    """The identifier must identify a row.

    A repeated value is silently destructive: it makes two different rows
    indistinguishable to everything downstream, including the matcher.
    """
    rows = [VALID_ROWS[0], dict(VALID_ROWS[1], record_id="r0000001")]
    with pytest.raises(InputError, match="unique"):
        read_records(_write(tmp_path, rows))


def test_empty_input_is_rejected(tmp_path):
    path = _write(tmp_path, [])
    pd.DataFrame(columns=list(VALID_ROWS[0])).to_csv(path, index=False)
    with pytest.raises(InputError, match="no records"):
        read_records(path)


def test_batches_cover_every_record_once(tmp_path):
    rows, _ = generate_records(people=60, seed=7)
    path = write_csv(rows, tmp_path / "many.csv")

    batches = list(iter_batches(path, batch_size=25))
    assert len(batches) > 1
    assert sum(len(batch) for batch in batches) == len(rows)

    seen = [rid for batch in batches for rid in batch["record_id"]]
    assert len(seen) == len(set(seen))
    assert seen == sorted(seen), "batch order is not stable"


def test_watermark_round_trips(tmp_path):
    mark = Watermark(tmp_path / ".watermark.json")
    assert mark.load() is None

    mark.save("r0000042", records_processed=42)
    assert mark.load() == "r0000042"

    mark.clear()
    assert mark.load() is None


def test_watermark_survives_a_corrupt_file(tmp_path):
    """A damaged watermark means 'start over', not 'crash'.

    Reprocessing is safe because the write is idempotent; refusing to run is
    not.
    """
    path = tmp_path / ".watermark.json"
    path.write_text("{ this is not json", encoding="utf-8")
    assert Watermark(path).load() is None


def test_only_records_after_the_mark_are_selected(tmp_path):
    frame = read_records(_write(tmp_path, VALID_ROWS))
    assert len(select_new_records(frame, None)) == 2
    assert len(select_new_records(frame, "r0000001")) == 1
    assert len(select_new_records(frame, "r0000002")) == 0


def test_threshold_must_be_a_probability():
    with pytest.raises(ValueError, match="threshold"):
        PipelineConfig(match_threshold=1.5).validate()
    with pytest.raises(ValueError, match="threshold"):
        PipelineConfig(match_threshold=0.0).validate()


def test_warehouse_uri_is_usable_on_this_platform(tmp_path):
    """The warehouse URI keeps a form PyIceberg accepts.

    On Windows the obvious construction yields 'file:///C:/...', whose leading
    slash makes the path unusable once the scheme is stripped. This asserts the
    working form on whichever platform the suite is running.
    """
    config = PipelineConfig(warehouse_dir=tmp_path / "warehouse")
    uri = config.warehouse_uri

    assert uri.startswith("file://")
    assert not uri.startswith("file:///C:")
    assert "\\" not in uri


def test_environment_overrides_defaults(monkeypatch):
    monkeypatch.setenv("DESCRAMBLE_THRESHOLD", "0.75")
    monkeypatch.setenv("DESCRAMBLE_TABLE", "resolved")
    config = PipelineConfig.from_environment()
    assert config.match_threshold == 0.75
    assert config.table_name == "resolved"


def test_unreadable_environment_value_is_reported(monkeypatch):
    monkeypatch.setenv("DESCRAMBLE_THRESHOLD", "not-a-number")
    with pytest.raises(ValueError, match="DESCRAMBLE_THRESHOLD"):
        PipelineConfig.from_environment()

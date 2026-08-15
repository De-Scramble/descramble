# SPDX-License-Identifier: Apache-2.0
"""Survivorship rules.

These run without the linkage engine: clusters are supplied directly, so the
election logic is tested on its own rather than through a probabilistic model
whose output would obscure it.
"""

from __future__ import annotations

import pandas as pd

from descramble.golden import GOLDEN_COLUMNS, build_golden_records


def _records(rows: list[dict[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _clusters(assignment: dict[str, str]) -> pd.DataFrame:
    return pd.DataFrame(
        {"record_id": list(assignment), "cluster_id": list(assignment.values())}
    )


def test_majority_value_wins():
    """The value most records agree on survives — damage is usually the minority."""
    records = _records(
        [
            {"record_id": "r1", "first_name": "Imogen", "last_name": "Sedgwick",
             "email": "i@example.com", "postcode": "AB1 2CD", "city": "Ashford"},
            {"record_id": "r2", "first_name": "Imogen", "last_name": "Sedgwick",
             "email": "i@example.com", "postcode": "AB1 2CD", "city": "Ashford"},
            {"record_id": "r3", "first_name": "Imogen", "last_name": "Sedgwikc",
             "email": "i@example.com", "postcode": "AB1 2CD", "city": "Ashford"},
        ]
    )
    golden = build_golden_records(records, _clusters({"r1": "c", "r2": "c", "r3": "c"}))

    assert len(golden) == 1
    assert golden.loc[0, "last_name"] == "Sedgwick"
    assert golden.loc[0, "source_record_count"] == 3


def test_ties_are_broken_deterministically():
    """With no majority the outcome is still fixed, not arbitrary run to run."""
    records = _records(
        [
            {"record_id": "r1", "first_name": "Rowena", "last_name": "Alderton",
             "email": "a@example.com", "postcode": "AB1 2CD", "city": "Ashford"},
            {"record_id": "r2", "first_name": "Rowena", "last_name": "Aldertone",
             "email": "a@example.com", "postcode": "AB1 2CD", "city": "Ashford"},
        ]
    )
    golden = build_golden_records(records, _clusters({"r1": "c", "r2": "c"}))
    assert golden.loc[0, "last_name"] == "Alderton"  # lexicographically smallest


def test_blank_values_never_win():
    """A field is blank in the result only if it was blank in every source record."""
    records = _records(
        [
            {"record_id": "r1", "first_name": "Magnus", "last_name": "Loxley",
             "email": "m@example.com", "postcode": "AB1 2CD", "city": ""},
            {"record_id": "r2", "first_name": "Magnus", "last_name": "Loxley",
             "email": "m@example.com", "postcode": "AB1 2CD", "city": ""},
            {"record_id": "r3", "first_name": "Magnus", "last_name": "Loxley",
             "email": "m@example.com", "postcode": "AB1 2CD", "city": "Kestrelby"},
        ]
    )
    golden = build_golden_records(records, _clusters({"r1": "c", "r2": "c", "r3": "c"}))
    assert golden.loc[0, "city"] == "Kestrelby"


def test_field_stays_blank_when_no_record_has_it():
    records = _records(
        [
            {"record_id": "r1", "first_name": "Verity", "last_name": "Oakhurst",
             "email": "v@example.com", "postcode": "AB1 2CD", "city": ""},
            {"record_id": "r2", "first_name": "Verity", "last_name": "Oakhurst",
             "email": "v@example.com", "postcode": "AB1 2CD", "city": ""},
        ]
    )
    golden = build_golden_records(records, _clusters({"r1": "c", "r2": "c"}))
    assert golden.loc[0, "city"] == ""


def test_singleton_records_survive_as_their_own_golden_record():
    """Someone who appears once is a person, not a reject."""
    records = _records(
        [
            {"record_id": "r1", "first_name": "Tamsin", "last_name": "Voysey",
             "email": "t@example.com", "postcode": "AB1 2CD", "city": "Fenwick"},
            {"record_id": "r2", "first_name": "Orlando", "last_name": "Kirkbride",
             "email": "o@example.com", "postcode": "ZZ9 9ZZ", "city": "Oakhaven"},
        ]
    )
    golden = build_golden_records(records, _clusters({"r1": "c1", "r2": "c2"}))
    assert len(golden) == 2
    assert set(golden["source_record_count"]) == {1}


def test_output_shape_and_traceability():
    """Every golden record names the source records it came from."""
    records = _records(
        [
            {"record_id": "r5", "first_name": "Gideon", "last_name": "Prescott",
             "email": "g@example.com", "postcode": "AB1 2CD", "city": "Fenwick"},
            {"record_id": "r2", "first_name": "Gideon", "last_name": "Prescott",
             "email": "g@example.com", "postcode": "AB1 2CD", "city": "Fenwick"},
        ]
    )
    golden = build_golden_records(records, _clusters({"r5": "c", "r2": "c"}))

    assert list(golden.columns) == list(GOLDEN_COLUMNS)
    assert golden.loc[0, "source_record_ids"] == "r2,r5"
    assert golden.loc[0, "cluster_id"] == "r2"

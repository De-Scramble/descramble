# SPDX-License-Identifier: Apache-2.0
"""Survivorship — collapsing a cluster of matched records into one.

Linkage decides *which* records describe the same person. It does not decide
what that person's name is. When three records agree that they are the same
individual but disagree about the spelling of their surname, something has to
choose, and the choice must be explainable and repeatable.

The rule used here is plurality with a deterministic tie-break: for each field,
take the value that appears most often among the cluster's records, and settle
ties by choosing the lexicographically smallest. Blank values never win, and a
field is blank in the golden record only when it is blank in every source
record.

Plurality is the right default because damage is usually the minority: one
typo among three clean spellings loses. Its limitation is honest and worth
stating — where a cluster has no majority, plurality has no real opinion and
the tie-break is arbitrary but at least stable. Recency would beat plurality
where records carry reliable timestamps, and this is where that rule would go.

Cluster identifiers are derived here rather than taken from the linkage engine:
the identifier is the smallest ``record_id`` in the cluster. That makes it a
stable, meaningful property of the cluster's membership, so the same input
yields the same identifiers on every run and on any backend.
"""

from __future__ import annotations

from collections import Counter

import pandas as pd

from descramble.config import RECORD_ID_COLUMN

#: Fields carried into the golden record, in output order.
SURVIVING_COLUMNS = ("first_name", "last_name", "email", "postcode", "city")

GOLDEN_COLUMNS = (
    "cluster_id",
    *SURVIVING_COLUMNS,
    "source_record_count",
    "source_record_ids",
)


def _elect(values: list[str]) -> str:
    """Pick the surviving value: most frequent, ties broken lexicographically."""
    populated = [value for value in values if value and value.strip()]
    if not populated:
        return ""
    counts = Counter(populated)
    best = max(counts.values())
    return min(value for value, count in counts.items() if count == best)


def build_golden_records(records: pd.DataFrame, clusters: pd.DataFrame) -> pd.DataFrame:
    """Collapse clustered records into one resolved record per cluster.

    Args:
        records: the input records, one row per source record.
        clusters: ``record_id`` to ``cluster_id``, as produced by linkage.

    Returns:
        One row per resolved person, ordered by cluster identifier, carrying the
        surviving field values, how many source records were merged, and exactly
        which ones — so any golden record can be traced back to its inputs.
    """
    joined = records.merge(clusters, on=RECORD_ID_COLUMN, how="left", validate="one_to_one")

    # A record that took part in no scored pair has no cluster; it is simply a
    # person who appears once. It stands alone rather than being dropped.
    missing = joined["cluster_id"].isna()
    if bool(missing.any()):
        joined.loc[missing, "cluster_id"] = joined.loc[missing, RECORD_ID_COLUMN]

    grouped: dict[str, list[dict[str, str]]] = {}
    for row in joined.to_dict("records"):
        grouped.setdefault(str(row["cluster_id"]), []).append(row)

    resolved: list[dict[str, object]] = []
    for members in grouped.values():
        member_ids = sorted(str(member[RECORD_ID_COLUMN]) for member in members)
        golden: dict[str, object] = {"cluster_id": member_ids[0]}
        for column in SURVIVING_COLUMNS:
            golden[column] = _elect([str(member.get(column, "") or "") for member in members])
        golden["source_record_count"] = len(member_ids)
        golden["source_record_ids"] = ",".join(member_ids)
        resolved.append(golden)

    frame = pd.DataFrame(resolved, columns=list(GOLDEN_COLUMNS))
    frame["source_record_count"] = frame["source_record_count"].astype("int64")
    return frame.sort_values("cluster_id", kind="stable").reset_index(drop=True)

# SPDX-License-Identifier: Apache-2.0
"""Apache Iceberg output — the lakehouse half.

Resolved records are worth little if the act of publishing them breaks the
things reading them. Writing to plain files has an ugly failure mode: a reader
arriving mid-write sees a directory that is half old and half new, and there is
no way for it to tell. The usual workarounds — write to a temporary location,
then move; or take a lock and make everyone wait — either are not atomic across
storage systems, or trade availability for safety.

Iceberg's answer is a layer of indirection. A table is a set of immutable data
files plus metadata listing which files make up the current **snapshot**.
Writing adds new files, which no reader is looking at, and then swaps a single
metadata pointer. That swap is atomic, so every reader sees either the whole
previous snapshot or the whole new one, never a mixture. Readers are never
blocked by a writer, and each reader is consistent for the duration of its scan.

That property is what makes the hub-and-spoke arrangement work: one table is
written once and read by many independent consumers, none of which need a copy
of the data and none of which can observe a partial write.

The default catalogue here is a local SQLite database and the default warehouse
is a local directory, so the pipeline runs end to end with no cloud account and
no running service. Swapping in object storage and a shared catalogue changes
configuration, not code.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pyarrow as pa
from pyiceberg.catalog.sql import SqlCatalog

from descramble.config import PipelineConfig
from descramble.golden import GOLDEN_COLUMNS

#: Explicit output schema. Stated rather than inferred, because an inferred
#: schema silently changes shape when the input does, and a table whose column
#: types depend on the data that happened to arrive first is not a contract.
GOLDEN_SCHEMA = pa.schema(
    [
        pa.field("cluster_id", pa.string(), nullable=False),
        pa.field("first_name", pa.string()),
        pa.field("last_name", pa.string()),
        pa.field("email", pa.string()),
        pa.field("postcode", pa.string()),
        pa.field("city", pa.string()),
        pa.field("source_record_count", pa.int64(), nullable=False),
        pa.field("source_record_ids", pa.string(), nullable=False),
    ]
)


@dataclass
class WriteSummary:
    rows_written: int
    table_location: str
    snapshot_count: int


class Lakehouse:
    """A local-by-default Iceberg destination for golden records."""

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self._catalog: SqlCatalog | None = None

    def catalog(self) -> SqlCatalog:
        if self._catalog is None:
            Path(self.config.warehouse_dir).mkdir(parents=True, exist_ok=True)
            self._catalog = SqlCatalog(
                self.config.catalog_name,
                **{
                    "uri": self.config.catalog_uri,
                    "warehouse": self.config.warehouse_uri,
                },
            )
        return self._catalog

    def _table(self):
        catalog = self.catalog()
        catalog.create_namespace_if_not_exists(self.config.namespace)
        return catalog.create_table_if_not_exists(
            self.config.table_identifier, schema=GOLDEN_SCHEMA
        )

    @staticmethod
    def to_arrow(frame: pd.DataFrame) -> pa.Table:
        ordered = frame.loc[:, list(GOLDEN_COLUMNS)]
        return pa.Table.from_pandas(ordered, schema=GOLDEN_SCHEMA, preserve_index=False)

    def write_golden_records(self, frame: pd.DataFrame, append: bool = False) -> WriteSummary:
        """Publish golden records as a new snapshot.

        The default replaces the table's contents rather than appending. A full
        resolution run is a statement about the whole input, so re-running it
        should leave one authoritative set of golden records, not two
        overlapping generations of them. That makes repeated runs idempotent:
        run the same input twice and the table holds the same rows, once.

        Pass ``append=True`` when adding an incremental batch that has been
        resolved separately.
        """
        table = self._table()
        arrow_table = self.to_arrow(frame)
        # Overwriting a table that has never been written is a delete matching
        # nothing. Appending to the empty table is the same result without the
        # pointless delete.
        if append or not table.metadata.snapshots:
            table.append(arrow_table)
        else:
            table.overwrite(arrow_table)
        return WriteSummary(
            rows_written=arrow_table.num_rows,
            table_location=table.location(),
            snapshot_count=len(list(table.metadata.snapshots)),
        )

    def read_golden_records(self) -> pd.DataFrame:
        """Read the current snapshot back, in a stable order."""
        table = self._table()
        frame = table.scan().to_arrow().to_pandas()
        if frame.empty:
            return pd.DataFrame(columns=list(GOLDEN_COLUMNS))
        return (
            frame.loc[:, list(GOLDEN_COLUMNS)]
            .sort_values("cluster_id", kind="stable")
            .reset_index(drop=True)
        )

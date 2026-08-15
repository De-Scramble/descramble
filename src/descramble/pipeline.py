# SPDX-License-Identifier: Apache-2.0
"""The pipeline: read records, resolve identities, publish golden records."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from descramble.config import RECORD_ID_COLUMN, PipelineConfig
from descramble.golden import build_golden_records
from descramble.lakehouse import Lakehouse
from descramble.reader import Watermark, read_records, select_new_records
from descramble.resolve import resolve_records

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """What a run did, in the terms a person actually wants to know."""

    input_records: int
    golden_records: int
    duplicate_clusters: int
    records_merged_away: int
    candidate_pairs: int
    all_possible_pairs: int
    blocking_reduction_ratio: float
    threshold: float
    table_location: str = ""
    snapshot_count: int = 0
    written: bool = False
    golden: pd.DataFrame = field(default_factory=pd.DataFrame, repr=False)

    def summary_lines(self) -> list[str]:
        reduction = f"{self.blocking_reduction_ratio * 100:.2f}%"
        lines = [
            f"{self.input_records:,} raw records "
            f"-> {self.golden_records:,} golden records",
            f"{self.duplicate_clusters:,} duplicate clusters resolved, "
            f"{self.records_merged_away:,} redundant records merged away",
            f"blocking considered {self.candidate_pairs:,} candidate pairs "
            f"out of {self.all_possible_pairs:,} possible ({reduction} removed)",
            f"match threshold {self.threshold}",
        ]
        if self.written:
            lines.append(f"written to Iceberg table at {self.table_location}")
            lines.append(f"table now holds {self.snapshot_count} snapshot(s)")
        return lines


def run_pipeline(
    config: PipelineConfig,
    write: bool = True,
    incremental: bool = False,
) -> PipelineResult:
    """Resolve the configured input and, by default, publish the result.

    Args:
        config: validated pipeline settings.
        write: publish golden records to the lakehouse. Turning this off is
            useful for evaluating match quality without touching the table.
        incremental: process only records newer than the stored watermark, and
            append rather than replace. Records already resolved are not
            reconsidered, so this trades completeness for cost — appropriate
            when the input only ever grows.
    """
    config = config.validate()
    records = read_records(config.input_path)
    watermark = Watermark(config.warehouse_dir / ".watermark.json")

    if incremental:
        mark = watermark.load()
        records = select_new_records(records, mark)
        if records.empty:
            logger.info("no records newer than watermark %s; nothing to do", mark)
            return PipelineResult(
                input_records=0,
                golden_records=0,
                duplicate_clusters=0,
                records_merged_away=0,
                candidate_pairs=0,
                all_possible_pairs=0,
                blocking_reduction_ratio=0.0,
                threshold=config.match_threshold,
            )

    linkage = resolve_records(records, config)
    golden = build_golden_records(records, linkage.clusters)

    duplicate_clusters = int((golden["source_record_count"] > 1).sum())
    result = PipelineResult(
        input_records=len(records),
        golden_records=len(golden),
        duplicate_clusters=duplicate_clusters,
        records_merged_away=len(records) - len(golden),
        candidate_pairs=linkage.candidate_pairs,
        all_possible_pairs=linkage.all_possible_pairs,
        blocking_reduction_ratio=linkage.blocking_reduction_ratio,
        threshold=config.match_threshold,
        golden=golden,
    )

    if write:
        summary = Lakehouse(config).write_golden_records(golden, append=incremental)
        result.table_location = summary.table_location
        result.snapshot_count = summary.snapshot_count
        result.written = True
        # Advance the mark only now that the write has succeeded. Doing it
        # earlier would let a failed write silently skip records forever.
        highest = str(records[RECORD_ID_COLUMN].max())
        watermark.save(highest, len(records))

    return result

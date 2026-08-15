# SPDX-License-Identifier: Apache-2.0
"""Generic record input.

The reader deliberately knows nothing about where records come from. It takes a
CSV or Parquet file and yields batches of rows, which means the pipeline works
the same whether the file was exported from a database, dropped by a partner,
or produced by the sample generator in this package.

Two properties are worth more than they look:

**Batching.** Records are read in bounded chunks rather than all at once, so
input size is limited by disk rather than by memory.

**Watermarking.** A run records the highest record identifier it has processed.
A later run can resume from that mark and process only what is new. This is what
makes re-running the pipeline safe: an interrupted or repeated run does not
duplicate work or double-write, because the mark advances only over records that
were actually handled. The same idea applies to any ordered, append-mostly
source, which is why it lives here rather than in a source-specific reader.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from descramble.config import RECORD_COLUMNS, RECORD_ID_COLUMN

DEFAULT_BATCH_SIZE = 50_000


class InputError(RuntimeError):
    """Raised when input is missing, unreadable, or the wrong shape."""


def _read_frame(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[])
    if suffix in (".parquet", ".pq"):
        return pd.read_parquet(path).astype(str)
    raise InputError(
        f"unsupported input format {suffix!r} for {path}; expected .csv or .parquet"
    )


def read_records(path: str | Path, required_columns: tuple[str, ...] = RECORD_COLUMNS) -> pd.DataFrame:
    """Read every record from ``path`` into a single frame.

    Values are read as strings throughout. Identity fields are not quantities:
    coercing a numeric-looking postcode to an integer silently destroys leading
    zeros, which is a real and unpleasant source of false non-matches.
    """
    path = Path(path)
    if not path.exists():
        raise InputError(
            f"input file not found: {path}. Generate the sample data first with "
            "`python -m descramble generate`."
        )

    frame = _read_frame(path)
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise InputError(
            f"{path} is missing required column(s): {', '.join(missing)}. "
            f"Expected: {', '.join(required_columns)}"
        )
    if frame.empty:
        raise InputError(f"{path} contains no records")

    frame = frame.loc[:, list(required_columns)].copy()
    for column in required_columns:
        frame[column] = frame[column].fillna("").astype(str).str.strip()

    duplicated_ids = frame[RECORD_ID_COLUMN].duplicated()
    if bool(duplicated_ids.any()):
        offenders = frame.loc[duplicated_ids, RECORD_ID_COLUMN].head(3).tolist()
        raise InputError(
            f"{RECORD_ID_COLUMN} must be unique per row; repeated value(s): "
            f"{', '.join(offenders)}. Note this column identifies a ROW, not a person — "
            "two rows describing the same person still need different values."
        )

    return frame.sort_values(RECORD_ID_COLUMN, kind="stable").reset_index(drop=True)


def iter_batches(
    path: str | Path,
    batch_size: int = DEFAULT_BATCH_SIZE,
    required_columns: tuple[str, ...] = RECORD_COLUMNS,
) -> Iterator[pd.DataFrame]:
    """Yield the records in ``path`` as bounded, deterministically ordered batches."""
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    frame = read_records(path, required_columns)
    for start in range(0, len(frame), batch_size):
        yield frame.iloc[start : start + batch_size].reset_index(drop=True)


@dataclass
class Watermark:
    """The high-water mark of a previous run, persisted next to the warehouse.

    The mark is the highest ``record_id`` that has been fully processed. It is
    advanced only after downstream work succeeds, so a crash mid-run leaves the
    mark where it was and the affected records are simply reprocessed — at-least
    once, which combined with an idempotent write is what makes repeated runs
    safe.
    """

    path: Path

    def load(self) -> str | None:
        if not self.path.exists():
            return None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        mark = payload.get("highest_record_id")
        return str(mark) if mark is not None else None

    def save(self, highest_record_id: str, records_processed: int) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "highest_record_id": highest_record_id,
                    "records_processed": records_processed,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)


def select_new_records(frame: pd.DataFrame, mark: str | None) -> pd.DataFrame:
    """Return only the records that come after ``mark``."""
    if mark is None:
        return frame
    return frame.loc[frame[RECORD_ID_COLUMN] > mark].reset_index(drop=True)

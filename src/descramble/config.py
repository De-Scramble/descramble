# SPDX-License-Identifier: Apache-2.0
"""Pipeline settings.

Settings resolve in a single, predictable order: an explicit argument beats an
environment variable, which beats the built-in default. Every default is chosen
so that a freshly cloned checkout runs with no configuration whatsoever.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

#: Column holding the identifier unique to each *input* record. It identifies a
#: row, not a person: two rows describing the same person have different values
#: here, which is precisely the problem this project exists to solve.
RECORD_ID_COLUMN = "record_id"

#: The generic, person-like schema the pipeline resolves on. Deliberately plain:
#: these are the fields that vary in messy real-world data, and nothing here is
#: specific to any industry or dataset.
RECORD_COLUMNS = (
    RECORD_ID_COLUMN,
    "first_name",
    "last_name",
    "email",
    "postcode",
    "city",
)

DEFAULT_SEED = 1729
DEFAULT_THRESHOLD = 0.9


def _env_path(name: str, fallback: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw) if raw else fallback


def _env_float(name: str, fallback: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return fallback
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc


def _env_int(name: str, fallback: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return fallback
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a whole number, got {raw!r}") from exc


@dataclass(frozen=True)
class PipelineConfig:
    """Everything the pipeline needs to know, resolved and validated."""

    input_path: Path = Path("data/sample_records.csv")
    warehouse_dir: Path = Path("warehouse")
    catalog_name: str = "descramble"
    namespace: str = "descramble"
    table_name: str = "golden_records"
    match_threshold: float = DEFAULT_THRESHOLD
    seed: int = DEFAULT_SEED
    max_pairs_for_estimation: int = 10_000_000

    @classmethod
    def from_environment(cls) -> "PipelineConfig":
        """Build a config from environment variables, falling back to defaults."""
        base = cls()
        return cls(
            input_path=_env_path("DESCRAMBLE_INPUT", base.input_path),
            warehouse_dir=_env_path("DESCRAMBLE_WAREHOUSE", base.warehouse_dir),
            catalog_name=os.environ.get("DESCRAMBLE_CATALOG", base.catalog_name),
            namespace=os.environ.get("DESCRAMBLE_NAMESPACE", base.namespace),
            table_name=os.environ.get("DESCRAMBLE_TABLE", base.table_name),
            match_threshold=_env_float("DESCRAMBLE_THRESHOLD", base.match_threshold),
            seed=_env_int("DESCRAMBLE_SEED", base.seed),
        )

    def with_overrides(self, **overrides: object) -> "PipelineConfig":
        """Return a copy with the non-``None`` overrides applied."""
        supplied = {k: v for k, v in overrides.items() if v is not None}
        return replace(self, **supplied) if supplied else self

    def validate(self) -> "PipelineConfig":
        if not 0.0 < self.match_threshold <= 1.0:
            raise ValueError(
                f"match threshold must be above 0 and at most 1, got {self.match_threshold}"
            )
        if not self.table_name or not self.namespace:
            raise ValueError("namespace and table name must both be non-empty")
        return self

    @property
    def table_identifier(self) -> tuple[str, str]:
        return (self.namespace, self.table_name)

    @property
    def catalog_uri(self) -> str:
        """SQLAlchemy URI for the local SQLite catalogue backing the warehouse."""
        return f"sqlite:///{(self.warehouse_dir / 'catalog.db').resolve().as_posix()}"

    @property
    def warehouse_uri(self) -> str:
        """Warehouse location as a URI PyIceberg accepts on every platform.

        The form matters more than it looks. ``Path.as_uri()`` yields
        ``file:///C:/...`` on Windows, and the leading slash before the drive
        letter makes the path unusable once the scheme is stripped off again.
        Prefixing the POSIX form instead produces ``file:///home/...`` on
        POSIX systems and ``file://C:/...`` on Windows — both of which resolve
        correctly.
        """
        return "file://" + self.warehouse_dir.resolve().as_posix()

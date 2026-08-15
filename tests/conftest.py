# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures.

Linkage is the expensive part of the suite, so the resolved result is computed
once per session and shared. Tests that need to compare two independent runs
build their own.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations

import pandas as pd
import pytest

from descramble.config import PipelineConfig
from descramble.golden import build_golden_records
from descramble.reader import read_records
from descramble.resolve import LinkageResult, resolve_records
from descramble.sampledata import GenerationSummary, generate_records, write_csv

#: Small enough to keep the suite quick, large enough for parameter estimation
#: to have something to work with.
TEST_PEOPLE = 300
TEST_SEED = 1729


def pair_set(assignment: dict[str, str]) -> set[tuple[str, str]]:
    """Every within-group pair implied by a record-to-group assignment.

    Comparing linkage against ground truth is done on pairs rather than on
    group labels, because the labels themselves are arbitrary: what matters is
    which records were placed together, not what their cluster ended up called.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for record_id, group_id in assignment.items():
        groups[group_id].append(record_id)
    return {
        pair
        for members in groups.values()
        for pair in combinations(sorted(members), 2)
    }


@dataclass
class ResolvedSample:
    records: pd.DataFrame
    summary: GenerationSummary
    linkage: LinkageResult
    golden: pd.DataFrame
    config: PipelineConfig

    @property
    def true_pairs(self) -> set[tuple[str, str]]:
        return pair_set(self.summary.truth)

    @property
    def predicted_pairs(self) -> set[tuple[str, str]]:
        assignment = dict(
            zip(self.linkage.clusters["record_id"], self.linkage.clusters["cluster_id"])
        )
        return pair_set(assignment)

    @property
    def precision(self) -> float:
        predicted = self.predicted_pairs
        if not predicted:
            return 0.0
        return len(self.true_pairs & predicted) / len(predicted)

    @property
    def recall(self) -> float:
        true = self.true_pairs
        if not true:
            return 0.0
        return len(true & self.predicted_pairs) / len(true)


@pytest.fixture(scope="session")
def sample_csv(tmp_path_factory) -> tuple[object, GenerationSummary]:
    directory = tmp_path_factory.mktemp("sample")
    rows, summary = generate_records(people=TEST_PEOPLE, seed=TEST_SEED)
    return write_csv(rows, directory / "records.csv"), summary


@pytest.fixture(scope="session")
def resolved(sample_csv, tmp_path_factory) -> ResolvedSample:
    path, summary = sample_csv
    config = PipelineConfig(
        input_path=path,
        warehouse_dir=tmp_path_factory.mktemp("warehouse"),
    ).validate()
    records = read_records(path)
    linkage = resolve_records(records, config)
    golden = build_golden_records(records, linkage.clusters)
    return ResolvedSample(records, summary, linkage, golden, config)

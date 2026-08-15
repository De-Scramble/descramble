# SPDX-License-Identifier: Apache-2.0
"""Linkage correctness.

The two failures that matter pull in opposite directions, and a test suite that
only guards one of them is worse than useless — it certifies a system that has
quietly gone wrong in the other direction. Merging nothing scores perfectly on
precision; merging everything scores perfectly on recall. Both are asserted
here, against generated ground truth.

The thresholds are floors, not targets. They sit below measured performance
with enough room that ordinary variation does not turn the suite red, and close
enough that a real regression does.
"""

from __future__ import annotations

MINIMUM_RECALL = 0.90
MINIMUM_PRECISION = 0.95


def test_known_duplicates_are_clustered_together(resolved):
    """Records describing the same person end up in the same cluster."""
    recall = resolved.recall
    assert recall >= MINIMUM_RECALL, (
        f"only {recall:.1%} of true duplicate pairs were clustered together "
        f"(floor {MINIMUM_RECALL:.0%}); duplicates are being missed"
    )


def test_distinct_people_are_not_merged(resolved):
    """Records describing different people stay apart."""
    precision = resolved.precision
    assert precision >= MINIMUM_PRECISION, (
        f"only {precision:.1%} of clustered pairs are genuine duplicates "
        f"(floor {MINIMUM_PRECISION:.0%}); distinct people are being merged"
    )


def test_every_input_record_appears_in_exactly_one_golden_record(resolved):
    """No record is lost, and none is counted twice.

    Survivorship must partition the input. A record that vanishes is silent
    data loss; a record in two golden records means the same person is counted
    more than once downstream.
    """
    contributing = [
        record_id
        for ids in resolved.golden["source_record_ids"]
        for record_id in ids.split(",")
    ]
    assert len(contributing) == len(set(contributing)), "a record appears in two clusters"
    assert set(contributing) == set(resolved.records["record_id"]), (
        "the golden records do not account for exactly the input records"
    )
    assert int(resolved.golden["source_record_count"].sum()) == len(resolved.records)


def test_resolution_reduces_the_record_count(resolved):
    """The pipeline actually deduplicates, and does not over-collapse.

    Ground truth says how many people there are. The result should land near
    it — meaningfully fewer rows than the input, and not far below the true
    number of people.
    """
    people = resolved.summary.distinct_people
    produced = len(resolved.golden)
    assert produced < len(resolved.records), "no duplicates were resolved at all"
    assert 0.90 * people <= produced <= 1.15 * people, (
        f"{produced} golden records against {people} real people is too far off"
    )


def test_blocking_removes_the_vast_majority_of_comparisons(resolved):
    """Blocking is doing its job.

    Without it the comparison count is quadratic and the pipeline does not
    scale at all, so a collapse in the reduction ratio is a scaling regression
    even when accuracy looks fine.
    """
    assert resolved.linkage.blocking_reduction_ratio > 0.95
    assert resolved.linkage.candidate_pairs < resolved.linkage.all_possible_pairs

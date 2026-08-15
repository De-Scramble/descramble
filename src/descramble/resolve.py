# SPDX-License-Identifier: Apache-2.0
"""Probabilistic record linkage — the Fellegi-Sunter model, via Splink.

The problem in one line: the same person appears in your data more than once,
under spellings that no equality test will ever reconcile.

The Fellegi-Sunter answer is to stop asking "are these two records equal?" and
start asking "how much more likely is this pattern of agreement if the records
describe the same person than if they do not?" For a candidate pair, each field
is compared and reduced to a comparison level — exact, near, different — and the
resulting vector is scored with two probabilities per level:

* **m** — probability of observing this level *given the records match*. Typos
  are common, so agreeing exactly on a surname is likely but not certain.
* **u** — probability of observing this level *given the records do not match*.
  Two unrelated people rarely share a surname, so this is small.

The ratio ``m/u`` for a level is its Bayes factor: how much observing it should
shift belief. Multiply the factors across fields, apply them to a prior about
how often two randomly chosen records match, and the result is a posterior match
probability for the pair. Records are then grouped by connected components at a
threshold on that probability.

The m and u values are not guessed. u is estimated from random pairs, which are
overwhelmingly non-matches; m is estimated by expectation-maximisation, which
alternates between scoring pairs with the current parameters and re-estimating
the parameters from those scores until they settle.

**Blocking** is what makes any of this tractable. Comparing every pair is
quadratic — a million records is five hundred billion pairs, which is not a
tuning problem but an arithmetic one. Instead, candidate pairs are generated
only within blocks that agree on something cheap and selective: the same email,
or the same surname and postcode. Recall depends on using several complementary
rules, so that a pair missed by one is caught by another.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd
import splink.comparison_library as cl
from splink import DuckDBAPI, Linker, SettingsCreator, block_on

from descramble.config import RECORD_ID_COLUMN, PipelineConfig

logger = logging.getLogger(__name__)

#: Columns compared when scoring a candidate pair.
COMPARISON_COLUMNS = ("first_name", "last_name", "email", "postcode", "city")


def blocking_rules() -> list:
    """Candidate-pair rules. Each is cheap, selective, and covers the others' gaps.

    * **email** — the strongest single signal, but blind to a mistyped address.
    * **surname + postcode** — catches a changed or mistyped email, and stays
      selective because the pair is far rarer than either part alone.
    * **given name + city** — the fallback for a mistyped surname, which the
      previous rule depends on.
    * **first two letters of each name** — catches a typo anywhere after the
      second character, which is where most of them land.
    * **postcode** — deliberately weaker than the rules above, and worth it.
      It is the only rule that still fires when the email *and* both names are
      damaged in the same record.

    A pair missed by every rule is never scored at all, so recall is bounded by
    this list before the model sees anything. The rules are therefore chosen for
    complementary blind spots rather than individual strength: each one covers a
    case that damages the others.

    On the bundled sample, these five rules consider roughly 4,700 candidate
    pairs out of 5.0 million possible — a 99.9% reduction — and recall the great
    majority of true duplicates. Recall can be pushed higher by adding a rule on
    a prefix of the email local part, but on this data that costs about five
    times the comparisons for a fraction of a percent, which is the shape of the
    trade in general: blocking rules are cheap individually and the cost is
    paid in the pairs they generate together.
    """
    return [
        block_on("email"),
        block_on("last_name", "postcode"),
        block_on("first_name", "city"),
        block_on("substr(first_name, 1, 2)", "substr(last_name, 1, 2)"),
        block_on("postcode"),
    ]


def deterministic_rules() -> list:
    """Rules whose agreement is near-certain evidence of a match.

    Used only to estimate the prior — how often two randomly drawn records
    describe the same person — not to decide matches.
    """
    return [
        block_on("email"),
        block_on("first_name", "last_name", "postcode"),
    ]


def comparisons() -> list:
    """How each field is compared, and why it is compared that way.

    ``NameComparison`` grades names through exact, then string-similarity, then
    edit-distance levels, which is what a mistyped or shortened name needs.
    ``EmailComparison`` understands that the domain half carries far less
    identifying information than the local part. Postcodes are graded by edit
    distance, so a single wrong character still counts as near-agreement.
    City is a plain exact match: it is weak, correlated with postcode, and
    earns its place only as a tie-breaker.
    """
    return [
        cl.NameComparison("first_name"),
        cl.NameComparison("last_name"),
        cl.EmailComparison("email"),
        cl.LevenshteinAtThresholds("postcode", [1, 2]),
        cl.ExactMatch("city"),
    ]


def build_settings(config: PipelineConfig) -> SettingsCreator:
    return SettingsCreator(
        link_type="dedupe_only",
        comparisons=comparisons(),
        blocking_rules_to_generate_predictions=blocking_rules(),
        unique_id_column_name=RECORD_ID_COLUMN,
        retain_intermediate_calculation_columns=False,
    )


def _prepare(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalise input for comparison.

    Blank strings are converted to nulls, which matters more than it sounds.
    Left as empty strings, two records that merely *lack* a city would be
    scored as agreeing on it, and absence of evidence would be counted as
    evidence — nudging unrelated people together. As nulls, the field is
    correctly treated as uninformative for that pair.
    """
    prepared = frame.copy()

    # Standardise before comparing. Case is not identity: an address typed in
    # capitals belongs to the same person as one typed in lower case, and
    # leaving that to the probabilistic model wastes it on a difference that a
    # single cheap rule settles outright. Doing it here also repairs the
    # blocking rule on email, which is an equality test and would otherwise
    # miss every pair that differs only by capitalisation.
    if "email" in prepared.columns:
        prepared["email"] = prepared["email"].str.strip().str.lower()

    for column in COMPARISON_COLUMNS:
        if column in prepared.columns:
            prepared[column] = prepared[column].replace(r"^\s*$", None, regex=True)
    return prepared


@dataclass
class LinkageResult:
    """Clusters, plus the numbers needed to judge whether they are trustworthy."""

    clusters: pd.DataFrame
    input_records: int
    candidate_pairs: int
    pairs_above_threshold: int
    threshold: float

    @property
    def all_possible_pairs(self) -> int:
        n = self.input_records
        return n * (n - 1) // 2

    @property
    def blocking_reduction_ratio(self) -> float:
        """Fraction of all possible pairs that blocking removed from consideration."""
        total = self.all_possible_pairs
        if total == 0:
            return 0.0
        return 1.0 - (self.candidate_pairs / total)


def resolve_records(frame: pd.DataFrame, config: PipelineConfig) -> LinkageResult:
    """Run linkage over ``frame`` and return the resulting clusters.

    The returned frame has one row per input record, carrying its
    ``record_id`` and the ``cluster_id`` Splink assigned to it.
    """
    prepared = _prepare(frame)
    db_api = DuckDBAPI()
    linker = Linker(
        prepared,
        build_settings(config),
        db_api=db_api,
        set_up_basic_logging=False,
    )

    # Prior: how often would two records drawn at random describe the same
    # person? Estimated from near-certain rules and an assumed recall, rather
    # than left at a default that has nothing to do with this dataset.
    linker.training.estimate_probability_two_random_records_match(
        deterministic_rules(), recall=0.8
    )

    # u — agreement rates among non-matches. Random pairs are almost all
    # non-matches, so sampling them estimates u directly. Seeded, because an
    # unseeded sample would make every run's output slightly different.
    linker.training.estimate_u_using_random_sampling(
        max_pairs=config.max_pairs_for_estimation, seed=config.seed
    )

    # m — agreement rates among matches. EM is trained on more than one
    # blocking rule because a rule fixes its own column: training only on
    # email agreement teaches the model nothing about how email behaves.
    for rule in (
        block_on("email"),
        block_on("last_name", "postcode"),
        block_on("first_name", "last_name"),
    ):
        linker.training.estimate_parameters_using_expectation_maximisation(rule)

    predictions = linker.inference.predict()
    predictions_frame = predictions.as_pandas_dataframe()
    candidate_pairs = len(predictions_frame)
    above = int((predictions_frame["match_probability"] >= config.match_threshold).sum())

    clustered = linker.clustering.cluster_pairwise_predictions_at_threshold(
        predictions, threshold_match_probability=config.match_threshold
    )
    clusters = clustered.as_pandas_dataframe()[[RECORD_ID_COLUMN, "cluster_id"]].copy()
    clusters[RECORD_ID_COLUMN] = clusters[RECORD_ID_COLUMN].astype(str)
    clusters["cluster_id"] = clusters["cluster_id"].astype(str)

    return LinkageResult(
        clusters=clusters.sort_values(RECORD_ID_COLUMN, kind="stable").reset_index(drop=True),
        input_records=len(frame),
        candidate_pairs=candidate_pairs,
        pairs_above_threshold=above,
        threshold=config.match_threshold,
    )

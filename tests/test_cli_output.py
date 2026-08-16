# SPDX-License-Identifier: Apache-2.0
"""The demo's warning presentation.

Hiding warnings is a dangerous thing to do, so the filter that does it is
tested for what it must *not* hide as much as for what it should. A filter that
quietly swallowed a real problem would be far worse than the wall of expected
warnings it exists to remove.
"""

from __future__ import annotations

import logging

import pytest

from descramble.cli import ExpectedTrainingNoise, _quieten_expected_demo_warnings


def record(logger_name: str, message: str) -> logging.LogRecord:
    return logging.LogRecord(logger_name, logging.WARNING, __file__, 1, message, None, None)


@pytest.mark.parametrize(
    "message",
    [
        "Level Exact match on username on comparison email not observed in dataset, "
        "unable to train m value",
        "Comparison: 'postcode':\n    m values not fully trained",
        "You have called predict(), but there are some parameter estimates which have "
        "neither been estimated or specified in your settings dictionary.",
    ],
)
def test_expected_training_warnings_are_hidden(message):
    """The known-expected, small-dataset warnings are the ones removed."""
    noise = ExpectedTrainingNoise()
    assert noise.filter(record("splink.internals.expectation_maximisation", message)) is False
    assert noise.suppressed == 1


@pytest.mark.parametrize(
    "message",
    [
        "Your blocking rules generated 0 comparisons",
        "DEPRECATION: this API will be removed in the next release",
        "Out of memory while executing query",
        "Failed to connect to the catalogue",
    ],
)
def test_real_warnings_are_never_hidden(message):
    """Anything that is not on the expected list still reaches the user.

    This is the property that makes the filter defensible. If it ever starts
    swallowing messages like these, the demo would be reporting success over a
    genuine failure.
    """
    noise = ExpectedTrainingNoise()
    assert noise.filter(record("splink.internals.linker", message)) is True
    assert noise.suppressed == 0


def test_only_splink_loggers_are_filtered():
    """Scope is limited to Splink, so this project's own logging is never touched."""
    noise = ExpectedTrainingNoise()
    same_text = "not observed in dataset"
    assert noise.filter(record("descramble.pipeline", same_text)) is True
    assert noise.filter(record("splink.internals.expectation_maximisation", same_text)) is False


def test_filter_is_removed_again_afterwards():
    """The filter is scoped to the demo and must not leak into the process.

    A filter left installed on the root handlers would silently apply to every
    later run in the same session, including a real one.
    """
    handlers = logging.getLogger().handlers
    if not handlers:
        logging.basicConfig()
        handlers = logging.getLogger().handlers

    before = [list(handler.filters) for handler in handlers]
    with _quieten_expected_demo_warnings(active=True) as noise:
        assert noise is not None
        assert any(
            isinstance(f, ExpectedTrainingNoise) for handler in handlers for f in handler.filters
        )
    after = [list(handler.filters) for handler in handlers]
    assert after == before


def test_inactive_context_installs_nothing():
    """With --verbose the filter is not installed at all, so nothing is hidden."""
    handlers = logging.getLogger().handlers
    with _quieten_expected_demo_warnings(active=False) as noise:
        assert noise is None
        assert not any(
            isinstance(f, ExpectedTrainingNoise) for handler in handlers for f in handler.filters
        )

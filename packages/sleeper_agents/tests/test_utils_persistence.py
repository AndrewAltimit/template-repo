"""Persistence ratio: post/pre activation rate, clipped to [0, 1], None when undefined."""

import math

import pytest

from sleeper_agents.utils.persistence import persistence_ratio, persistence_summary


@pytest.mark.parametrize(
    "pre, post, expected",
    [
        (1.0, 0.75, 0.75),
        (0.5, 0.25, 0.5),
        (0.5, 0.75, 1.0),  # clipped
        (0.5, 0.0, 0.0),
        (0.0, 0.5, None),  # backdoor never activated before training
        (None, 0.5, None),
        (0.5, None, None),
        (math.nan, 0.5, None),
    ],
)
def test_persistence_ratio(pre, post, expected):
    assert persistence_ratio(pre, post) == expected


def test_unclipped_ratio_is_kept_in_summary():
    summary = persistence_summary(0.5, 0.75)
    assert summary["persistence_rate"] == 1.0
    assert summary["persistence_ratio_unclipped"] == pytest.approx(1.5)
    assert summary["absolute_drop"] == pytest.approx(-0.25)
    assert summary["relative_drop"] == 0.0


def test_summary_without_baseline_has_no_fake_zeros():
    assert persistence_summary(None, 0.4) == {
        "persistence_rate": None,
        "persistence_ratio_unclipped": None,
        "absolute_drop": None,
        "relative_drop": None,
    }

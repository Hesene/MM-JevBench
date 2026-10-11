import math

import pytest

from evaluation.evaluate import score


def _row(record_id: str, group_id: str, label: int) -> dict:
    return {
        "id": record_id,
        "group_id": group_id,
        "candidates": [{"key": "A"}, {"key": "B"}],
        "gold": {"label_index": label},
    }


def test_group_macro_gives_each_group_equal_weight() -> None:
    rows = [
        _row("a", "large", 0),
        _row("b", "large", 0),
        _row("c", "small", 1),
    ]
    predictions = {
        "a": {"probabilities": [0.9, 0.1]},
        "b": {"probabilities": [0.4, 0.6]},
        "c": {"probabilities": [0.2, 0.8]},
    }

    result = score(rows, predictions)

    assert result["accuracy"] == pytest.approx(2 / 3)
    assert result["group_macro"]["n_groups"] == 2
    assert result["group_macro"]["accuracy"] == pytest.approx(0.75)

    large_nll = (-math.log(0.9) - math.log(0.4)) / 2
    small_nll = -math.log(0.8)
    assert result["group_macro"]["nll"] == pytest.approx((large_nll + small_nll) / 2)

    # Per-row Brier sums are .02, .72 and .08.  The large group's mean is
    # .37, which is then averaged equally with the small group's .08.
    assert result["group_macro"]["brier_sum"] == pytest.approx(0.225)


def test_group_macro_matches_sample_metrics_for_singleton_groups() -> None:
    rows = [_row("a", "g1", 0), _row("b", "g2", 1)]
    predictions = {
        "a": {"probabilities": [0.7, 0.3]},
        "b": {"probabilities": [0.4, 0.6]},
    }

    result = score(rows, predictions)

    assert result["group_macro"]["accuracy"] == pytest.approx(result["accuracy"])
    assert result["group_macro"]["nll"] == pytest.approx(result["nll"])
    assert result["group_macro"]["brier_sum"] == pytest.approx(result["brier_sum"])

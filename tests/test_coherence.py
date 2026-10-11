import math

import pytest

from mmjevbench.coherence import (
    batch_independence_distribution_error,
    batch_independent_distribution_error,
    candidate_permutation_alignment_error,
    choice_merge_additivity_error,
    logical_monotonicity_error,
    logical_monotonicity_violation_rate,
    logical_monotonicity_violations,
    noul_negation_error,
    submenu_conditional_consistency_error,
    submenu_odds_consistency_error,
)


def test_candidate_permutation_alignment_error_is_zero_after_alignment():
    # [A, B, C] -> [C, A, B], so new positions map to old [2, 0, 1].
    error = candidate_permutation_alignment_error(
        [0.1, 0.6, 0.3], [0.3, 0.1, 0.6], [2, 0, 1]
    )
    assert error == pytest.approx(0.0)


def test_candidate_permutation_alignment_error_has_hand_computed_tv():
    # The changed distribution aligns to [0.15, 0.60, 0.25].
    # TV = (|.10-.15| + |.60-.60| + |.30-.25|) / 2 = .05.
    error = candidate_permutation_alignment_error(
        [0.1, 0.6, 0.3], [0.25, 0.15, 0.60], [2, 0, 1]
    )
    assert error == pytest.approx(0.05)


def test_noul_negation_error_uses_no_yes_complement():
    # Exact negation would be [.8, .2]; observed [.75, .25] has TV .05.
    assert noul_negation_error([0.2, 0.8], [0.75, 0.25]) == pytest.approx(0.05)
    assert noul_negation_error([0.2, 0.8], [0.8, 0.2]) == pytest.approx(0.0)


def test_choice_merge_additivity_error_has_hand_computed_tv():
    # Groups {0,2} and {1,3} imply [.4, .6].
    # Observed [.45, .55] has TV .05.
    error = choice_merge_additivity_error(
        [0.1, 0.2, 0.3, 0.4], [[0, 2], [1, 3]], [0.45, 0.55]
    )
    assert error == pytest.approx(0.05)


def test_choice_merge_requires_a_true_partition():
    with pytest.raises(ValueError, match="partition"):
        choice_merge_additivity_error(
            [0.2, 0.3, 0.5], [[0, 1], [1, 2]], [0.4, 0.6]
        )


def test_submenu_conditional_and_odds_errors_are_hand_computed():
    # Restrict [.2, .3, .5] to indices 0,1: conditional distribution [.4,.6].
    # Against [.25,.75], TV = .15.
    conditional_error = submenu_conditional_consistency_error(
        [0.2, 0.3, 0.5], [0, 1], [0.25, 0.75]
    )
    assert conditional_error == pytest.approx(0.15)

    # Full odds are 2/3; submenu odds are 1/3, so change is |log(2)|.
    odds_error = submenu_odds_consistency_error(
        [0.2, 0.3, 0.5], [0, 1], [0.25, 0.75]
    )
    assert odds_error == pytest.approx(math.log(2.0))


def test_submenu_exact_conditioning_has_zero_errors():
    assert submenu_conditional_consistency_error(
        [0.2, 0.3, 0.5], [0, 1], [0.4, 0.6]
    ) == pytest.approx(0.0)
    assert submenu_odds_consistency_error(
        [0.2, 0.3, 0.5], [0, 1], [0.4, 0.6]
    ) == pytest.approx(0.0)


def test_submenu_odds_rejects_zero_probability_instead_of_smoothing():
    with pytest.raises(ValueError, match="strictly positive"):
        submenu_odds_consistency_error([0.0, 0.5, 0.5], [0, 1], [0.1, 0.9])


def test_logical_monotonicity_metrics_are_hand_computed():
    probabilities = {"A": 0.7, "B": 0.6, "C": 0.9}
    implications = [("A", "B"), ("B", "C"), ("A", "C")]

    # Only A -> B is violated, by .1. Mean gap over three edges is .1/3.
    assert logical_monotonicity_error(
        probabilities, implications
    ) == pytest.approx(0.1 / 3.0)
    assert logical_monotonicity_violation_rate(
        probabilities, implications
    ) == pytest.approx(1.0 / 3.0)

    violations = logical_monotonicity_violations(probabilities, implications)
    assert len(violations) == 1
    assert violations[0].antecedent == "A"
    assert violations[0].consequent == "B"
    assert violations[0].gap == pytest.approx(0.1)


def test_logical_violation_tolerance_affects_rate_not_reported_gap():
    probabilities = {"A": 0.7000001, "B": 0.7}
    implications = [("A", "B")]
    assert logical_monotonicity_violation_rate(
        probabilities, implications, tolerance=1e-6
    ) == pytest.approx(0.0)
    assert logical_monotonicity_error(probabilities, implications) == pytest.approx(
        1e-7
    )


def test_batch_independence_error_supports_id_mapping_and_alias():
    independent = {"a": [0.7, 0.3], "b": [0.2, 0.3, 0.5]}
    batched = {"b": [0.1, 0.4, 0.5], "a": [0.6, 0.4]}
    # Each sample has TV .1, hence both mean and max are .1.
    assert batch_independent_distribution_error(
        independent, batched
    ) == pytest.approx(0.1)
    assert batch_independent_distribution_error(
        independent, batched, reduction="max"
    ) == pytest.approx(0.1)
    assert batch_independence_distribution_error(
        independent, batched
    ) == pytest.approx(0.1)


def test_invalid_distribution_is_not_silently_normalized():
    with pytest.raises(ValueError, match="sum to 1"):
        noul_negation_error([0.2, 0.7], [0.8, 0.2])


def test_permutation_mapping_must_be_bijective():
    with pytest.raises(ValueError, match="permutation"):
        candidate_permutation_alignment_error(
            [0.2, 0.3, 0.5], [0.2, 0.3, 0.5], [0, 0, 2]
        )

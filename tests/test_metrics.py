import math
import unittest

from mmjevbench.metrics import (
    accuracy,
    adaptive_calibration_error,
    area_under_risk_coverage_curve,
    calibration_bins,
    chance_corrected_accuracy,
    expected_calibration_error,
    group_bootstrap,
    jensen_shannon_divergence,
    multiclass_brier_score,
    negative_log_likelihood,
    paired_bootstrap,
    risk_coverage_curve,
    total_variation_distance,
    validate_probabilities,
    wilson_interval,
)


class CoreMetricTests(unittest.TestCase):
    def test_perfect_predictions(self):
        labels = [0, 1, 2]
        probabilities = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        self.assertEqual(accuracy(labels, probabilities), 1.0)
        self.assertEqual(chance_corrected_accuracy(labels, probabilities), 1.0)
        self.assertEqual(negative_log_likelihood(labels, probabilities), 0.0)
        self.assertEqual(multiclass_brier_score(labels, probabilities), 0.0)
        self.assertEqual(expected_calibration_error(labels, probabilities), 0.0)
        self.assertEqual(adaptive_calibration_error(labels, probabilities, n_bins=3), 0.0)
        self.assertEqual(area_under_risk_coverage_curve(labels, probabilities), 0.0)

    def test_all_wrong_predictions(self):
        labels = [0, 1]
        probabilities = [[0, 1], [1, 0]]
        self.assertEqual(accuracy(labels, probabilities), 0.0)
        self.assertEqual(chance_corrected_accuracy(labels, probabilities), -1.0)
        self.assertAlmostEqual(
            negative_log_likelihood(labels, probabilities, epsilon=1e-6), -math.log(1e-6)
        )
        self.assertEqual(multiclass_brier_score(labels, probabilities), 2.0)
        self.assertEqual(
            multiclass_brier_score(labels, probabilities, class_reduction="mean"), 1.0
        )
        self.assertEqual(expected_calibration_error(labels, probabilities), 1.0)
        self.assertEqual(area_under_risk_coverage_curve(labels, probabilities), 1.0)

    def test_uniform_predictions_have_expected_closed_forms(self):
        labels = [0, 1, 2]
        probabilities = [[1 / 3, 1 / 3, 1 / 3]] * 3
        self.assertAlmostEqual(accuracy(labels, probabilities), 1 / 3)
        self.assertAlmostEqual(chance_corrected_accuracy(labels, probabilities), 0.0)
        self.assertAlmostEqual(negative_log_likelihood(labels, probabilities), math.log(3))
        self.assertAlmostEqual(multiclass_brier_score(labels, probabilities), 2 / 3)
        self.assertAlmostEqual(expected_calibration_error(labels, probabilities), 0.0)
        # With one classwise bin, uniform confidence equals each class prevalence.
        # Finer equal-mass ACE bins intentionally expose within-bin label variation.
        self.assertAlmostEqual(adaptive_calibration_error(labels, probabilities, n_bins=1), 0.0)

    def test_hard_labels_and_soft_targets_for_brier(self):
        probabilities = [[0.7, 0.3], [0.2, 0.8]]
        self.assertAlmostEqual(multiclass_brier_score([0, 1], probabilities), 0.13)
        soft_targets = [[0.6, 0.4], [0.1, 0.9]]
        self.assertAlmostEqual(multiclass_brier_score(soft_targets, probabilities), 0.02)
        self.assertAlmostEqual(
            multiclass_brier_score(
                [0, 1], probabilities, class_reduction="sum", sample_reduction="sum"
            ),
            0.26,
        )

    def test_accuracy_accepts_class_indices(self):
        self.assertEqual(accuracy([0, 1, 2], [0, 0, 2]), 2 / 3)
        self.assertAlmostEqual(
            chance_corrected_accuracy([0, 1, 2], [0, 0, 2], num_classes=3), 0.5
        )

    def test_marginal_chance_correction(self):
        labels = [0, 0, 1, 1]
        predictions = [0, 0, 0, 0]
        # Observed and marginal-chance agreement are both 0.5.
        self.assertEqual(
            chance_corrected_accuracy(labels, predictions, num_classes=2, strategy="marginal"),
            0.0,
        )


class CalibrationAndSelectiveRiskTests(unittest.TestCase):
    def setUp(self):
        self.labels = [0, 1, 1, 0]
        self.probabilities = [[0.9, 0.1], [0.2, 0.8], [0.6, 0.4], [0.3, 0.7]]

    def test_equal_width_and_equal_mass_ece(self):
        self.assertAlmostEqual(
            expected_calibration_error(
                self.labels, self.probabilities, n_bins=2, binning="equal_width"
            ),
            0.25,
        )
        self.assertAlmostEqual(
            expected_calibration_error(
                self.labels, self.probabilities, n_bins=2, binning="equal_mass"
            ),
            0.4,
        )
        bins = calibration_bins(
            self.labels, self.probabilities, n_bins=2, binning="equal_mass"
        )
        self.assertEqual([bin_.count for bin_ in bins], [2, 2])

    def test_risk_coverage_curve_and_empirical_aurc(self):
        curve = risk_coverage_curve(self.labels, self.probabilities)
        self.assertEqual([point.n_selected for point in curve], [1, 2, 3, 4])
        self.assertEqual([point.coverage for point in curve], [0.25, 0.5, 0.75, 1.0])
        self.assertEqual([point.risk for point in curve], [0.0, 0.0, 1 / 3, 0.5])
        self.assertAlmostEqual(
            area_under_risk_coverage_curve(self.labels, self.probabilities), 5 / 24
        )


class DistributionAndIntervalTests(unittest.TestCase):
    def test_tv_and_js_divergence(self):
        self.assertEqual(total_variation_distance([1, 0], [0, 1]), 1.0)
        self.assertEqual(jensen_shannon_divergence([1, 0], [0, 1]), 1.0)
        self.assertEqual(total_variation_distance([0.25, 0.75], [0.25, 0.75]), 0.0)
        self.assertEqual(jensen_shannon_divergence([0.25, 0.75], [0.25, 0.75]), 0.0)

    def test_wilson_interval_known_value(self):
        interval = wilson_interval(50, 100)
        self.assertAlmostEqual(interval.lower, 0.4038, places=4)
        self.assertAlmostEqual(interval.upper, 0.5962, places=4)
        extreme = wilson_interval(0, 10)
        self.assertGreaterEqual(extreme.lower, 0.0)
        self.assertLessEqual(extreme.upper, 1.0)


class BootstrapTests(unittest.TestCase):
    def test_paired_bootstrap_is_reproducible(self):
        kwargs = {"n_resamples": 250, "confidence": 0.9, "seed": 73}
        first = paired_bootstrap([1, 1, 0, 1], [0, 1, 0, 0], **kwargs)
        second = paired_bootstrap([1, 1, 0, 1], [0, 1, 0, 0], **kwargs)
        self.assertEqual(first, second)
        self.assertEqual(first.estimate, 0.5)
        self.assertEqual(first.method, "paired")
        self.assertLessEqual(first.lower, first.estimate)
        self.assertGreaterEqual(first.upper, first.estimate)

    def test_group_bootstrap_and_paired_group_bootstrap(self):
        values = [1.0, 0.0, 0.5, 0.5]
        groups = ["source-a", "source-a", "source-b", "source-b"]
        first = group_bootstrap(values, groups, n_resamples=100, seed=4)
        second = group_bootstrap(values, groups, n_resamples=100, seed=4)
        self.assertEqual(first, second)
        self.assertEqual(first.estimate, 0.5)
        self.assertEqual(first.method, "group")
        paired = paired_bootstrap(
            values, [0.0, 0.0, 0.0, 0.0], groups=groups, n_resamples=50, seed=4
        )
        self.assertEqual(paired.method, "paired-group")


class InvalidProbabilityTests(unittest.TestCase):
    def test_validation_rejects_malformed_probabilities(self):
        invalid_matrices = [
            [[0.2, 0.2]],  # not normalised
            [[-0.1, 1.1]],  # out of range
            [[float("nan"), float("nan")]],
            [[0.5, 0.5], [1.0]],  # ragged
            [[]],
        ]
        for matrix in invalid_matrices:
            with self.subTest(matrix=matrix):
                with self.assertRaises((TypeError, ValueError)):
                    validate_probabilities(matrix)

    def test_metrics_do_not_silently_normalise(self):
        for metric in (
            accuracy,
            negative_log_likelihood,
            multiclass_brier_score,
            expected_calibration_error,
            adaptive_calibration_error,
            area_under_risk_coverage_curve,
        ):
            with self.subTest(metric=metric.__name__):
                with self.assertRaises(ValueError):
                    metric([0], [[0.6, 0.6]])

    def test_invalid_labels_and_options(self):
        with self.assertRaises(ValueError):
            accuracy([2], [[0.5, 0.5]])
        with self.assertRaises(ValueError):
            expected_calibration_error([0], [[0.5, 0.5]], n_bins=0)
        with self.assertRaises(ValueError):
            negative_log_likelihood([0], [[0.5, 0.5]], reduction="median")
        with self.assertRaises(ValueError):
            wilson_interval(11, 10)


if __name__ == "__main__":
    unittest.main()

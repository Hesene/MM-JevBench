"""Dependency-free evaluation metrics for MM-JevBench.

The functions in this module intentionally make their statistical conventions
explicit.  In particular:

* multiclass Brier score defaults to a *sum* over classes and a mean over
  samples (the common multiclass Brier definition);
* ECE is top-label calibration and can use equal-width or equal-mass bins;
* ACE is classwise calibration with equal-mass bins;
* empirical AURC is the arithmetic mean of selective risks at coverages
  ``1 / n, ..., n / n``.

Every metric that consumes probabilities validates them without clipping or
renormalising.  This is deliberate: malformed model output must fail loudly
rather than silently improving a reported benchmark result.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from numbers import Integral, Real
from statistics import NormalDist, fmean, stdev
from typing import Callable, Hashable, Iterable, List, NamedTuple, Optional, Sequence, Tuple, TypeVar


Number = Real
T = TypeVar("T")


@dataclass(frozen=True)
class CalibrationBin:
    """One non-empty calibration bin."""

    lower: float
    upper: float
    count: int
    mean_confidence: float
    accuracy: float
    gap: float


@dataclass(frozen=True)
class RiskCoveragePoint:
    """Selective risk after retaining the most confident ``n_selected`` rows."""

    coverage: float
    risk: float
    threshold: float
    n_selected: int


class WilsonInterval(NamedTuple):
    """Lower and upper bounds of a Wilson score interval."""

    lower: float
    upper: float


@dataclass(frozen=True)
class BootstrapResult:
    """Percentile bootstrap confidence interval and resampling metadata."""

    estimate: float
    lower: float
    upper: float
    standard_error: float
    confidence: float
    n_resamples: int
    seed: int
    method: str


def _materialize(values: Iterable[T], name: str) -> List[T]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{name} must be an iterable of observations, not text")
    try:
        result = list(values)
    except TypeError as exc:
        raise TypeError(f"{name} must be iterable") from exc
    if not result:
        raise ValueError(f"{name} must not be empty")
    return result


def _is_finite_real(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(float(value))


def validate_probabilities(
    probabilities: Iterable[Iterable[Number]], *, atol: float = 1e-8
) -> Tuple[Tuple[float, ...], ...]:
    """Validate and freeze a matrix of categorical probability distributions.

    Rows must be non-empty, have identical lengths, contain finite numeric
    values in ``[0, 1]``, and sum to one within the absolute tolerance.  Values
    are never clipped or renormalised.
    """

    if not _is_finite_real(atol) or float(atol) < 0:
        raise ValueError("atol must be a finite non-negative number")
    raw_rows = _materialize(probabilities, "probabilities")
    rows: List[Tuple[float, ...]] = []
    width: Optional[int] = None
    for row_index, raw_row in enumerate(raw_rows):
        if isinstance(raw_row, (str, bytes)):
            raise TypeError(f"probabilities[{row_index}] must be a numeric sequence")
        try:
            row_values = list(raw_row)
        except TypeError as exc:
            raise TypeError(f"probabilities[{row_index}] must be a numeric sequence") from exc
        if not row_values:
            raise ValueError(f"probabilities[{row_index}] must not be empty")
        if width is None:
            width = len(row_values)
        elif len(row_values) != width:
            raise ValueError("all probability rows must have the same number of classes")

        row: List[float] = []
        for class_index, value in enumerate(row_values):
            if not _is_finite_real(value):
                raise ValueError(
                    f"probabilities[{row_index}][{class_index}] must be a finite real number"
                )
            probability = float(value)
            if probability < 0.0 or probability > 1.0:
                raise ValueError(
                    f"probabilities[{row_index}][{class_index}]={probability} is outside [0, 1]"
                )
            row.append(probability)
        row_sum = math.fsum(row)
        if not math.isclose(row_sum, 1.0, rel_tol=0.0, abs_tol=float(atol)):
            raise ValueError(
                f"probabilities[{row_index}] sums to {row_sum!r}; expected 1 within atol={atol}"
            )
        rows.append(tuple(row))
    return tuple(rows)


def _validate_labels(labels: Iterable[int], n_samples: int, n_classes: int) -> Tuple[int, ...]:
    raw_labels = _materialize(labels, "labels")
    if len(raw_labels) != n_samples:
        raise ValueError(f"labels has {len(raw_labels)} rows but predictions has {n_samples}")
    result: List[int] = []
    for index, label in enumerate(raw_labels):
        if not isinstance(label, Integral) or isinstance(label, bool):
            raise TypeError(f"labels[{index}] must be an integer class index")
        integer_label = int(label)
        if integer_label < 0 or integer_label >= n_classes:
            raise ValueError(
                f"labels[{index}]={integer_label} is outside [0, {n_classes - 1}]"
            )
        result.append(integer_label)
    return tuple(result)


def _argmax(row: Sequence[float]) -> int:
    # max(range(...), key=...) deterministically resolves ties to the first class.
    return max(range(len(row)), key=row.__getitem__)


def _labels_and_predictions(
    labels: Iterable[int], predictions: Iterable[object]
) -> Tuple[Tuple[int, ...], Tuple[int, ...], int]:
    raw_predictions = _materialize(predictions, "predictions")
    if all(isinstance(value, Integral) and not isinstance(value, bool) for value in raw_predictions):
        raw_labels = _materialize(labels, "labels")
        if len(raw_labels) != len(raw_predictions):
            raise ValueError(
                f"labels has {len(raw_labels)} rows but predictions has {len(raw_predictions)}"
            )
        all_indices = list(raw_labels) + raw_predictions
        for index, value in enumerate(all_indices):
            if not isinstance(value, Integral) or isinstance(value, bool):
                raise TypeError(f"class index at position {index} must be an integer")
            if int(value) < 0:
                raise ValueError("class indices must be non-negative")
        n_classes = max(int(value) for value in all_indices) + 1
        return (
            tuple(int(value) for value in raw_labels),
            tuple(int(value) for value in raw_predictions),
            n_classes,
        )

    matrix = validate_probabilities(raw_predictions)  # type: ignore[arg-type]
    checked_labels = _validate_labels(labels, len(matrix), len(matrix[0]))
    return checked_labels, tuple(_argmax(row) for row in matrix), len(matrix[0])


def accuracy(labels: Iterable[int], predictions: Iterable[object]) -> float:
    """Return exact top-1 accuracy for class indices or probability rows."""

    checked_labels, predicted_labels, _ = _labels_and_predictions(labels, predictions)
    return fmean(int(gold == predicted) for gold, predicted in zip(checked_labels, predicted_labels))


def chance_corrected_accuracy(
    labels: Iterable[int],
    predictions: Iterable[object],
    *,
    num_classes: Optional[int] = None,
    chance: Optional[float] = None,
    strategy: str = "uniform",
) -> float:
    """Return ``(accuracy - expected) / (1 - expected)``.

    ``strategy='uniform'`` uses ``1 / num_classes``.  ``num_classes`` is
    inferred when omitted, but should be supplied when evaluating a subset
    that may not contain every candidate class.  ``strategy='marginal'`` uses
    the product of observed gold and prediction marginals (Cohen's kappa
    chance term).  An explicit ``chance`` overrides the strategy.
    """

    checked_labels, predicted_labels, inferred_classes = _labels_and_predictions(labels, predictions)
    if num_classes is None:
        num_classes = inferred_classes
    if not isinstance(num_classes, Integral) or isinstance(num_classes, bool) or num_classes < 1:
        raise ValueError("num_classes must be a positive integer")
    num_classes = int(num_classes)
    if any(value >= num_classes for value in checked_labels + predicted_labels):
        raise ValueError("num_classes is smaller than an observed class index")

    observed = fmean(int(a == b) for a, b in zip(checked_labels, predicted_labels))
    if chance is not None:
        if not _is_finite_real(chance) or float(chance) < 0.0 or float(chance) >= 1.0:
            raise ValueError("chance must be finite and in [0, 1)")
        expected = float(chance)
    elif strategy == "uniform":
        expected = 1.0 / num_classes
    elif strategy == "marginal":
        n = len(checked_labels)
        gold_counts = [0] * num_classes
        predicted_counts = [0] * num_classes
        for gold, predicted in zip(checked_labels, predicted_labels):
            gold_counts[gold] += 1
            predicted_counts[predicted] += 1
        expected = math.fsum(g * p for g, p in zip(gold_counts, predicted_counts)) / (n * n)
    else:
        raise ValueError("strategy must be 'uniform' or 'marginal'")
    if expected >= 1.0:
        raise ValueError("chance correction is undefined when expected accuracy is 1")
    return (observed - expected) / (1.0 - expected)


def negative_log_likelihood(
    labels: Iterable[int],
    probabilities: Iterable[Iterable[Number]],
    *,
    epsilon: float = 1e-15,
    reduction: str = "mean",
) -> float:
    """Return categorical NLL, flooring only the logarithm argument at epsilon.

    Probability rows themselves are still strictly validated and never
    modified.  ``reduction`` is ``'mean'`` (default) or ``'sum'``.
    """

    if not _is_finite_real(epsilon) or float(epsilon) <= 0.0 or float(epsilon) > 1.0:
        raise ValueError("epsilon must be finite and in (0, 1]")
    matrix = validate_probabilities(probabilities)
    checked_labels = _validate_labels(labels, len(matrix), len(matrix[0]))
    losses = [-math.log(max(row[label], float(epsilon))) for label, row in zip(checked_labels, matrix)]
    if reduction == "mean":
        return fmean(losses)
    if reduction == "sum":
        return math.fsum(losses)
    raise ValueError("reduction must be 'mean' or 'sum'")


nll = negative_log_likelihood


def _target_matrix(
    targets: Iterable[object], n_samples: int, n_classes: int
) -> Tuple[Tuple[float, ...], ...]:
    raw_targets = _materialize(targets, "targets")
    if len(raw_targets) != n_samples:
        raise ValueError(f"targets has {len(raw_targets)} rows but probabilities has {n_samples}")
    if all(isinstance(value, Integral) and not isinstance(value, bool) for value in raw_targets):
        labels = _validate_labels(raw_targets, n_samples, n_classes)  # type: ignore[arg-type]
        return tuple(
            tuple(1.0 if class_index == label else 0.0 for class_index in range(n_classes))
            for label in labels
        )
    matrix = validate_probabilities(raw_targets)  # type: ignore[arg-type]
    if len(matrix[0]) != n_classes:
        raise ValueError("soft targets and probabilities must have the same number of classes")
    return matrix


def multiclass_brier_score(
    targets: Iterable[object],
    probabilities: Iterable[Iterable[Number]],
    *,
    class_reduction: str = "sum",
    sample_reduction: str = "mean",
) -> float:
    """Return the multiclass Brier score for hard labels or soft targets.

    Per-sample squared errors are reduced over classes with
    ``class_reduction='sum'`` (default, range ``[0, 2]`` for hard targets) or
    ``'mean'`` (the sum divided by the number of classes).  The resulting
    sample scores are then reduced using ``sample_reduction='mean'`` or
    ``'sum'``.
    """

    matrix = validate_probabilities(probabilities)
    target_matrix = _target_matrix(targets, len(matrix), len(matrix[0]))
    sample_scores: List[float] = []
    for target, predicted in zip(target_matrix, matrix):
        squared_sum = math.fsum((p - y) ** 2 for y, p in zip(target, predicted))
        if class_reduction == "sum":
            sample_scores.append(squared_sum)
        elif class_reduction == "mean":
            sample_scores.append(squared_sum / len(predicted))
        else:
            raise ValueError("class_reduction must be 'sum' or 'mean'")
    if sample_reduction == "mean":
        return fmean(sample_scores)
    if sample_reduction == "sum":
        return math.fsum(sample_scores)
    raise ValueError("sample_reduction must be 'mean' or 'sum'")


brier_score = multiclass_brier_score


def _validate_bin_count(n_bins: int) -> int:
    if not isinstance(n_bins, Integral) or isinstance(n_bins, bool) or n_bins < 1:
        raise ValueError("n_bins must be a positive integer")
    return int(n_bins)


def _top_label_observations(
    labels: Iterable[int], probabilities: Iterable[Iterable[Number]]
) -> Tuple[List[float], List[int]]:
    matrix = validate_probabilities(probabilities)
    checked_labels = _validate_labels(labels, len(matrix), len(matrix[0]))
    confidences: List[float] = []
    correctness: List[int] = []
    for label, row in zip(checked_labels, matrix):
        predicted = _argmax(row)
        confidences.append(row[predicted])
        correctness.append(int(predicted == label))
    return confidences, correctness


def calibration_bins(
    labels: Iterable[int],
    probabilities: Iterable[Iterable[Number]],
    *,
    n_bins: int = 15,
    binning: str = "equal_width",
) -> Tuple[CalibrationBin, ...]:
    """Return non-empty top-label calibration bins.

    Equal-width bins partition ``[0, 1]``.  Equal-mass bins contain sample
    counts differing by at most one after a stable confidence sort.
    """

    n_bins = _validate_bin_count(n_bins)
    confidences, correctness = _top_label_observations(labels, probabilities)
    members: List[Tuple[float, float, List[int]]] = []
    if binning == "equal_width":
        buckets: List[List[int]] = [[] for _ in range(n_bins)]
        for index, confidence in enumerate(confidences):
            bucket_index = min(int(confidence * n_bins), n_bins - 1)
            buckets[bucket_index].append(index)
        for bucket_index, indices in enumerate(buckets):
            if indices:
                members.append((bucket_index / n_bins, (bucket_index + 1) / n_bins, indices))
    elif binning == "equal_mass":
        ordered = sorted(range(len(confidences)), key=lambda i: (confidences[i], i))
        actual_bins = min(n_bins, len(ordered))
        quotient, remainder = divmod(len(ordered), actual_bins)
        cursor = 0
        for bucket_index in range(actual_bins):
            size = quotient + int(bucket_index < remainder)
            indices = ordered[cursor : cursor + size]
            cursor += size
            members.append((confidences[indices[0]], confidences[indices[-1]], indices))
    else:
        raise ValueError("binning must be 'equal_width' or 'equal_mass'")

    result: List[CalibrationBin] = []
    for lower, upper, indices in members:
        mean_confidence = fmean(confidences[index] for index in indices)
        bin_accuracy = fmean(correctness[index] for index in indices)
        result.append(
            CalibrationBin(
                lower=lower,
                upper=upper,
                count=len(indices),
                mean_confidence=mean_confidence,
                accuracy=bin_accuracy,
                gap=abs(bin_accuracy - mean_confidence),
            )
        )
    return tuple(result)


def expected_calibration_error(
    labels: Iterable[int],
    probabilities: Iterable[Iterable[Number]],
    *,
    n_bins: int = 15,
    binning: str = "equal_width",
) -> float:
    """Return sample-weighted top-label ECE."""

    bins = calibration_bins(labels, probabilities, n_bins=n_bins, binning=binning)
    total = sum(bin_.count for bin_ in bins)
    return math.fsum(bin_.count * bin_.gap for bin_ in bins) / total


ece = expected_calibration_error


def adaptive_calibration_error(
    labels: Iterable[int],
    probabilities: Iterable[Iterable[Number]],
    *,
    n_bins: int = 15,
) -> float:
    """Return classwise equal-mass Adaptive Calibration Error (ACE).

    For every class, samples are sorted by that class probability and divided
    into equal-mass bins.  Absolute gaps between mean class probability and
    empirical one-vs-rest frequency are averaged equally over all non-empty
    class bins.
    """

    n_bins = _validate_bin_count(n_bins)
    matrix = validate_probabilities(probabilities)
    checked_labels = _validate_labels(labels, len(matrix), len(matrix[0]))
    gaps: List[float] = []
    actual_bins = min(n_bins, len(matrix))
    quotient, remainder = divmod(len(matrix), actual_bins)
    for class_index in range(len(matrix[0])):
        ordered = sorted(range(len(matrix)), key=lambda i: (matrix[i][class_index], i))
        cursor = 0
        for bucket_index in range(actual_bins):
            size = quotient + int(bucket_index < remainder)
            indices = ordered[cursor : cursor + size]
            cursor += size
            mean_probability = fmean(matrix[index][class_index] for index in indices)
            frequency = fmean(int(checked_labels[index] == class_index) for index in indices)
            gaps.append(abs(mean_probability - frequency))
    return fmean(gaps)


ace = adaptive_calibration_error


def risk_coverage_curve(
    labels: Iterable[int], probabilities: Iterable[Iterable[Number]]
) -> Tuple[RiskCoveragePoint, ...]:
    """Return empirical selective risk at every attainable sample coverage.

    Samples are ordered by decreasing maximum class probability.  Confidence
    ties preserve input order, making results deterministic.  Risk is top-1
    error among retained samples.
    """

    matrix = validate_probabilities(probabilities)
    checked_labels = _validate_labels(labels, len(matrix), len(matrix[0]))
    observations = [
        (max(row), int(_argmax(row) != label), index)
        for index, (label, row) in enumerate(zip(checked_labels, matrix))
    ]
    observations.sort(key=lambda item: (-item[0], item[2]))
    cumulative_errors = 0
    result: List[RiskCoveragePoint] = []
    for rank, (confidence, error, _) in enumerate(observations, start=1):
        cumulative_errors += error
        result.append(
            RiskCoveragePoint(
                coverage=rank / len(observations),
                risk=cumulative_errors / rank,
                threshold=confidence,
                n_selected=rank,
            )
        )
    return tuple(result)


def area_under_risk_coverage_curve(
    labels: Iterable[int], probabilities: Iterable[Iterable[Number]]
) -> float:
    """Return empirical AURC as the mean risk over coverages ``k / n``."""

    return fmean(point.risk for point in risk_coverage_curve(labels, probabilities))


aurc = area_under_risk_coverage_curve


def _validate_distribution(distribution: Iterable[Number], name: str) -> Tuple[float, ...]:
    try:
        matrix = validate_probabilities([distribution])
    except (TypeError, ValueError) as exc:
        raise type(exc)(f"invalid {name}: {exc}") from exc
    return matrix[0]


def total_variation_distance(p: Iterable[Number], q: Iterable[Number]) -> float:
    """Return ``0.5 * sum(abs(p_i - q_i))`` for two distributions."""

    left = _validate_distribution(p, "p")
    right = _validate_distribution(q, "q")
    if len(left) != len(right):
        raise ValueError("p and q must have the same number of classes")
    return 0.5 * math.fsum(abs(a - b) for a, b in zip(left, right))


tv_distance = total_variation_distance


def jensen_shannon_divergence(
    p: Iterable[Number], q: Iterable[Number], *, base: float = 2.0
) -> float:
    """Return Jensen-Shannon divergence; base 2 gives a result in ``[0, 1]``."""

    if not _is_finite_real(base) or float(base) <= 0.0 or math.isclose(float(base), 1.0):
        raise ValueError("base must be finite, positive, and different from 1")
    left = _validate_distribution(p, "p")
    right = _validate_distribution(q, "q")
    if len(left) != len(right):
        raise ValueError("p and q must have the same number of classes")
    midpoint = tuple((a + b) / 2.0 for a, b in zip(left, right))
    log_base = math.log(float(base))

    def kl(distribution: Sequence[float]) -> float:
        return math.fsum(
            value * (math.log(value / middle) / log_base)
            for value, middle in zip(distribution, midpoint)
            if value > 0.0
        )

    return 0.5 * (kl(left) + kl(right))


js_divergence = jensen_shannon_divergence


def wilson_interval(successes: int, total: int, *, confidence: float = 0.95) -> WilsonInterval:
    """Return a two-sided Wilson score interval for a binomial proportion."""

    if not isinstance(successes, Integral) or isinstance(successes, bool):
        raise TypeError("successes must be an integer")
    if not isinstance(total, Integral) or isinstance(total, bool):
        raise TypeError("total must be an integer")
    if total <= 0:
        raise ValueError("total must be positive")
    if successes < 0 or successes > total:
        raise ValueError("successes must be between 0 and total")
    if not _is_finite_real(confidence) or float(confidence) <= 0.0 or float(confidence) >= 1.0:
        raise ValueError("confidence must be in (0, 1)")

    n = int(total)
    p_hat = int(successes) / n
    z = NormalDist().inv_cdf(0.5 + float(confidence) / 2.0)
    denominator = 1.0 + z * z / n
    centre = (p_hat + z * z / (2.0 * n)) / denominator
    half_width = (
        z * math.sqrt(p_hat * (1.0 - p_hat) / n + z * z / (4.0 * n * n)) / denominator
    )
    return WilsonInterval(max(0.0, centre - half_width), min(1.0, centre + half_width))


def _validate_bootstrap_options(n_resamples: int, confidence: float, seed: int) -> None:
    if not isinstance(n_resamples, Integral) or isinstance(n_resamples, bool) or n_resamples < 1:
        raise ValueError("n_resamples must be a positive integer")
    if not _is_finite_real(confidence) or float(confidence) <= 0.0 or float(confidence) >= 1.0:
        raise ValueError("confidence must be in (0, 1)")
    if not isinstance(seed, Integral) or isinstance(seed, bool):
        raise TypeError("seed must be an integer")


def _checked_statistic(statistic: Callable[[Sequence[T]], float], sample: Sequence[T]) -> float:
    value = statistic(sample)
    if not _is_finite_real(value):
        raise ValueError("statistic must return a finite real number")
    return float(value)


def _percentile(sorted_values: Sequence[float], probability: float) -> float:
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def _bootstrap_result(
    estimate: float,
    replicates: List[float],
    *,
    confidence: float,
    n_resamples: int,
    seed: int,
    method: str,
) -> BootstrapResult:
    replicates.sort()
    alpha = 1.0 - float(confidence)
    standard_error = stdev(replicates) if len(replicates) > 1 else 0.0
    return BootstrapResult(
        estimate=estimate,
        lower=_percentile(replicates, alpha / 2.0),
        upper=_percentile(replicates, 1.0 - alpha / 2.0),
        standard_error=standard_error,
        confidence=float(confidence),
        n_resamples=int(n_resamples),
        seed=int(seed),
        method=method,
    )


def _group_indices(groups: Iterable[Hashable], n_samples: int) -> List[List[int]]:
    raw_groups = _materialize(groups, "groups")
    if len(raw_groups) != n_samples:
        raise ValueError(f"groups has {len(raw_groups)} rows but values has {n_samples}")
    lookup = {}
    ordered_groups: List[List[int]] = []
    for index, group in enumerate(raw_groups):
        try:
            hash(group)
        except TypeError as exc:
            raise TypeError(f"groups[{index}] must be hashable") from exc
        if group not in lookup:
            lookup[group] = len(ordered_groups)
            ordered_groups.append([])
        ordered_groups[lookup[group]].append(index)
    return ordered_groups


def paired_bootstrap(
    values_a: Iterable[T],
    values_b: Iterable[T],
    *,
    statistic: Optional[Callable[[Sequence[T]], float]] = None,
    groups: Optional[Iterable[Hashable]] = None,
    n_resamples: int = 2000,
    confidence: float = 0.95,
    seed: int = 0,
) -> BootstrapResult:
    """Percentile CI for ``statistic(A) - statistic(B)`` using paired rows.

    The default statistic is the arithmetic mean and therefore expects numeric
    per-example scores (for example correctness indicators or per-item loss).
    If ``groups`` is supplied, whole groups are sampled with replacement; this
    is appropriate for multiple variants/questions sharing a source item.
    """

    _validate_bootstrap_options(n_resamples, confidence, seed)
    left = _materialize(values_a, "values_a")
    right = _materialize(values_b, "values_b")
    if len(left) != len(right):
        raise ValueError("values_a and values_b must have equal length")
    if statistic is None:
        statistic = fmean  # type: ignore[assignment]
    estimate = _checked_statistic(statistic, left) - _checked_statistic(statistic, right)
    clusters = _group_indices(groups, len(left)) if groups is not None else [[i] for i in range(len(left))]
    rng = random.Random(int(seed))
    replicates: List[float] = []
    for _ in range(int(n_resamples)):
        indices: List[int] = []
        for _ in range(len(clusters)):
            indices.extend(clusters[rng.randrange(len(clusters))])
        sample_a = [left[index] for index in indices]
        sample_b = [right[index] for index in indices]
        replicates.append(
            _checked_statistic(statistic, sample_a) - _checked_statistic(statistic, sample_b)
        )
    return _bootstrap_result(
        estimate,
        replicates,
        confidence=confidence,
        n_resamples=n_resamples,
        seed=seed,
        method="paired-group" if groups is not None else "paired",
    )


def group_bootstrap(
    values: Iterable[T],
    groups: Iterable[Hashable],
    *,
    statistic: Optional[Callable[[Sequence[T]], float]] = None,
    n_resamples: int = 2000,
    confidence: float = 0.95,
    seed: int = 0,
) -> BootstrapResult:
    """Percentile cluster-bootstrap CI for one statistic.

    Whole groups, rather than individual rows, are sampled with replacement.
    This preserves within-group dependence during each replicate.
    """

    _validate_bootstrap_options(n_resamples, confidence, seed)
    sample = _materialize(values, "values")
    clusters = _group_indices(groups, len(sample))
    if statistic is None:
        statistic = fmean  # type: ignore[assignment]
    estimate = _checked_statistic(statistic, sample)
    rng = random.Random(int(seed))
    replicates: List[float] = []
    for _ in range(int(n_resamples)):
        indices: List[int] = []
        for _ in range(len(clusters)):
            indices.extend(clusters[rng.randrange(len(clusters))])
        replicates.append(_checked_statistic(statistic, [sample[index] for index in indices]))
    return _bootstrap_result(
        estimate,
        replicates,
        confidence=confidence,
        n_resamples=n_resamples,
        seed=seed,
        method="group",
    )


grouped_bootstrap = group_bootstrap


__all__ = [
    "BootstrapResult",
    "CalibrationBin",
    "RiskCoveragePoint",
    "WilsonInterval",
    "accuracy",
    "ace",
    "adaptive_calibration_error",
    "area_under_risk_coverage_curve",
    "aurc",
    "brier_score",
    "calibration_bins",
    "chance_corrected_accuracy",
    "ece",
    "expected_calibration_error",
    "group_bootstrap",
    "grouped_bootstrap",
    "jensen_shannon_divergence",
    "js_divergence",
    "multiclass_brier_score",
    "negative_log_likelihood",
    "nll",
    "paired_bootstrap",
    "risk_coverage_curve",
    "total_variation_distance",
    "tv_distance",
    "validate_probabilities",
    "wilson_interval",
]

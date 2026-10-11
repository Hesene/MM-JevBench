from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import fmean

from mmjevbench.io import read_jsonl
from mmjevbench.metrics import wilson_interval


def valid_distribution(values: object, count: int, tolerance: float = 1e-6) -> bool:
    return (
        isinstance(values, list)
        and len(values) == count
        and all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= 1 for value in values)
        and abs(sum(values) - 1.0) <= tolerance
    )


def penalized_distribution(label: int, count: int, epsilon: float = 1e-15) -> list[float]:
    result = [(1.0 - epsilon) / (count - 1)] * count
    result[label] = epsilon
    return result


def top_label_ece(labels: list[int], probabilities: list[list[float]], bins: int = 10) -> float:
    observations = []
    for label, row in zip(labels, probabilities):
        prediction = max(range(len(row)), key=row.__getitem__)
        observations.append((max(row), int(prediction == label)))
    observations.sort(key=lambda item: item[0])
    bucket_count = min(bins, len(observations))
    quotient, remainder = divmod(len(observations), bucket_count)
    cursor = 0
    weighted = 0.0
    for index in range(bucket_count):
        size = quotient + int(index < remainder)
        bucket = observations[cursor : cursor + size]
        cursor += size
        weighted += size * abs(fmean(item[0] for item in bucket) - fmean(item[1] for item in bucket))
    return weighted / len(observations)


def aurc(labels: list[int], probabilities: list[list[float]]) -> float:
    rows = []
    for index, (label, row) in enumerate(zip(labels, probabilities)):
        prediction = max(range(len(row)), key=row.__getitem__)
        rows.append((max(row), int(prediction != label), index))
    rows.sort(key=lambda item: (-item[0], item[2]))
    errors = 0
    risks = []
    for selected, (_, error, _) in enumerate(rows, start=1):
        errors += error
        risks.append(errors / selected)
    return fmean(risks)


def score(rows: list[dict], prediction_map: dict[str, dict]) -> dict:
    labels: list[int] = []
    probabilities: list[list[float]] = []
    invalid = 0
    for row in rows:
        label = row["gold"]["label_index"]
        count = len(row["candidates"])
        prediction = prediction_map.get(row["id"])
        values = prediction.get("probabilities") if prediction else None
        if not valid_distribution(values, count):
            invalid += 1
            values = penalized_distribution(label, count)
        labels.append(label)
        probabilities.append([float(value) for value in values])
    correct = [int(max(range(len(values)), key=values.__getitem__) == label) for label, values in zip(labels, probabilities)]
    item_nll = [
        -math.log(max(values[label], 1e-15))
        for label, values in zip(labels, probabilities)
    ]
    item_brier = [
        sum((value - int(index == label)) ** 2 for index, value in enumerate(values))
        for label, values in zip(labels, probabilities)
    ]
    accuracy = fmean(correct)
    chance = fmean(1 / len(values) for values in probabilities)
    nll = fmean(item_nll)
    brier = fmean(item_brier)

    # A sample-level mean lets long trajectories or multi-question source
    # materials contribute once per row.  The group macro below first averages
    # within group_id, then gives every source group equal weight.  Both are
    # reported because they answer different estimands, and retaining the
    # original sample-level fields keeps the evaluator backward compatible.
    group_items: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"accuracy": [], "nll": [], "brier_sum": []}
    )
    for row, item_accuracy, loss, brier_score in zip(rows, correct, item_nll, item_brier):
        group_id = str(row.get("group_id", row["id"]))
        group_items[group_id]["accuracy"].append(float(item_accuracy))
        group_items[group_id]["nll"].append(loss)
        group_items[group_id]["brier_sum"].append(brier_score)
    group_macro = {
        metric: fmean(fmean(group[metric]) for group in group_items.values())
        for metric in ("accuracy", "nll", "brier_sum")
    }
    group_macro["n_groups"] = len(group_items)

    interval = wilson_interval(sum(correct), len(correct))
    return {
        "n": len(rows),
        "accuracy": accuracy,
        "accuracy_wilson95": [interval.lower, interval.upper],
        "chance_corrected_accuracy": (accuracy - chance) / (1 - chance),
        "nll": nll,
        "brier_sum": brier,
        "ece_equal_mass_10": top_label_ece(labels, probabilities, 10),
        "aurc": aurc(labels, probabilities),
        "invalid_or_missing": invalid,
        "invalid_rate": invalid / len(rows),
        "group_macro": group_macro,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", default="test")
    args = parser.parse_args()
    gold = [row for row in read_jsonl(args.gold) if row["split"] == args.split]
    predictions = {row["id"]: row for row in read_jsonl(args.predictions)}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in gold:
        grouped[row["track"]].append(row)
    tracks = {track: score(rows, predictions) for track, rows in sorted(grouped.items())}
    report = {
        "split": args.split,
        "tracks": tracks,
        "equal_track_macro": {
            metric: fmean(result[metric] for result in tracks.values())
            for metric in ["accuracy", "chance_corrected_accuracy", "nll", "brier_sum", "ece_equal_mass_10", "aurc", "invalid_rate"]
        },
        "equal_track_group_macro": {
            metric: fmean(result["group_macro"][metric] for result in tracks.values())
            for metric in ["accuracy", "nll", "brier_sum"]
        },
        "note": "Macro values are equal-track diagnostics; always report each track. group_macro first averages within group_id and then weights groups equally. Missing/invalid predictions receive a worst-case gold-probability penalty.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


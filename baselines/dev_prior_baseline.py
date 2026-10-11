from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from mmjevbench.io import read_jsonl, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("data", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--alpha", type=float, default=1.0, help="Laplace smoothing")
    args = parser.parse_args()
    rows = list(read_jsonl(args.data))
    counts: dict[tuple[str, int], Counter[int]] = defaultdict(Counter)
    for row in rows:
        if row["split"] == "dev":
            counts[(row["track"], len(row["candidates"]))][row["gold"]["label_index"]] += 1
    predictions = []
    for row in rows:
        if row["split"] != "test":
            continue
        count = len(row["candidates"])
        observed = counts[(row["track"], count)]
        denominator = sum(observed.values()) + args.alpha * count
        probabilities = [(observed[index] + args.alpha) / denominator for index in range(count)]
        predictions.append({
            "id": row["id"],
            "probabilities": probabilities,
            "probability_source": "dev_label_position_prior",
            "latency_ms": 0.0,
        })
    write_jsonl(args.output, predictions)
    print(f"wrote {len(predictions)} predictions")


if __name__ == "__main__":
    main()


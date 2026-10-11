from __future__ import annotations

import argparse
from pathlib import Path

from mmjevbench.io import read_jsonl, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("data", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", default="test")
    args = parser.parse_args()
    predictions = []
    for row in read_jsonl(args.data):
        if row["split"] != args.split:
            continue
        count = len(row["candidates"])
        predictions.append({
            "id": row["id"],
            "probabilities": [1.0 / count] * count,
            "probability_source": "native_baseline",
            "latency_ms": 0.0,
        })
    write_jsonl(args.output, predictions)
    print(f"wrote {len(predictions)} predictions")


if __name__ == "__main__":
    main()


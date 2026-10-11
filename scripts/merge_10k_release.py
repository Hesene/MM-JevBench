from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import yaml

from mmjevbench.expansion import assign_splits_preserving_anchor
from mmjevbench.io import read_jsonl, write_jsonl
from mmjevbench.validation import validate_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge an anchor-preserving MM-JevBench 10k release")
    parser.add_argument("inputs", nargs="+", type=Path, help="Full per-track canonical JSONL files")
    parser.add_argument("--anchor", type=Path, default=Path("datasets/processed/mmjevbench_public3.jsonl"))
    parser.add_argument("--config", type=Path, default=Path("configs/sampling_config_10k.yaml"))
    parser.add_argument("--schema", type=Path, default=Path("schemas/mmjevbench.schema.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, default=Path("reports/release_10k_summary.json"))
    parser.add_argument("--expect", type=int)
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    track_config = config["tracks"]
    rows = [row for path in args.inputs for row in read_jsonl(path)]
    counts = Counter(str(row["track"]) for row in rows)
    issues: list[dict] = []
    for track, observed in sorted(counts.items()):
        expected = int(track_config[track]["target"])
        if observed != expected:
            issues.append({"type": "track_count", "track": track, "expected": expected, "observed": observed})

    rows = assign_splits_preserving_anchor(
        rows,
        read_jsonl(args.anchor),
        {track: int(values["dev"]) for track, values in track_config.items()},
        str(config["seed"]),
    )
    validation = validate_rows(rows, args.schema)
    if args.expect is not None and len(rows) != args.expect:
        issues.append({"type": "total_count", "expected": args.expect, "observed": len(rows)})

    anchor = {row["id"]: row for row in read_jsonl(args.anchor)}
    expanded = {row["id"]: row for row in rows}
    preserved = sum(
        record_id in expanded and expanded[record_id]["split"] == row["split"]
        for record_id, row in anchor.items()
    )
    summary = {
        "release": config["release"],
        "records": len(rows),
        "valid": bool(validation["valid"] and not issues),
        "schema_issues": validation["issues"],
        "release_issues": issues,
        "tracks": dict(sorted(counts.items())),
        "splits": dict(Counter(row["split"] for row in rows)),
        "groups": len({row["group_id"] for row in rows}),
        "anchor_records": len(anchor),
        "anchor_ids_and_splits_preserved": preserved,
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if summary["valid"]:
        write_jsonl(args.output, rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

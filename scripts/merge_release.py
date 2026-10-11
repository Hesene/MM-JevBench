from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from mmjevbench.io import read_jsonl, write_jsonl
from mmjevbench.validation import validate_rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=Path("schemas/mmjevbench.schema.json"))
    parser.add_argument("--summary", type=Path, default=Path("reports/release_summary.json"))
    parser.add_argument("--expect", type=int)
    args = parser.parse_args()
    rows = [row for path in args.inputs for row in read_jsonl(path)]
    rows.sort(key=lambda row: row["id"])
    report = validate_rows(rows, args.schema)
    if args.expect is not None and len(rows) != args.expect:
        report["valid"] = False
        report["issues"].append({"type": "count", "message": f"expected {args.expect}, observed {len(rows)}"})
    summary = {
        **report,
        "tracks": Counter(row["track"] for row in rows),
        "splits": Counter(row["split"] for row in rows),
        "sources": Counter(row["source"]["dataset"] for row in rows),
        "groups": len({row["group_id"] for row in rows}),
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if report["valid"]:
        write_jsonl(args.output, rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

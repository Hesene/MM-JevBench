from __future__ import annotations

import argparse
import json
from pathlib import Path

from mmjevbench.validation import validate_jsonl


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("data", type=Path)
    parser.add_argument("--schema", type=Path, default=Path("schemas/mmjevbench.schema.json"))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = validate_jsonl(args.data, args.schema)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from mmjevbench.io import read_jsonl, write_jsonl
from mmjevbench.transforms import generate_coherence_suite


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("data", type=Path)
    parser.add_argument("--variants", type=Path, default=Path("datasets/coherence/variants.jsonl"))
    parser.add_argument("--relations", type=Path, default=Path("datasets/coherence/relations.jsonl"))
    parser.add_argument("--permutations", type=int, default=3)
    parser.add_argument("--seed", default="MM-JevBench-mini-v1.0")
    args = parser.parse_args()
    variants, relations = generate_coherence_suite(read_jsonl(args.data), args.seed, args.permutations)
    write_jsonl(args.variants, variants)
    write_jsonl(args.relations, relations)
    print({"variants": len(variants), "relations": len(relations), "families": Counter(row["family"] for row in relations)})


if __name__ == "__main__":
    main()


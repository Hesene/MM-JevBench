from __future__ import annotations

import argparse
import base64
import csv
import hashlib
from collections import defaultdict
from pathlib import Path

from mmjevbench.io import write_jsonl
from mmjevbench.records import make_choice_record
from mmjevbench.sampling import assign_dev_test, square_root_allocate, stratified_hash_sample

REVISION = "open-compass/MMBench@8eaac9ae42e22eaf42863b218455acd51268ba1c"
DATASETS = {
    "mmbench-dev-cn": {
        "track": "general_mmbench",
        "source_dataset": "MMBench-Dev-CN",
        "namespace": "mmbench_dev_cn",
    },
    "ccbench": {
        "track": "culture_ccbench",
        "source_dataset": "CCBench",
        "namespace": "ccbench",
    },
}


def load_eligible(tsv_path: Path, dataset_key: str) -> list[dict]:
    spec = DATASETS[dataset_key]
    records: list[dict] = []
    with tsv_path.open("r", encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle, delimiter="\t"):
            source_id = str(raw.get("index") or "").strip()
            if not source_id.isdigit() or int(source_id) >= 1_000_000:
                continue  # CircularEval rotations; only the canonical pass counts.
            question = str(raw.get("question") or "").strip()
            answer = str(raw.get("answer") or "").strip().upper()
            keyed_options = [(key, str(raw.get(key) or "").strip()) for key in "ABCD"]
            keyed_options = [(key, value) for key, value in keyed_options if value]
            keys = [key for key, _ in keyed_options]
            if not question or answer not in keys or len(keyed_options) < 2:
                continue
            try:
                image_payload = base64.b64decode(str(raw.get("image") or ""), validate=True)
            except (ValueError, TypeError):
                continue
            if not image_payload.startswith(b"\xff\xd8\xff"):
                continue
            image_sha = hashlib.sha256(image_payload).hexdigest()
            relative_media = f"datasets/media/{spec['namespace']}/{image_sha[:2]}/{image_sha}.jpg"
            record = make_choice_record(
                record_id=f"mmjev_{spec['namespace']}_{source_id}",
                track=spec["track"],
                domain=str(raw.get("category") or "general_multimodal"),
                source_dataset=spec["source_dataset"],
                source_id=source_id,
                source_version=REVISION,
                context=str(raw.get("hint") or "").strip(),
                question=question,
                options=[value for _, value in keyed_options],
                label_index=keys.index(answer),
                media={"image": [relative_media], "audio": [], "video": []},
                group_id=f"mmbench_image_{image_sha[:24]}",
                metadata={
                    "category": str(raw.get("category") or "unknown"),
                    "l2_category": str(raw.get("l2-category") or "unknown"),
                    "upstream_source": str(raw.get("source") or ""),
                    "source_split": str(raw.get("split") or "dev"),
                    "circular_variants_excluded": True,
                },
            )
            record["_image_payload"] = image_payload
            records.append(record)
    return records


def build(tsv_path: Path, output: Path, media_root: Path, dataset_key: str, target: int, seed: str) -> list[dict]:
    eligible = load_eligible(tsv_path, dataset_key)
    key = lambda row: (row["metadata"]["category"], row["metadata"]["l2_category"])
    capacities: dict[tuple, int] = defaultdict(int)
    for row in eligible:
        capacities[key(row)] += 1
    quotas = square_root_allocate(dict(capacities), target, minimum=1)
    selected = stratified_hash_sample(eligible, quotas, key, seed)
    selected = assign_dev_test(selected, seed, 0.2, key)
    written: set[str] = set()
    for row in selected:
        payload = row.pop("_image_payload")
        relative = row["state"]["media"]["image"][0]
        if relative in written:
            continue
        destination = media_root / Path(relative).relative_to("datasets/media")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        written.add(relative)
    write_jsonl(output, sorted(selected, key=lambda row: row["id"]))
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert canonical MMBench-Dev-CN or CCBench rows")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--dataset", choices=sorted(DATASETS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--media-root", type=Path, default=Path("datasets/media"))
    parser.add_argument("--target", type=int, required=True)
    parser.add_argument("--seed", default="MM-JevBench-10k-v1.0")
    args = parser.parse_args()
    rows = build(args.input, args.output, args.media_root, args.dataset, args.target, args.seed)
    print(f"wrote {len(rows)} {args.dataset} records to {args.output}")


if __name__ == "__main__":
    main()

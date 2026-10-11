from __future__ import annotations

import argparse
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from mmjevbench.io import read_jsonl


def json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def flatten(row: dict) -> dict:
    state = row["state"]
    media = state["media"]
    gold = row["gold"]
    source = row["source"]
    return {
        "id": row["id"],
        "split": row["split"],
        "track": row["track"],
        "task_type": row["task_type"],
        "domain": row["domain"],
        "language": row["language"],
        "group_id": row["group_id"],
        "question": state["question"],
        "context": state["context"],
        "modalities": row["modalities"],
        "candidates_json": json_text(row["candidates"]),
        "label_index": gold["label_index"],
        "label_key": gold["label_key"],
        "outcome_distribution": gold["outcome_distribution"],
        "image": media["image"],
        "audio": media["audio"],
        "video": media["video"],
        "history_json": json_text(state["history"]),
        "source_dataset": source["dataset"],
        "source_id": source["source_id"],
        "source_version": source["version"],
        "sampling_json": json_text(row["sampling"]),
        "metadata_json": json_text(row["metadata"]),
        "annotations_json": json_text(row["annotations"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the frozen MM-JevBench release for Hugging Face")
    parser.add_argument("--input", type=Path, default=Path("datasets/processed/10k/mmjevbench_10k.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("dist/huggingface"))
    parser.add_argument("--dataset-card", type=Path, default=Path("docs/huggingface_dataset_card.md"))
    args = parser.parse_args()

    rows = [flatten(row) for row in read_jsonl(args.input)]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for split in ("dev", "test"):
        split_rows = [row for row in rows if row["split"] == split]
        pq.write_table(
            pa.Table.from_pylist(split_rows),
            args.output_dir / f"{split}.parquet",
            compression="zstd",
        )
    (args.output_dir / "README.md").write_text(args.dataset_card.read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps({"records": len(rows), "dev": sum(r["split"] == "dev" for r in rows), "test": sum(r["split"] == "test" for r in rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

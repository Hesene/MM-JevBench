from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path

import pyarrow.parquet as pq

from mmjevbench.io import write_jsonl
from mmjevbench.records import make_choice_record
from mmjevbench.sampling import assign_dev_test, capped_allocate, deduplicate_by_group, stratified_hash_sample

SOURCE_VERSION = "m-a-p/CMMMU@d7ba0c8d5b73a45a0897ec29a9e841fab8acdde2"


def _replace_image_tags(question: str) -> str:
    counter = 0

    def replace(_: re.Match[str]) -> str:
        nonlocal counter
        counter += 1
        return f"[IMAGE_{counter}]"

    return re.sub(r'<img=["\'][^"\']+["\']>', replace, question or "").strip()


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    try:
        parsed = ast.literal_eval(str(value))
        return [str(item) for item in parsed] if isinstance(parsed, list) else [str(value)]
    except (SyntaxError, ValueError):
        return [str(value)]


def load_excluded_ids(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("CMMMU", [])
    if not isinstance(entries, list):
        raise ValueError("configs/exclusions.json: CMMMU must be a list")
    excluded: set[str] = set()
    for entry in entries:
        if isinstance(entry, str):
            excluded.add(entry)
        elif isinstance(entry, dict) and "source_id" in entry:
            excluded.add(str(entry["source_id"]))
        else:
            raise ValueError("each CMMMU exclusion must be a source_id string or object")
    return excluded


def load_eligible(
    parquet_dir: Path,
    excluded_ids: set[str] | None = None,
    include_judgment: bool = False,
) -> list[dict]:
    excluded_ids = excluded_ids or set()
    records: list[dict] = []
    for parquet_path in sorted(parquet_dir.glob("*.parquet")):
        for raw in pq.read_table(parquet_path).to_pylist():
            question_type = str(raw.get("type"))
            if question_type not in ({"选择", "判断"} if include_judgment else {"选择"}):
                continue
            source_id = str(raw["id"])
            if source_id in excluded_ids:
                continue
            answer_text = str(raw.get("answer") or "").strip()
            if question_type == "选择":
                options = [str(raw.get(f"option{i}") or "").strip() for i in range(1, 5)]
                while options and not options[-1]:
                    options.pop()
                answer_match = re.fullmatch(r"[\[\('\"\s]*([A-D])[\]\)'\"\s]*", answer_text.upper())
                if len(options) < 2 or not answer_match:
                    continue
                answer = answer_match.group(1)
                label_index = ord(answer) - ord("A")
                if label_index >= len(options):
                    continue
            else:
                judgment_labels = {"错": 0, "对": 1}
                if answer_text not in judgment_labels:
                    continue
                options = ["错误（错）", "正确（对）"]
                label_index = judgment_labels[answer_text]
            image_payloads: list[tuple[str, bytes]] = []
            for index in range(1, 6):
                image = raw.get(f"image_{index}")
                if not image or not image.get("bytes"):
                    continue
                filename = str(raw.get(f"image_{index}_filename") or image.get("path") or f"{raw['id']}_{index}.png")
                image_payloads.append((Path(filename).name, image["bytes"]))
            if not image_payloads:
                continue
            media_fingerprint = hashlib.sha256(b"\x00".join(payload for _, payload in image_payloads)).hexdigest()
            relative_media = [f"datasets/media/cmmmu/{source_id}/{name}" for name, _ in image_payloads]
            question = _replace_image_tags(str(raw.get("question") or ""))
            if question_type == "判断":
                question = f"判断下列陈述是否正确：\n{question}"
            record = make_choice_record(
                record_id=f"mmjev_cmmmu_{source_id}",
                track="academic_cmmmu",
                domain=str(raw.get("category") or "academic"),
                source_dataset="CMMMU",
                source_id=source_id,
                source_version=SOURCE_VERSION,
                question=question,
                options=options,
                label_index=label_index,
                media={"image": relative_media, "audio": [], "video": []},
                group_id=f"cmmmu_media_{media_fingerprint[:24]}",
                metadata={
                    "subject": str(raw.get("subcategory") or "unknown"),
                    "discipline": str(raw.get("category") or "unknown"),
                    "difficulty": str(raw.get("difficulty_level") or "unknown"),
                    "image_types": _as_list(raw.get("img_type")),
                    "education_distribution": str(raw.get("distribution") or "unknown"),
                    "source_split_file": parquet_path.name,
                    "source_url": str(raw.get("source") or ""),
                    "source_question_type": question_type,
                },
            )
            record["_image_payloads"] = image_payloads
            records.append(record)
    return records


def build(
    parquet_dir: Path,
    output: Path,
    media_root: Path,
    target: int,
    seed: str,
    exclusions: Path | None = None,
    include_judgment: bool = False,
    retain_group_siblings: bool = False,
) -> list[dict]:
    excluded_ids = load_excluded_ids(exclusions)
    eligible = load_eligible(parquet_dir, excluded_ids, include_judgment)
    if not retain_group_siblings:
        eligible = deduplicate_by_group(eligible, seed)
    capacities: dict[str, int] = {}
    for row in eligible:
        subject = row["metadata"]["subject"]
        capacities[subject] = capacities.get(subject, 0) + 1
    quotas = capped_allocate(capacities, target, minimum=0)
    selected = stratified_hash_sample(eligible, quotas, lambda row: row["metadata"]["subject"], seed)
    selected = assign_dev_test(selected, seed, 0.2, lambda row: row["metadata"]["subject"])

    for row in selected:
        payloads = row.pop("_image_payloads")
        for relative, (_, payload) in zip(row["state"]["media"]["image"], payloads):
            destination = media_root / Path(relative).relative_to("datasets/media")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
    write_jsonl(output, sorted(selected, key=lambda row: row["id"]))
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert and stratify CMMMU dev/validation parquet files")
    parser.add_argument("--input", type=Path, required=True, help="Directory containing CMMMU parquet shards")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--media-root", type=Path, default=Path("datasets/media"))
    parser.add_argument("--target", type=int, default=500)
    parser.add_argument("--seed", default="MM-JevBench-mini-v1.0")
    parser.add_argument(
        "--exclusions",
        type=Path,
        default=Path("configs/exclusions.json"),
        help="Frozen source-level exclusions after duplicate/error adjudication",
    )
    parser.add_argument("--include-judgment", action="store_true", help="Include source 判断 items as binary Choice")
    parser.add_argument(
        "--retain-group-siblings",
        action="store_true",
        help="Retain multiple canonical questions sharing a media group; split remains group-aware",
    )
    args = parser.parse_args()
    rows = build(
        args.input,
        args.output,
        args.media_root,
        args.target,
        args.seed,
        args.exclusions,
        args.include_judgment,
        args.retain_group_siblings,
    )
    print(f"wrote {len(rows)} CMMMU records to {args.output}")


if __name__ == "__main__":
    main()


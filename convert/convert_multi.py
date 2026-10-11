from __future__ import annotations

import argparse
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath

from mmjevbench.io import stable_digest, write_jsonl
from mmjevbench.records import make_choice_record
from mmjevbench.sampling import assign_dev_test, deduplicate_by_group, square_root_allocate, stable_priority, stratified_hash_sample

SOURCE_VERSION = "MULTI-v1.3.1-20251016"
SCENARIO_JSON = "problem_v1.3.1_20241210.json"
ELITE_JSON = "hard_list_v1.3.0_20241203.json"


def parse_options(content: str) -> tuple[str, list[tuple[str, str]]]:
    text = content or ""
    marker_pattern = re.compile(r"(?m)^\s*([A-Ha-h])\s*[\.．、]\s*")
    markers = list(marker_pattern.finditer(text))
    valid_starts: list[int] = []
    for start, marker in enumerate(markers):
        if marker.group(1).upper() != "A":
            continue
        keys = [item.group(1).upper() for item in markers[start:]]
        expected = [chr(ord("A") + index) for index in range(len(keys))]
        if len(keys) >= 2 and keys == expected:
            valid_starts.append(start)
    if not valid_starts:
        return content.strip(), []
    start = min(valid_starts, key=lambda index: (-len(markers[index:]), markers[index].start()))
    option_markers = markers[start:]
    options: list[tuple[str, str]] = []
    for index, marker in enumerate(option_markers):
        end = option_markers[index + 1].start() if index + 1 < len(option_markers) else len(text)
        option_text = text[marker.end() : end].strip()
        if not option_text:
            return content.strip(), []
        options.append((marker.group(1).upper(), option_text))
    question = text[: option_markers[0].start()].strip()
    return question, options


def _zip_media_path(raw_path: str) -> str:
    normalized = raw_path.replace("\\", "/")
    marker = "images/"
    if marker not in normalized:
        raise ValueError(f"unexpected MULTI image path: {raw_path}")
    return marker + normalized.split(marker, 1)[1]


def load_eligible(archive: Path) -> tuple[list[dict], zipfile.ZipFile]:
    zipped = zipfile.ZipFile(archive)
    problems = json.loads(zipped.read(SCENARIO_JSON))
    elite = set(json.loads(zipped.read(ELITE_JSON)))
    records: list[dict] = []
    for problem_id, raw in problems.items():
        media_paths = [_zip_media_path(path) for path in raw.get("img_paths") or []]
        if not media_paths:
            continue
        types = raw.get("problem_type_list") or []
        contents = raw.get("problem_content_list") or []
        answers = raw.get("problem_answer_list") or []
        for index, question_type in enumerate(types):
            if question_type != "单选" or index >= len(contents) or index >= len(answers):
                continue
            question, keyed_options = parse_options(str(contents[index]))
            keys = [key for key, _ in keyed_options]
            answer = str(answers[index]).strip().upper()
            if answer not in keys:
                continue
            source_id = f"{problem_id}_{index}"
            relative_media = [f"datasets/media/multi/{path.removeprefix('images/')}" for path in media_paths]
            record = make_choice_record(
                record_id=f"mmjev_multi_{source_id}",
                track="exam_multi",
                domain=str((raw.get("subject") or ["academic"])[0]),
                source_dataset="MULTI-Benchmark",
                source_id=source_id,
                source_version=SOURCE_VERSION,
                question=question,
                options=[text for _, text in keyed_options],
                label_index=keys.index(answer),
                media={"image": relative_media, "audio": [], "video": []},
                group_id=f"multi_problem_{stable_digest(problem_id)[:24]}",
                metadata={
                    "problem_id": problem_id,
                    "subject": str((raw.get("subject") or ["unknown"])[0]),
                    "education": str(raw.get("education") or "unknown"),
                    "difficulty": raw.get("difficulty"),
                    "quality": raw.get("quality"),
                    "image_count": len(media_paths),
                    "image_bin": "multiple" if len(media_paths) > 1 else "single",
                    "is_multi_elite": source_id in elite,
                    "zip_media_paths": media_paths,
                    "source_url": str(raw.get("problem_url") or ""),
                },
            )
            records.append(record)
    return records, zipped


def _constrained_quotas(capacities: dict[tuple, int], total: int, multi_min: int, elite_min: int) -> dict[tuple, int]:
    quotas = square_root_allocate(capacities, total, minimum=1)

    def enforce(flag_index: int, required: int) -> None:
        required = min(required, sum(size for key, size in capacities.items() if key[flag_index]))
        while sum(value for key, value in quotas.items() if key[flag_index]) < required:
            receivers = [key for key in quotas if key[flag_index] and quotas[key] < capacities[key]]
            donors = [key for key in quotas if not key[flag_index] and quotas[key] > 0]
            if not receivers or not donors:
                break
            receiver = sorted(receivers, key=lambda key: (-(capacities[key] - quotas[key]), str(key)))[0]
            donor = sorted(donors, key=lambda key: (-quotas[key], str(key)))[0]
            quotas[receiver] += 1
            quotas[donor] -= 1

    enforce(1, multi_min)
    enforce(2, elite_min)
    return quotas


def build(archive: Path, output: Path, media_root: Path, target: int, seed: str) -> list[dict]:
    eligible, zipped = load_eligible(archive)
    try:
        eligible = deduplicate_by_group(eligible, seed)
        key = lambda row: (
            row["metadata"]["subject"],
            row["metadata"]["image_bin"] == "multiple",
            bool(row["metadata"]["is_multi_elite"]),
        )
        capacities: dict[tuple, int] = defaultdict(int)
        for row in eligible:
            capacities[key(row)] += 1
        quotas = _constrained_quotas(dict(capacities), target, min(100, target), min(100, target))
        selected = stratified_hash_sample(eligible, quotas, key, seed)
        selected = assign_dev_test(selected, seed, 0.2, key)
        extracted: set[str] = set()
        available = set(zipped.namelist())
        for row in selected:
            paths = row["metadata"].pop("zip_media_paths")
            for zip_path, relative in zip(paths, row["state"]["media"]["image"]):
                if zip_path in extracted:
                    continue
                if zip_path not in available or PurePosixPath(zip_path).is_absolute() or ".." in PurePosixPath(zip_path).parts:
                    raise FileNotFoundError(f"unsafe or missing archive member: {zip_path}")
                destination = media_root / Path(relative).relative_to("datasets/media")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(zipped.read(zip_path))
                extracted.add(zip_path)
        write_jsonl(output, sorted(selected, key=lambda row: row["id"]))
        return selected
    finally:
        zipped.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert MULTI v1.3.1 to MM-JevBench")
    parser.add_argument("--input", type=Path, required=True, help="Official MULTI release zip")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--media-root", type=Path, default=Path("datasets/media"))
    parser.add_argument("--target", type=int, default=500)
    parser.add_argument("--seed", default="MM-JevBench-mini-v1.0")
    args = parser.parse_args()
    rows = build(args.input, args.output, args.media_root, args.target, args.seed)
    print(f"wrote {len(rows)} MULTI records to {args.output}")


if __name__ == "__main__":
    main()


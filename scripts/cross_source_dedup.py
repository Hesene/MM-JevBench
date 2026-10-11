from __future__ import annotations

import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from PIL import Image

from mmjevbench.io import read_jsonl, sha256_file


def normalize_text(value: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value.lower())


def record_text(row: dict) -> str:
    return normalize_text(row["state"]["question"] + "".join(candidate["text"] for candidate in row["candidates"]))


def dhash(path: Path) -> int:
    with Image.open(path) as image:
        resized = image.convert("L").resize((9, 8))
        pixel_reader = getattr(resized, "get_flattened_data", resized.getdata)
        pixels = list(pixel_reader())
    value = 0
    for y in range(8):
        for x in range(8):
            value = (value << 1) | int(pixels[y * 9 + x] > pixels[y * 9 + x + 1])
    return value


def hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def main() -> None:
    parser = argparse.ArgumentParser(description="Conservative cross-source duplicate candidate audit")
    parser.add_argument("--data", type=Path, default=Path("datasets/processed/mmjevbench_public3.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("reports/cross_source_dedup.json"))
    parser.add_argument("--text-ratio", type=float, default=0.92)
    parser.add_argument("--image-hamming", type=int, default=4)
    args = parser.parse_args()
    rows = list(read_jsonl(args.data))
    academic = [row for row in rows if row["track"] in {"academic_cmmmu", "exam_multi"}]
    by_track = {track: [row for row in academic if row["track"] == track] for track in {"academic_cmmmu", "exam_multi"}}
    left_rows = by_track["academic_cmmmu"]
    right_rows = by_track["exam_multi"]

    exact_text = []
    near_text = []
    left_text = {row["id"]: record_text(row) for row in left_rows}
    right_text = {row["id"]: record_text(row) for row in right_rows}
    right_exact: dict[str, list[str]] = {}
    for record_id, text in right_text.items():
        right_exact.setdefault(text, []).append(record_id)
    for record_id, text in left_text.items():
        for other in right_exact.get(text, []):
            exact_text.append([record_id, other])
    for left in left_rows:
        a = left_text[left["id"]]
        if len(a) < 20:
            continue
        for right in right_rows:
            b = right_text[right["id"]]
            if len(b) < 20 or abs(len(a) - len(b)) / max(len(a), len(b)) > 0.2:
                continue
            ratio = SequenceMatcher(None, a, b, autojunk=False).ratio()
            if ratio >= args.text_ratio:
                near_text.append({"left": left["id"], "right": right["id"], "ratio": ratio})

    def image_rows(items: list[dict]) -> list[tuple[str, str, Path]]:
        result = []
        for row in items:
            for raw in row["state"]["media"].get("image", []):
                path = Path(raw)
                if path.exists():
                    result.append((row["id"], raw, path))
        return result

    left_images = [(rid, raw, path, sha256_file(path), dhash(path)) for rid, raw, path in image_rows(left_rows)]
    right_images = [(rid, raw, path, sha256_file(path), dhash(path)) for rid, raw, path in image_rows(right_rows)]
    exact_images = []
    near_images = []
    right_hash: dict[str, list[tuple[str, str]]] = {}
    for rid, raw, _, digest, _ in right_images:
        right_hash.setdefault(digest, []).append((rid, raw))
    for rid, raw, _, digest, _ in left_images:
        for other_id, other_raw in right_hash.get(digest, []):
            exact_images.append({"left": rid, "right": other_id, "left_path": raw, "right_path": other_raw})
    for left_id, left_raw, _, _, left_dhash in left_images:
        for right_id, right_raw, _, _, right_dhash in right_images:
            distance = hamming(left_dhash, right_dhash)
            if distance <= args.image_hamming:
                near_images.append({"left": left_id, "right": right_id, "distance": distance, "left_path": left_raw, "right_path": right_raw})

    report = {
        "thresholds": {"text_sequence_ratio": args.text_ratio, "image_dhash_hamming": args.image_hamming},
        "exact_text_pairs": exact_text,
        "near_text_candidates": near_text,
        "exact_image_pairs": exact_images,
        "near_image_candidates": near_images,
        "decision": "Exact pairs must be grouped/removed. Near pairs are review candidates only and must not be auto-deleted.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: len(value) for key, value in report.items() if isinstance(value, list)}, ensure_ascii=False))


if __name__ == "__main__":
    main()


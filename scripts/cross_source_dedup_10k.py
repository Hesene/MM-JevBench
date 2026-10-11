from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image, UnidentifiedImageError

from mmjevbench.io import read_jsonl, sha256_file


FOCUS_LEFT = {"MMBench-Dev-CN", "CCBench"}
FOCUS_RIGHT = {"CMMMU", "MULTI-Benchmark"}
SEPARATOR = "\x1f"


def normalize_text(value: Any) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(value or "").lower())


def source_name(row: dict[str, Any]) -> str:
    source = row.get("source", {})
    if isinstance(source, dict):
        return str(source.get("dataset") or source.get("name") or "unknown")
    return str(source or "unknown")


def candidate_texts(row: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for candidate in row.get("candidates", []):
        if isinstance(candidate, dict):
            value = candidate.get("text")
            if value in (None, ""):
                value = candidate.get("value")
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            value = candidate
        result.append(str(value or ""))
    return result


def row_text(row: dict[str, Any]) -> dict[str, str]:
    state = row.get("state", {})
    context = str(state.get("context") or "")
    question = str(state.get("question") or "")
    candidates = candidate_texts(row)
    normalized_candidates = sorted(filter(None, (normalize_text(item) for item in candidates)))
    decision = SEPARATOR.join(
        [normalize_text(context), normalize_text(question), *normalized_candidates]
    )
    search = normalize_text(context + question + " ".join(sorted(candidates)))
    display = " ".join(part for part in [context, question, " / ".join(candidates)] if part)
    return {
        "question": normalize_text(question),
        "decision": decision,
        "search": search,
        "display": display,
    }


def char_ngrams(value: str, width: int = 3) -> set[str]:
    if len(value) <= width:
        return {value} if value else set()
    return {value[index : index + width] for index in range(len(value) - width + 1)}


def jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def simhash(shingles: Iterable[str]) -> int:
    vector = [0] * 64
    for shingle in shingles:
        digest = hashlib.blake2b(shingle.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        for bit in range(64):
            vector[bit] += 1 if value & (1 << bit) else -1
    result = 0
    for bit, weight in enumerate(vector):
        if weight >= 0:
            result |= 1 << bit
    return result


def source_pair(left: dict[str, Any], right: dict[str, Any]) -> str:
    return " <> ".join(sorted([source_name(left), source_name(right)]))


def is_focus_pair(left: dict[str, Any], right: dict[str, Any]) -> bool:
    sources = {source_name(left), source_name(right)}
    return bool(sources & FOCUS_LEFT) and bool(sources & FOCUS_RIGHT)


def record_ref(row: dict[str, Any]) -> dict[str, str]:
    return {
        "id": str(row.get("id", "")),
        "source": source_name(row),
        "track": str(row.get("track", "")),
    }


def cross_source_groups(
    rows: list[dict[str, Any]],
    keys: list[str],
    texts: list[dict[str, str]],
    field: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, key in enumerate(keys):
        if key:
            grouped[key].append(index)
    result: list[dict[str, Any]] = []
    for key, indexes in grouped.items():
        sources = {source_name(rows[index]) for index in indexes}
        if len(sources) < 2:
            continue
        counts = Counter(source_name(rows[index]) for index in indexes)
        pair_count = sum(
            counts[left] * counts[right]
            for left, right in combinations(sorted(counts), 2)
        )
        result.append(
            {
                "signature_sha256": hashlib.sha256(key.encode("utf-8")).hexdigest(),
                "normalized_length": len(key),
                "cross_source_pair_count": pair_count,
                "sources": dict(sorted(counts.items())),
                "records": [record_ref(rows[index]) for index in indexes],
                "example": texts[indexes[0]]["display"][:400],
                "field": field,
            }
        )
    return sorted(
        result,
        key=lambda item: (-item["cross_source_pair_count"], -item["normalized_length"]),
    )


def expand_group_pairs(groups: list[dict[str, Any]]) -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    for group in groups:
        for left, right in combinations(group["records"], 2):
            if left["source"] != right["source"]:
                result.add(tuple(sorted([left["id"], right["id"]])))
    return result


def near_text_candidates(
    rows: list[dict[str, Any]],
    texts: list[dict[str, str]],
    exact_pairs: set[tuple[str, str]],
    threshold: float,
    max_candidates: int,
    max_bucket_size: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    full_grams = [char_ngrams(item["search"]) for item in texts]
    question_grams = [char_ngrams(item["question"]) for item in texts]
    document_frequency: Counter[str] = Counter()
    for grams in full_grams:
        document_frequency.update(grams)

    buckets: dict[tuple[str, Any], list[int]] = defaultdict(list)
    eligible = 0
    for index, item in enumerate(texts):
        if len(item["search"]) < 12:
            continue
        eligible += 1
        rare = sorted(full_grams[index], key=lambda gram: (document_frequency[gram], gram))[:24]
        for gram in rare:
            buckets[("gram", gram)].append(index)
        signature = simhash(full_grams[index])
        for band in range(8):
            buckets[("simhash", band, (signature >> (band * 8)) & 0xFF)].append(index)

    pair_indexes: set[tuple[int, int]] = set()
    skipped_buckets = 0
    for indexes in buckets.values():
        unique_indexes = sorted(set(indexes))
        if len(unique_indexes) > max_bucket_size:
            skipped_buckets += 1
            continue
        for left_index, right_index in combinations(unique_indexes, 2):
            if source_name(rows[left_index]) == source_name(rows[right_index]):
                continue
            left_id = str(rows[left_index].get("id", ""))
            right_id = str(rows[right_index].get("id", ""))
            if tuple(sorted([left_id, right_id])) not in exact_pairs:
                pair_indexes.add((left_index, right_index))

    candidates: list[dict[str, Any]] = []
    for left_index, right_index in pair_indexes:
        left_text = texts[left_index]
        right_text = texts[right_index]
        left_value = left_text["search"]
        right_value = right_text["search"]
        if not left_value or not right_value:
            continue
        length_ratio = min(len(left_value), len(right_value)) / max(len(left_value), len(right_value))
        if length_ratio < 0.55:
            continue
        full_ratio = SequenceMatcher(None, left_value, right_value, autojunk=False).ratio()
        full_jaccard = jaccard(full_grams[left_index], full_grams[right_index])
        question_ratio = 0.0
        question_jaccard = 0.0
        if texts[left_index]["question"] and texts[right_index]["question"]:
            question_ratio = SequenceMatcher(
                None,
                texts[left_index]["question"],
                texts[right_index]["question"],
                autojunk=False,
            ).ratio()
            question_jaccard = jaccard(question_grams[left_index], question_grams[right_index])
        full_match = full_ratio >= threshold and full_jaccard >= max(0.50, threshold - 0.28)
        question_match = (
            min(len(texts[left_index]["question"]), len(texts[right_index]["question"])) >= 12
            and question_ratio >= max(0.94, threshold)
            and question_jaccard >= 0.70
            and full_ratio >= 0.55
        )
        if not (full_match or question_match):
            continue
        left = rows[left_index]
        right = rows[right_index]
        candidates.append(
            {
                "left": record_ref(left),
                "right": record_ref(right),
                "source_pair": source_pair(left, right),
                "focus_pair": is_focus_pair(left, right),
                "full_sequence_ratio": round(full_ratio, 6),
                "full_trigram_jaccard": round(full_jaccard, 6),
                "question_sequence_ratio": round(question_ratio, 6),
                "question_trigram_jaccard": round(question_jaccard, 6),
                "left_text": left_text["display"][:400],
                "right_text": right_text["display"][:400],
                "review_only": True,
            }
        )
    candidates.sort(
        key=lambda item: (
            not item["focus_pair"],
            -max(item["full_sequence_ratio"], item["question_sequence_ratio"]),
            -item["full_trigram_jaccard"],
            item["left"]["id"],
            item["right"]["id"],
        )
    )
    stats = {
        "eligible_records": eligible,
        "candidate_pairs_scored": len(pair_indexes),
        "matching_pairs_before_cap": len(candidates),
        "skipped_oversized_buckets": skipped_buckets,
        "reported_pairs": min(len(candidates), max_candidates),
    }
    return candidates[:max_candidates], stats


def dct_matrix(size: int) -> np.ndarray:
    positions = np.arange(size, dtype=np.float64)
    frequencies = positions[:, None]
    matrix = np.cos(np.pi * (2 * positions + 1) * frequencies / (2 * size))
    matrix[0, :] *= np.sqrt(1 / size)
    matrix[1:, :] *= np.sqrt(2 / size)
    return matrix


DCT_32 = dct_matrix(32)


def image_hashes(path: Path) -> tuple[int, int, int, int, str]:
    with Image.open(path) as image:
        width, height = image.size
        mode = image.mode
        grayscale = image.convert("L")
        dhash_pixels = np.asarray(grayscale.resize((9, 8), Image.Resampling.LANCZOS))
        differences = dhash_pixels[:, :-1] > dhash_pixels[:, 1:]
        dhash_value = 0
        for bit in differences.flatten():
            dhash_value = (dhash_value << 1) | int(bit)
        phash_pixels = np.asarray(
            grayscale.resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float64
        )
        transformed = DCT_32 @ phash_pixels @ DCT_32.T
        low = transformed[:8, :8]
        median = float(np.median(low.flatten()[1:]))
        phash_value = 0
        for bit in (low > median).flatten():
            phash_value = (phash_value << 1) | int(bit)
    return dhash_value, phash_value, width, height, mode


def resolve_media_path(raw: str, project_root: Path) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else project_root / path


def image_inventory(
    rows: list[dict[str, Any]], project_root: Path
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[dict[str, str]]]:
    images: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    unreadable: list[dict[str, str]] = []
    for row_index, row in enumerate(rows):
        media = row.get("state", {}).get("media", {})
        for raw_value in media.get("image", []) or []:
            raw = str(raw_value)
            path = resolve_media_path(raw, project_root)
            if not path.is_file():
                missing.append({**record_ref(row), "path": raw})
                continue
            try:
                dhash_value, phash_value, width, height, mode = image_hashes(path)
                digest = sha256_file(path)
            except (OSError, ValueError, UnidentifiedImageError) as error:
                unreadable.append({**record_ref(row), "path": raw, "error": str(error)})
                continue
            images.append(
                {
                    "row_index": row_index,
                    "id": str(row.get("id", "")),
                    "source": source_name(row),
                    "track": str(row.get("track", "")),
                    "path": raw,
                    "sha256": digest,
                    "dhash": dhash_value,
                    "phash": phash_value,
                    "width": width,
                    "height": height,
                    "mode": mode,
                }
            )
    return images, missing, unreadable


def exact_image_groups(images: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for image in images:
        grouped[image["sha256"]].append(image)
    result: list[dict[str, Any]] = []
    for digest, items in grouped.items():
        sources = Counter(item["source"] for item in items)
        if len(sources) < 2:
            continue
        pair_count = sum(sources[left] * sources[right] for left, right in combinations(sorted(sources), 2))
        result.append(
            {
                "sha256": digest,
                "cross_source_pair_count": pair_count,
                "sources": dict(sorted(sources.items())),
                "images": [
                    {
                        "id": item["id"],
                        "source": item["source"],
                        "track": item["track"],
                        "path": item["path"],
                        "width": item["width"],
                        "height": item["height"],
                    }
                    for item in items
                ],
            }
        )
    return sorted(result, key=lambda item: -item["cross_source_pair_count"])


def expand_image_pairs(groups: list[dict[str, Any]]) -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    for group in groups:
        for left, right in combinations(group["images"], 2):
            if left["source"] != right["source"]:
                result.add(tuple(sorted([left["id"], right["id"]])))
    return result


def hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def near_image_candidates(
    rows: list[dict[str, Any]],
    images: list[dict[str, Any]],
    exact_pairs: set[tuple[str, str]],
    threshold: int,
    max_candidates: int,
    max_bucket_size: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    buckets: dict[tuple[str, int, int], list[int]] = defaultdict(list)
    for index, image in enumerate(images):
        for kind in ("dhash", "phash"):
            value = int(image[kind])
            for band in range(8):
                buckets[(kind, band, (value >> (band * 8)) & 0xFF)].append(index)

    pair_indexes: set[tuple[int, int]] = set()
    skipped_buckets = 0
    for indexes in buckets.values():
        unique_indexes = sorted(set(indexes))
        if len(unique_indexes) > max_bucket_size:
            skipped_buckets += 1
            continue
        for left_index, right_index in combinations(unique_indexes, 2):
            left = images[left_index]
            right = images[right_index]
            if left["source"] == right["source"]:
                continue
            record_pair = tuple(sorted([left["id"], right["id"]]))
            if record_pair not in exact_pairs and left["sha256"] != right["sha256"]:
                pair_indexes.add((left_index, right_index))

    best_by_record_pair: dict[tuple[str, str], dict[str, Any]] = {}
    for left_index, right_index in pair_indexes:
        left_image = images[left_index]
        right_image = images[right_index]
        left_aspect = left_image["width"] / max(left_image["height"], 1)
        right_aspect = right_image["width"] / max(right_image["height"], 1)
        aspect_delta = abs(left_aspect - right_aspect) / max(left_aspect, right_aspect, 1e-9)
        if aspect_delta > 0.12:
            continue
        dhash_distance = hamming(left_image["dhash"], right_image["dhash"])
        phash_distance = hamming(left_image["phash"], right_image["phash"])
        # A dHash-only collision is common for sparse diagrams, tables, and traffic
        # signs. Keep a pair only when pHash independently agrees, or when pHash is
        # itself within the strict threshold. This remains a candidate rule, not a
        # duplicate decision.
        dual_hash_match = dhash_distance <= threshold and phash_distance <= max(12, threshold * 2)
        if phash_distance > threshold and not dual_hash_match:
            continue
        left_row = rows[left_image["row_index"]]
        right_row = rows[right_image["row_index"]]
        candidate = {
            "left": record_ref(left_row),
            "right": record_ref(right_row),
            "source_pair": source_pair(left_row, right_row),
            "focus_pair": is_focus_pair(left_row, right_row),
            "dhash_hamming": dhash_distance,
            "phash_hamming": phash_distance,
            "aspect_ratio_relative_delta": round(aspect_delta, 6),
            "left_path": left_image["path"],
            "right_path": right_image["path"],
            "left_size": [left_image["width"], left_image["height"]],
            "right_size": [right_image["width"], right_image["height"]],
            "review_only": True,
        }
        key = tuple(sorted([left_image["id"], right_image["id"]]))
        previous = best_by_record_pair.get(key)
        score = (min(dhash_distance, phash_distance), dhash_distance + phash_distance)
        if previous is None or score < (
            min(previous["dhash_hamming"], previous["phash_hamming"]),
            previous["dhash_hamming"] + previous["phash_hamming"],
        ):
            best_by_record_pair[key] = candidate

    candidates = list(best_by_record_pair.values())
    candidates.sort(
        key=lambda item: (
            not item["focus_pair"],
            min(item["dhash_hamming"], item["phash_hamming"]),
            item["dhash_hamming"] + item["phash_hamming"],
            item["left"]["id"],
            item["right"]["id"],
        )
    )
    stats = {
        "readable_images": len(images),
        "candidate_image_pairs_scored": len(pair_indexes),
        "matching_record_pairs_before_cap": len(candidates),
        "skipped_oversized_buckets": skipped_buckets,
        "reported_pairs": min(len(candidates), max_candidates),
    }
    return candidates[:max_candidates], stats


def enrich_text_candidates_with_image_evidence(
    candidates: list[dict[str, Any]], images: list[dict[str, Any]]
) -> None:
    by_record: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for image in images:
        by_record[image["id"]].append(image)
    for candidate in candidates:
        left_images = by_record.get(candidate["left"]["id"], [])
        right_images = by_record.get(candidate["right"]["id"], [])
        compared = len(left_images) * len(right_images)
        best: dict[str, Any] | None = None
        for left_image in left_images:
            for right_image in right_images:
                dhash_distance = hamming(left_image["dhash"], right_image["dhash"])
                phash_distance = hamming(left_image["phash"], right_image["phash"])
                evidence = {
                    "exact_sha256": left_image["sha256"] == right_image["sha256"],
                    "dhash_hamming": dhash_distance,
                    "phash_hamming": phash_distance,
                    "left_path": left_image["path"],
                    "right_path": right_image["path"],
                }
                score = (
                    not evidence["exact_sha256"],
                    phash_distance,
                    dhash_distance,
                )
                if best is None or score < (
                    not best["exact_sha256"],
                    best["phash_hamming"],
                    best["dhash_hamming"],
                ):
                    best = evidence
        candidate["image_evidence"] = {
            "image_pairs_compared": compared,
            "best_pair": best,
        }


def pair_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(item["source_pair"] for item in items).items()))


def markdown_escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    if not rows:
        return ["_None._"]
    result = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    result.extend("| " + " | ".join(markdown_escape(value) for value in row) + " |" for row in rows)
    return result


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    verdict = report["verdict"]
    lines = [
        "# MM-JevBench 10k Cross-source Deduplication Audit",
        "",
        f"- Input: `{report['input']['path']}`",
        f"- Input SHA-256: `{report['input']['sha256']}`",
        f"- Generated (UTC): {report['generated_utc']}",
        f"- Verdict: **{verdict['label']}**",
        f"- Data mutation: **none**",
        "",
        "## Summary",
        "",
    ]
    lines.extend(
        markdown_table(
            ["Metric", "Count"],
            [
                ["Records", summary["records"]],
                ["Readable / referenced images", f"{summary['readable_images']} / {summary['referenced_images']}"],
                ["Missing / unreadable images", f"{summary['missing_images']} / {summary['unreadable_images']}"],
                ["Exact decision-text groups", summary["exact_decision_text_groups"]],
                ["Exact question-only groups", summary["exact_question_groups"]],
                ["Exact image SHA groups", summary["exact_image_groups"]],
                ["Must-fix exact leakage pairs", summary["must_fix_exact_leakage_pairs"]],
                ["Near-text review candidates (reported)", summary["near_text_candidates"]],
                ["Near-image review candidates (reported)", summary["near_image_candidates"]],
            ],
        )
    )
    lines.extend(["", "## Source inventory", ""])
    lines.extend(
        markdown_table(
            ["Source", "Records"],
            [[source, count] for source, count in report["source_counts"].items()],
        )
    )
    lines.extend(["", "## Must-fix exact leakage", ""])
    lines.append(verdict["explanation"])
    lines.append("")
    lines.extend(
        markdown_table(
            ["Left", "Left source", "Right", "Right source", "Basis"],
            [
                [
                    item["left"]["id"],
                    item["left"]["source"],
                    item["right"]["id"],
                    item["right"]["source"],
                    item["basis"],
                ]
                for item in report["must_fix_exact_leakage_pairs"][:100]
            ],
        )
    )
    lines.extend(["", "## Exact decision-text groups", ""])
    lines.extend(
        markdown_table(
            ["Sources", "Pair count", "Length", "Records", "Example"],
            [
                [
                    json.dumps(item["sources"], ensure_ascii=False),
                    item["cross_source_pair_count"],
                    item["normalized_length"],
                    ", ".join(record["id"] for record in item["records"][:8]),
                    item["example"][:180],
                ]
                for item in report["exact_text"]["decision_groups"][:50]
            ],
        )
    )
    lines.extend(["", "## Exact image SHA groups", ""])
    lines.extend(
        markdown_table(
            ["Sources", "Pair count", "Records", "SHA-256"],
            [
                [
                    json.dumps(item["sources"], ensure_ascii=False),
                    item["cross_source_pair_count"],
                    ", ".join(image["id"] for image in item["images"][:8]),
                    item["sha256"],
                ]
                for item in report["exact_images"]["groups"][:50]
            ],
        )
    )
    lines.extend(["", "## Priority near-text candidates", ""])
    priority_text = [item for item in report["near_text"]["candidates"] if item["focus_pair"]]
    lines.extend(
        markdown_table(
            ["Left", "Right", "Sources", "Full ratio", "Question ratio", "Text excerpts"],
            [
                [
                    item["left"]["id"],
                    item["right"]["id"],
                    item["source_pair"],
                    item["full_sequence_ratio"],
                    item["question_sequence_ratio"],
                    (item["left_text"][:70] + " ⇄ " + item["right_text"][:70]),
                ]
                for item in priority_text[:50]
            ],
        )
    )
    lines.extend(["", "## Priority near-image candidates", ""])
    priority_images = [item for item in report["near_images"]["candidates"] if item["focus_pair"]]
    lines.extend(
        markdown_table(
            ["Left", "Right", "Sources", "dHash", "pHash", "Paths"],
            [
                [
                    item["left"]["id"],
                    item["right"]["id"],
                    item["source_pair"],
                    item["dhash_hamming"],
                    item["phash_hamming"],
                    item["left_path"] + " ⇄ " + item["right_path"],
                ]
                for item in priority_images[:50]
            ],
        )
    )
    lines.extend(
        [
            "",
            "## Interpretation and limits",
            "",
            "- `decision-text exact` compares normalized context + question + an order-insensitive candidate set. Question-only exact groups are reported separately because generic templates are not sufficient evidence of leakage.",
            "- `image exact` uses file-byte SHA-256. `must-fix` is intentionally conservative: the same cross-source record pair must share both an exact decision-text signature and an exact image SHA.",
            "- Near text uses rare character-trigram and SimHash blocking, then SequenceMatcher and trigram Jaccard scoring. Each reported text candidate also includes the closest available image-hash evidence. Near images require pHash agreement (alone or jointly with dHash), so sparse-image dHash collisions are suppressed. These are candidate generators, not deletion rules.",
            "- Oversized perceptual-hash/text buckets are skipped to keep the 10k audit tractable; exact hashing is exhaustive for every readable image.",
            "- Missing media are listed in the JSON report. They reduce near/exact image coverage only for those paths; the underlying dataset is not modified.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="MM-JevBench 10k cross-source duplicate audit")
    parser.add_argument(
        "--data",
        type=Path,
        default=project_root / "datasets/processed/10k/mmjevbench_10k.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "reports/cross_source_dedup_10k.json",
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=project_root / "reports/cross_source_dedup_10k.md",
    )
    parser.add_argument("--text-ratio", type=float, default=0.90)
    parser.add_argument("--image-hamming", type=int, default=6)
    parser.add_argument("--max-near-candidates", type=int, default=2000)
    parser.add_argument("--max-text-bucket", type=int, default=300)
    parser.add_argument("--max-image-bucket", type=int, default=350)
    args = parser.parse_args()

    rows = list(read_jsonl(args.data))
    texts = [row_text(row) for row in rows]
    decision_keys = [item["decision"] for item in texts]
    question_keys = [item["question"] for item in texts]
    decision_groups = cross_source_groups(rows, decision_keys, texts, "decision")
    question_groups = cross_source_groups(rows, question_keys, texts, "question")
    exact_text_pairs = expand_group_pairs(decision_groups)

    near_text, near_text_stats = near_text_candidates(
        rows,
        texts,
        exact_text_pairs,
        args.text_ratio,
        args.max_near_candidates,
        args.max_text_bucket,
    )

    images, missing_images, unreadable_images = image_inventory(rows, project_root)
    enrich_text_candidates_with_image_evidence(near_text, images)
    image_groups = exact_image_groups(images)
    exact_image_pairs = expand_image_pairs(image_groups)
    near_images, near_image_stats = near_image_candidates(
        rows,
        images,
        exact_image_pairs,
        args.image_hamming,
        args.max_near_candidates,
        args.max_image_bucket,
    )

    rows_by_id = {str(row.get("id", "")): row for row in rows}
    must_fix_pairs = []
    for left_id, right_id in sorted(exact_text_pairs & exact_image_pairs):
        left = rows_by_id[left_id]
        right = rows_by_id[right_id]
        must_fix_pairs.append(
            {
                "left": record_ref(left),
                "right": record_ref(right),
                "source_pair": source_pair(left, right),
                "focus_pair": is_focus_pair(left, right),
                "basis": "exact normalized decision text + exact image SHA-256",
            }
        )

    source_counts = dict(sorted(Counter(source_name(row) for row in rows).items()))
    referenced_images = len(images) + len(missing_images) + len(unreadable_images)
    must_fix_found = bool(must_fix_pairs)
    report: dict[str, Any] = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "input": {
            "path": str(args.data.resolve()),
            "sha256": sha256_file(args.data),
        },
        "scope": {
            "cross_source_only": True,
            "focus_left": sorted(FOCUS_LEFT),
            "focus_right": sorted(FOCUS_RIGHT),
            "automatic_deletion": False,
        },
        "thresholds": {
            "near_text_sequence_ratio": args.text_ratio,
            "near_image_hash_hamming": args.image_hamming,
            "max_text_block_size": args.max_text_bucket,
            "max_image_block_size": args.max_image_bucket,
        },
        "source_counts": source_counts,
        "summary": {
            "records": len(rows),
            "referenced_images": referenced_images,
            "readable_images": len(images),
            "missing_images": len(missing_images),
            "unreadable_images": len(unreadable_images),
            "exact_decision_text_groups": len(decision_groups),
            "exact_question_groups": len(question_groups),
            "exact_image_groups": len(image_groups),
            "must_fix_exact_leakage_pairs": len(must_fix_pairs),
            "near_text_candidates": len(near_text),
            "near_image_candidates": len(near_images),
        },
        "verdict": {
            "must_fix_exact_leakage_found": must_fix_found,
            "label": "MUST-FIX EXACT LEAKAGE FOUND" if must_fix_found else "NO MUST-FIX EXACT LEAKAGE FOUND",
            "explanation": (
                "At least one cross-source pair has both identical normalized decision text and identical image bytes; group or exclude it before paper evaluation."
                if must_fix_found
                else "No cross-source pair simultaneously shares an exact normalized decision signature and exact image bytes. Text-only, image-only, and approximate matches remain review candidates and were not deleted."
            ),
        },
        "must_fix_exact_leakage_pairs": must_fix_pairs,
        "exact_text": {
            "decision_groups": decision_groups,
            "question_groups": question_groups,
            "decision_cross_source_pair_count": len(exact_text_pairs),
        },
        "exact_images": {
            "groups": image_groups,
            "cross_source_record_pair_count": len(exact_image_pairs),
        },
        "near_text": {
            "stats": near_text_stats,
            "counts_by_source_pair": pair_counts(near_text),
            "candidates": near_text,
        },
        "near_images": {
            "stats": near_image_stats,
            "counts_by_source_pair": pair_counts(near_images),
            "candidates": near_images,
        },
        "media_coverage": {
            "missing_by_source": dict(sorted(Counter(item["source"] for item in missing_images).items())),
            "unreadable_by_source": dict(sorted(Counter(item["source"] for item in unreadable_images).items())),
            "missing": missing_images,
            "unreadable": unreadable_images,
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"summary": report["summary"], "verdict": report["verdict"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

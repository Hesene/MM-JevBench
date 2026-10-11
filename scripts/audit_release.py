from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from collections import Counter, defaultdict
from pathlib import Path

from mmjevbench.io import read_jsonl, sha256_file, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("datasets/processed/10k/mmjevbench_10k.jsonl"))
    parser.add_argument("--report", type=Path, default=Path("reports/sampling_summary_10k.json"))
    parser.add_argument("--media-manifest", type=Path, default=Path("datasets/manifests/10k/release_media.jsonl"))
    parser.add_argument("--release", default="MM-JevBench-10k-v1.0")
    args = parser.parse_args()
    rows = list(read_jsonl(args.data))
    group_splits: dict[str, set[str]] = defaultdict(set)
    track_split_rows: dict[str, Counter] = defaultdict(Counter)
    track_split_groups: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for row in rows:
        group_splits[row["group_id"]].add(row["split"])
        track_split_rows[row["track"]][row["split"]] += 1
        track_split_groups[row["track"]][row["split"]].add(row["group_id"])
    leaking_groups = sorted(group_id for group_id, splits in group_splits.items() if len(splits) > 1)
    strata: dict[tuple[str, str], dict] = {}
    for row in rows:
        sampling = row["sampling"]
        key = (row["track"], sampling["stratum"])
        strata[key] = {
            "track": row["track"],
            "stratum": sampling["stratum"],
            "frame_size": sampling["frame_size"],
            "quota": sampling["quota"],
            "inclusion_probability": sampling["inclusion_probability"],
            "analysis_weight": sampling["analysis_weight"],
        }
    media_entries = []
    seen = set()
    for row in rows:
        for paths in row["state"]["media"].values():
            for relative in paths:
                if relative.startswith("private://") or relative in seen:
                    continue
                seen.add(relative)
                path = Path(relative)
                media_entries.append({
                    "path": relative,
                    "exists": path.exists(),
                    "bytes": path.stat().st_size if path.exists() else None,
                    "sha256": sha256_file(path) if path.exists() else None,
                })
    write_jsonl(args.media_manifest, media_entries)
    summary = {
        "release": args.release,
        "canonical": len(rows),
        "tracks": Counter(row["track"] for row in rows),
        "splits": Counter(row["split"] for row in rows),
        "groups": len({row["group_id"] for row in rows}),
        "group_split_audit": {
            "leaking_group_count": len(leaking_groups),
            "leaking_group_ids": leaking_groups,
            "by_track": {
                track: {
                    split: {
                        "rows": track_split_rows[track][split],
                        "groups": len(track_split_groups[track][split]),
                    }
                    for split in sorted(track_split_rows[track])
                }
                for track in sorted(track_split_rows)
            },
        },
        "strata": list(sorted(strata.values(), key=lambda item: (item["track"], item["stratum"]))),
        "media": {
            "referenced_unique": len(media_entries),
            "present": sum(entry["exists"] for entry in media_entries),
            "bytes": sum(entry["bytes"] or 0 for entry in media_entries),
            "manifest_sha256": sha256_file(args.media_manifest),
        },
        "data_sha256": sha256_file(args.data),
        "environment": {"python": sys.version, "platform": platform.platform()},
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "strata"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

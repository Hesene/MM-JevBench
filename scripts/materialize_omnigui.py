from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import time
from pathlib import Path

import requests

from mmjevbench.io import read_jsonl, write_jsonl

REVISION = "2c9031077541186f6fb1f2514cb62446c811ffd4"
BASE_URL = "https://huggingface.co/datasets/OmniGUI/OmniGUI/resolve/{revision}/benchmark/{path}"


def download_one(item: tuple[str, Path], retries: int = 4) -> dict:
    source_path, destination = item
    url = BASE_URL.format(revision=REVISION, path=source_path.replace("\\", "/"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        payload = destination.read_bytes()
        return {"source_path": source_path, "path": str(destination), "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), "status": "existing"}
    partial = destination.with_suffix(destination.suffix + ".partial")
    for attempt in range(retries):
        try:
            digest = hashlib.sha256()
            size = 0
            with requests.get(url, stream=True, timeout=(30, 180), headers={"User-Agent": "MM-JevBench/0.1"}) as response:
                response.raise_for_status()
                with partial.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            handle.write(chunk)
                            digest.update(chunk)
                            size += len(chunk)
            partial.replace(destination)
            return {"source_path": source_path, "path": str(destination), "bytes": size, "sha256": digest.hexdigest(), "status": "downloaded"}
        except Exception as exc:  # noqa: BLE001 - retry and return structured failure
            if partial.exists():
                partial.unlink()
            if attempt + 1 == retries:
                return {"source_path": source_path, "path": str(destination), "status": "failed", "error": repr(exc)}
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def main() -> int:
    parser = argparse.ArgumentParser(description="Download only the OmniGUI assets selected by the frozen manifest")
    parser.add_argument("--data", type=Path, default=Path("datasets/processed/omnigui.jsonl"))
    parser.add_argument("--media-root", type=Path, default=Path("datasets/media/omnigui"))
    parser.add_argument("--manifest", type=Path, default=Path("datasets/manifests/omnigui_media.jsonl"))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--modalities", nargs="+", default=["image", "audio", "video"])
    args = parser.parse_args()

    wanted: dict[str, Path] = {}
    for row in read_jsonl(args.data):
        source = row.get("metadata", {}).get("source_media", {})
        for modality in args.modalities:
            path = source.get(modality)
            if path:
                wanted[path] = args.media_root / Path(path)
    items = sorted(wanted.items())
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(download_one, items))
    write_jsonl(args.manifest, results)
    failures = [result for result in results if result["status"] == "failed"]
    print(json.dumps({"requested": len(results), "failed": len(failures), "bytes": sum(result.get("bytes", 0) for result in results)}, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())


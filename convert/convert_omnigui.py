from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from mmjevbench.io import stable_digest, write_jsonl
from mmjevbench.records import make_choice_record
from mmjevbench.sampling import assign_dev_test, square_root_allocate, stable_priority, stratified_hash_sample

SOURCE_VERSION = "OmniGUI/OmniGUI@2c9031077541186f6fb1f2514cb62446c811ffd4"
ACTION_SPACE = [
    (-1, "等待或观察，不执行界面操作"),
    (0, "点击一次（TAP）"),
    (1, "双击（DOUBLE_TAP）"),
    (2, "长按（LONG_PRESS）"),
    (3, "向上滑动（SWIPE_UP）"),
    (4, "向下滑动（SWIPE_DOWN）"),
    (5, "向左滑动（SWIPE_LEFT）"),
    (6, "向右滑动（SWIPE_RIGHT）"),
    (7, "输入文本（INPUT）"),
    (8, "返回（BACK）"),
    (9, "回到主页（HOME）"),
    (10, "任务已完成（TASK_COMPLETE）"),
    (11, "任务无法完成（TASK_IMPOSSIBLE）"),
]


def _media_ref(kind: str, path: str) -> list[str]:
    return [f"datasets/media/omnigui/{path}"] if path else []


def load_episode_candidates(input_path: Path, seed: str, all_steps: bool = False) -> list[dict]:
    raw_rows = json.loads(input_path.read_text(encoding="utf-8"))
    episodes: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for raw in raw_rows:
        if int(raw.get("result_action_type", -999)) not in {value for value, _ in ACTION_SPACE}:
            continue
        episodes[(str(raw.get("app")), str(raw.get("episode_id")))].append(raw)

    records: list[dict] = []
    for (app, episode_id), steps in episodes.items():
        selected_steps = sorted(steps, key=lambda row: int(row.get("step_index", 0))) if all_steps else [
            min(
                steps,
                key=lambda row: stable_digest(seed, "omnigui-step", app, episode_id, row.get("step_index")),
            )
        ]
        for chosen in selected_steps:
            action = int(chosen["result_action_type"])
            label_index = [value for value, _ in ACTION_SPACE].index(action)
            image_path = str(chosen.get("image_path") or "")
            audio_path = str(chosen.get("audio_path") or "")
            video_path = str(chosen.get("video_path") or "")
            source_id = f"{app}:{episode_id}:{chosen.get('step_index')}"
            record = make_choice_record(
                record_id=f"mmjev_omnigui_{stable_digest(source_id)[:20]}",
                track="gui_action_type",
                domain="gui_agent",
                source_dataset="OmniGUI",
                source_id=source_id,
                source_version=SOURCE_VERSION,
                context=str(chosen.get("instruction") or ""),
                question="根据当前多模态状态和历史动作，下一步应选择哪一种动作类型？",
                options=[text for _, text in ACTION_SPACE],
                label_index=label_index,
                media={
                    "image": _media_ref("image", image_path),
                    "audio": _media_ref("audio", audio_path),
                    "video": _media_ref("video", video_path),
                },
                history=chosen.get("action_history") or [],
                group_id=f"omnigui_episode_{stable_digest(app, episode_id)[:24]}",
                metadata={
                    "app": app,
                    "episode_id": episode_id,
                    "step_index": int(chosen.get("step_index", 0)),
                    "cognitive_dimension": str(chosen.get("task_category_full") or "unknown"),
                    "action_code": action,
                    "gold_action": chosen.get("target_action") or json.loads(chosen.get("result_action_json") or "{}"),
                    "screen_width": chosen.get("image_width"),
                    "screen_height": chosen.get("image_height"),
                    "source_media": {"image": image_path, "audio": audio_path, "video": video_path},
                    "derived_task_notice": "Closed-world action-type Choice; report official open-action metrics separately.",
                },
            )
            for candidate, (value, _) in zip(record["candidates"], ACTION_SPACE):
                candidate["value"] = value
            records.append(record)
    return records


def build(input_path: Path, output: Path, target: int, seed: str, all_steps: bool = False) -> list[dict]:
    eligible = load_episode_candidates(input_path, seed, all_steps)
    key = lambda row: (row["metadata"]["cognitive_dimension"], row["metadata"]["app"])
    capacities: dict[tuple, int] = defaultdict(int)
    for row in eligible:
        capacities[key(row)] += 1
    quotas = square_root_allocate(dict(capacities), target, minimum=1)
    selected = stratified_hash_sample(eligible, quotas, key, seed)
    selected = assign_dev_test(selected, seed, 0.2, lambda row: row["metadata"]["cognitive_dimension"])
    write_jsonl(output, sorted(selected, key=lambda row: row["id"]))
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert one deterministic step per OmniGUI episode")
    parser.add_argument("--input", type=Path, required=True, help="merged_sorted.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", type=int, default=500)
    parser.add_argument("--seed", default="MM-JevBench-mini-v1.0")
    parser.add_argument("--all-steps", action="store_true", help="Retain all valid steps; split remains episode-grouped")
    args = parser.parse_args()
    rows = build(args.input, args.output, args.target, args.seed, args.all_steps)
    print(f"wrote {len(rows)} OmniGUI episode-level records to {args.output}")


if __name__ == "__main__":
    main()


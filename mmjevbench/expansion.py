from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from .io import stable_digest

Row = dict[str, Any]


def _exact_group_subset(
    groups: Sequence[tuple[str, list[Row]]],
    target_rows: int,
    seed: str,
    track: str,
) -> set[str]:
    """Choose whole groups whose record counts sum exactly to ``target_rows``."""
    if target_rows < 0 or target_rows > sum(len(members) for _, members in groups):
        raise ValueError(f"{track}: impossible grouped dev target {target_rows}")
    if target_rows == 0:
        return set()
    ordered = sorted(
        groups,
        key=lambda item: stable_digest(
            seed,
            "expanded-group-split",
            track,
            item[1][0].get("sampling", {}).get("stratum", "unstratified"),
            item[0],
        ),
    )
    parents: list[tuple[int, int] | None] = [None] * (target_rows + 1)
    parents[0] = (-1, -1)
    for index, (_, members) in enumerate(ordered):
        size = len(members)
        for total in range(target_rows, size - 1, -1):
            if parents[total] is None and parents[total - size] is not None:
                parents[total] = (total - size, index)
    if parents[target_rows] is None:
        raise ValueError(f"{track}: no exact group-preserving split reaches {target_rows} rows")
    selected: set[str] = set()
    cursor = target_rows
    while cursor:
        parent = parents[cursor]
        if parent is None:
            raise AssertionError("broken subset reconstruction")
        cursor, index = parent
        selected.add(ordered[index][0])
    return selected


def assign_splits_preserving_anchor(
    rows: Sequence[Row],
    anchor_rows: Iterable[Row],
    dev_targets: Mapping[str, int],
    seed: str,
) -> list[Row]:
    """Assign exact track-level dev counts while freezing anchor group splits.

    Existing mini IDs retain their original split. Every additional record
    sharing an anchor group inherits that split. Remaining groups are selected
    with a deterministic exact subset-sum so an episode, problem, or media
    group can never cross dev/test.
    """
    ids = [str(row["id"]) for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate record IDs in expanded release")

    anchor = {str(row["id"]): row for row in anchor_rows}
    missing = sorted(set(anchor).difference(ids))
    if missing:
        raise ValueError(f"expanded release is missing {len(missing)} anchor IDs")
    invalid_anchor = [record_id for record_id, row in anchor.items() if row.get("split") not in {"dev", "test"}]
    if invalid_anchor:
        raise ValueError("all anchor rows must have dev/test splits")

    anchor_group_split: dict[str, str] = {}
    for row in anchor.values():
        group_id = str(row["group_id"])
        split = str(row["split"])
        previous = anchor_group_split.setdefault(group_id, split)
        if previous != split:
            raise ValueError(f"anchor group {group_id} already crosses splits")

    by_track: dict[str, list[Row]] = defaultdict(list)
    for row in rows:
        by_track[str(row["track"])].append(row)
    unknown = sorted(set(by_track).difference(dev_targets))
    if unknown:
        raise ValueError(f"missing dev targets for tracks: {unknown}")

    output: list[Row] = []
    for track, track_rows in sorted(by_track.items()):
        target_dev = int(dev_targets[track])
        grouped: dict[str, list[Row]] = defaultdict(list)
        for row in track_rows:
            grouped[str(row["group_id"])].append(row)

        fixed_dev = sum(
            len(members)
            for group_id, members in grouped.items()
            if anchor_group_split.get(group_id) == "dev"
        )
        unresolved = [
            (group_id, members)
            for group_id, members in grouped.items()
            if group_id not in anchor_group_split
        ]
        extra_dev = target_dev - fixed_dev
        if extra_dev < 0:
            raise ValueError(f"anchor dev groups already exceed dev target for {track}")
        new_dev_groups = _exact_group_subset(unresolved, extra_dev, seed, track)

        for row in track_rows:
            group_id = str(row["group_id"])
            copy = dict(row)
            copy["split"] = anchor_group_split.get(
                group_id,
                "dev" if group_id in new_dev_groups else "test",
            )
            output.append(copy)

        observed = sum(row["split"] == "dev" for row in output if row["track"] == track)
        if observed != target_dev:
            raise AssertionError(f"{track}: expected {target_dev} dev rows, observed {observed}")

    return sorted(output, key=lambda row: str(row["id"]))

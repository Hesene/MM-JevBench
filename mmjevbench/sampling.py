from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Callable, Hashable, Iterable, Sequence

from .io import stable_digest

Row = dict[str, Any]


def stable_priority(row: Row, seed: str, namespace: str = "sample") -> str:
    return stable_digest(
        seed,
        namespace,
        row.get("source", {}).get("dataset", row.get("source_dataset", "")),
        row.get("source", {}).get("source_id", row.get("source_id", "")),
        row.get("group_id", ""),
    )


def capped_allocate(
    capacities: dict[Hashable, int],
    total: int,
    weights: dict[Hashable, float] | None = None,
    minimum: int = 0,
) -> dict[Hashable, int]:
    """Deterministic capped largest-remainder allocation.

    Every non-empty cell receives up to ``minimum`` first. Remaining units are
    distributed in proportion to ``weights`` (default: equal), never above the
    observed cell capacity. Ties use the string form of the cell key.
    """
    if total < 0 or any(value < 0 for value in capacities.values()):
        raise ValueError("total and capacities must be non-negative")
    if total > sum(capacities.values()):
        raise ValueError("requested sample exceeds eligible capacity")
    keys = sorted((key for key, size in capacities.items() if size > 0), key=str)
    allocation = {key: min(minimum, capacities[key]) for key in keys}
    remaining = total - sum(allocation.values())
    if remaining < 0:
        allocation = {key: 0 for key in keys}
        remaining = total
    weights = weights or {key: 1.0 for key in keys}

    while remaining:
        open_keys = [key for key in keys if allocation[key] < capacities[key]]
        if not open_keys:
            break
        denom = sum(max(0.0, float(weights.get(key, 0.0))) for key in open_keys)
        if denom <= 0:
            raw = {key: remaining / len(open_keys) for key in open_keys}
        else:
            raw = {key: remaining * max(0.0, float(weights.get(key, 0.0))) / denom for key in open_keys}
        floor_add = {
            key: min(capacities[key] - allocation[key], int(math.floor(raw[key])))
            for key in open_keys
        }
        added = sum(floor_add.values())
        for key, value in floor_add.items():
            allocation[key] += value
        remaining -= added
        if not remaining:
            break
        ranked = sorted(
            (key for key in open_keys if allocation[key] < capacities[key]),
            key=lambda key: (-(raw[key] - math.floor(raw[key])), str(key)),
        )
        if not ranked:
            continue
        for key in ranked[:remaining]:
            allocation[key] += 1
        remaining -= min(remaining, len(ranked))
    return allocation


def square_root_allocate(
    capacities: dict[Hashable, int], total: int, minimum: int = 0
) -> dict[Hashable, int]:
    return capped_allocate(
        capacities,
        total,
        weights={key: math.sqrt(size) for key, size in capacities.items()},
        minimum=minimum,
    )


def stratified_hash_sample(
    rows: Sequence[Row],
    quotas: dict[Hashable, int],
    stratum: Callable[[Row], Hashable],
    seed: str,
) -> list[Row]:
    cells: dict[Hashable, list[Row]] = defaultdict(list)
    for row in rows:
        cells[stratum(row)].append(row)
    selected: list[Row] = []
    for key in sorted(quotas, key=str):
        ordered = sorted(cells.get(key, []), key=lambda row: stable_priority(row, seed, f"stratum:{key}"))
        quota = quotas[key]
        if quota > len(ordered):
            raise ValueError(f"quota {quota} exceeds cell {key!r} capacity {len(ordered)}")
        for row in ordered[:quota]:
            copy = dict(row)
            copy["sampling"] = {
                **copy.get("sampling", {}),
                "stratum": str(key),
                "frame_size": len(ordered),
                "quota": quota,
                "inclusion_probability": quota / len(ordered),
                "analysis_weight": len(ordered) / quota,
                "priority": stable_priority(row, seed, f"stratum:{key}"),
            }
            selected.append(copy)
    return sorted(selected, key=lambda row: stable_priority(row, seed, "release-order"))


def assign_dev_test(
    rows: Sequence[Row],
    seed: str,
    dev_fraction: float = 0.2,
    stratum: Callable[[Row], Hashable] | None = None,
) -> list[Row]:
    if not 0 <= dev_fraction <= 1:
        raise ValueError("dev_fraction must be between zero and one")
    stratum = stratum or (lambda row: row.get("track", "all"))
    groups: dict[str, list[Row]] = defaultdict(list)
    for row in rows:
        groups[str(row["group_id"])].append(row)
    grouped_cells: dict[Hashable, list[tuple[str, list[Row]]]] = defaultdict(list)
    for group_id, members in groups.items():
        grouped_cells[stratum(members[0])].append((group_id, members))

    total_groups = sum(len(items) for items in grouped_cells.values())
    requested_dev = round(total_groups * dev_fraction)
    cell_capacities = {cell: len(items) for cell, items in grouped_cells.items()}
    dev_quotas = capped_allocate(
        cell_capacities,
        requested_dev,
        weights={cell: len(items) for cell, items in grouped_cells.items()},
    )
    output: list[Row] = []
    for cell, items in grouped_cells.items():
        items.sort(key=lambda item: stable_digest(seed, "split", cell, item[0]))
        dev_groups = dev_quotas[cell]
        for index, (_, members) in enumerate(items):
            split = "dev" if index < dev_groups else "test"
            for row in members:
                copy = dict(row)
                copy["split"] = split
                output.append(copy)
    return output


def deduplicate_by_group(rows: Iterable[Row], seed: str) -> list[Row]:
    best: dict[str, Row] = {}
    for row in rows:
        group = str(row["group_id"])
        if group not in best or stable_priority(row, seed, "group-dedup") < stable_priority(best[group], seed, "group-dedup"):
            best[group] = row
    return list(best.values())


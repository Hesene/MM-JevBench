from __future__ import annotations

import copy
import random
from itertools import combinations
from typing import Any, Iterable

from .io import stable_digest


def _rng(seed: str, record_id: str, operation: str) -> random.Random:
    return random.Random(int(stable_digest(seed, record_id, operation)[:16], 16))


def _rekey(record: dict[str, Any]) -> None:
    for index, candidate in enumerate(record["candidates"]):
        candidate["key"] = chr(ord("A") + index) if index < 26 else str(index)
    index = record["gold"]["label_index"]
    record["gold"]["label_key"] = record["candidates"][index]["key"]


def candidate_permutations(record: dict[str, Any], count: int, seed: str) -> tuple[list[dict], list[dict]]:
    size = len(record["candidates"])
    if size < 2:
        return [], []
    rng = _rng(seed, record["id"], "REP")
    identity = tuple(range(size))
    possible = min(count, max(1, 10_000 if size > 8 else _factorial(size) - 1))
    mappings: set[tuple[int, ...]] = set()
    attempts = 0
    while len(mappings) < possible and attempts < 10_000:
        mapping = list(identity)
        rng.shuffle(mapping)
        if tuple(mapping) != identity:
            mappings.add(tuple(mapping))
        attempts += 1
    variants: list[dict] = []
    relations: list[dict] = []
    for number, new_to_reference in enumerate(sorted(mappings), start=1):
        variant = copy.deepcopy(record)
        variant["id"] = f"{record['id']}__rep_perm{number}"
        old_candidates = record["candidates"]
        old_distribution = record["gold"]["outcome_distribution"]
        variant["candidates"] = [copy.deepcopy(old_candidates[index]) for index in new_to_reference]
        variant["gold"]["outcome_distribution"] = [old_distribution[index] for index in new_to_reference]
        variant["gold"]["label_index"] = new_to_reference.index(record["gold"]["label_index"])
        variant["gold"]["provenance"] = "derived"
        _rekey(variant)
        variant["metadata"]["coherence_parent_id"] = record["id"]
        variants.append(variant)
        relations.append({
            "relation_id": f"rel_rep_{record['id']}_{number}",
            "family": "REP",
            "reference_id": record["id"],
            "variant_ids": [variant["id"]],
            "expectation": {"type": "permutation_equivariance", "new_to_reference": list(new_to_reference)},
            "split": record["split"],
            "group_id": record["group_id"],
        })
    return variants, relations


def _factorial(value: int) -> int:
    result = 1
    for number in range(2, value + 1):
        result *= number
    return result


def submenu_variant(record: dict[str, Any], seed: str) -> tuple[dict, dict] | None:
    gold = record["gold"]["label_index"]
    removable = [index for index in range(len(record["candidates"])) if index != gold]
    if not removable or len(record["candidates"]) < 3:
        return None
    removed = _rng(seed, record["id"], "CHO").choice(removable)
    retained = [index for index in range(len(record["candidates"])) if index != removed]
    variant = copy.deepcopy(record)
    variant["id"] = f"{record['id']}__cho_submenu"
    variant["candidates"] = [copy.deepcopy(record["candidates"][index]) for index in retained]
    variant["gold"]["label_index"] = retained.index(gold)
    distribution = [record["gold"]["outcome_distribution"][index] for index in retained]
    total = sum(distribution)
    variant["gold"]["outcome_distribution"] = [value / total for value in distribution]
    variant["gold"]["provenance"] = "derived"
    _rekey(variant)
    variant["metadata"]["coherence_parent_id"] = record["id"]
    relation = {
        "relation_id": f"rel_cho_{record['id']}",
        "family": "CHO",
        "reference_id": record["id"],
        "variant_ids": [variant["id"]],
        "expectation": {"type": "conditional_choice_consistency", "submenu_indices": retained},
        "split": record["split"],
        "group_id": record["group_id"],
    }
    return variant, relation


def merge_variant(record: dict[str, Any], seed: str) -> tuple[dict, dict] | None:
    if len(record["candidates"]) < 3:
        return None
    rng = _rng(seed, record["id"], "MEA-merge")
    pair = tuple(sorted(rng.choice(list(combinations(range(len(record["candidates"])), 2)))))
    groups: list[list[int]] = [list(pair)] + [[index] for index in range(len(record["candidates"])) if index not in pair]
    variant = copy.deepcopy(record)
    variant["id"] = f"{record['id']}__mea_merge"
    merged_candidates = []
    merged_distribution = []
    old_distribution = record["gold"]["outcome_distribution"]
    for group in groups:
        if len(group) == 1:
            merged_candidates.append(copy.deepcopy(record["candidates"][group[0]]))
        else:
            texts = [record["candidates"][index]["text"] for index in group]
            merged_candidates.append({"key": "", "text": " 或 ".join(f"（{text}）" for text in texts), "value": {"merged_indices": group}})
        merged_distribution.append(sum(old_distribution[index] for index in group))
    old_gold = record["gold"]["label_index"]
    new_gold = next(index for index, group in enumerate(groups) if old_gold in group)
    variant["candidates"] = merged_candidates
    variant["gold"]["label_index"] = new_gold
    variant["gold"]["outcome_distribution"] = merged_distribution
    variant["gold"]["provenance"] = "derived"
    _rekey(variant)
    variant["metadata"]["coherence_parent_id"] = record["id"]
    relation = {
        "relation_id": f"rel_mea_merge_{record['id']}",
        "family": "MEA",
        "reference_id": record["id"],
        "variant_ids": [variant["id"]],
        "expectation": {"type": "finite_additivity", "groups": groups},
        "split": record["split"],
        "group_id": record["group_id"],
    }
    return variant, relation


def proposition_variants(record: dict[str, Any], seed: str) -> tuple[list[dict], list[dict]]:
    index = _rng(seed, record["id"], "noul-event").randrange(len(record["candidates"]))
    other = next(item for item in range(len(record["candidates"])) if item != index)
    base = copy.deepcopy(record)
    base["task_type"] = "noul"
    base["candidates"] = [
        {"key": "no", "text": "否", "value": False},
        {"key": "yes", "text": "是", "value": True},
    ]
    is_true = record["gold"]["label_index"] == index
    base["gold"] = {
        "label_index": 1 if is_true else 0,
        "label_key": "yes" if is_true else "no",
        "outcome_distribution": [0.0, 1.0] if is_true else [1.0, 0.0],
        "provenance": "derived",
    }
    text = record["candidates"][index]["text"]
    base["state"]["question"] = f"请判断以下命题是否成立：正确决策是“{text}”。"
    base["id"] = f"{record['id']}__mea_prop"
    base["metadata"]["coherence_parent_id"] = record["id"]

    negated = copy.deepcopy(base)
    negated["id"] = f"{record['id']}__mea_neg"
    negated["state"]["question"] = f"请判断以下命题是否成立：正确决策不是“{text}”。"
    negated["gold"]["label_index"] = 1 - base["gold"]["label_index"]
    negated["gold"]["label_key"] = "yes" if negated["gold"]["label_index"] else "no"
    negated["gold"]["outcome_distribution"] = list(reversed(base["gold"]["outcome_distribution"]))

    broad = copy.deepcopy(base)
    broad["id"] = f"{record['id']}__log_union"
    other_text = record["candidates"][other]["text"]
    broad["state"]["question"] = f"请判断以下命题是否成立：正确决策是“{text}”或“{other_text}”。"
    broad_true = record["gold"]["label_index"] in {index, other}
    broad["gold"]["label_index"] = 1 if broad_true else 0
    broad["gold"]["label_key"] = "yes" if broad_true else "no"
    broad["gold"]["outcome_distribution"] = [0.0, 1.0] if broad_true else [1.0, 0.0]

    relations = [
        {
            "relation_id": f"rel_mea_neg_{record['id']}",
            "family": "MEA",
            "reference_id": base["id"],
            "variant_ids": [negated["id"]],
            "expectation": {"type": "noul_complement", "candidate_order": ["no", "yes"]},
            "split": record["split"],
            "group_id": record["group_id"],
        },
        {
            "relation_id": f"rel_log_{record['id']}",
            "family": "LOG",
            "reference_id": base["id"],
            "variant_ids": [broad["id"]],
            "expectation": {"type": "logical_monotonicity", "narrow_event": [index], "broad_event": [index, other]},
            "split": record["split"],
            "group_id": record["group_id"],
        },
    ]
    return [base, negated, broad], relations


def batch_relations(records: list[dict[str, Any]], seed: str, batch_size: int = 8) -> list[dict]:
    ordered = sorted(records, key=lambda row: stable_digest(seed, "BAT", row["id"]))
    relations = []
    for batch_number, start in enumerate(range(0, len(ordered), batch_size)):
        chunk = ordered[start : start + batch_size]
        if len(chunk) < 2:
            continue
        ids = [row["id"] for row in chunk]
        relations.append({
            "relation_id": f"rel_bat_{batch_number:05d}",
            "family": "BAT",
            "reference_ids": ids,
            "variant_ids": [],
            "expectation": {
                "type": "batch_independence",
                "orders": [ids, list(reversed(ids)), ids[1:] + ids[:1]],
                "score_per_reference": True,
            },
            "split": chunk[0]["split"],
            "group_ids": [row["group_id"] for row in chunk],
        })
    return relations


def generate_coherence_suite(
    records: Iterable[dict[str, Any]], seed: str, permutations_per_case: int = 3
) -> tuple[list[dict], list[dict]]:
    canonical = [row for row in records if row.get("split") == "test"]
    variants: list[dict] = []
    relations: list[dict] = []
    for record in canonical:
        changed, linked = candidate_permutations(record, permutations_per_case, seed)
        variants.extend(changed)
        relations.extend(linked)
        result = submenu_variant(record, seed)
        if result:
            variants.append(result[0])
            relations.append(result[1])
        result = merge_variant(record, seed)
        if result:
            variants.append(result[0])
            relations.append(result[1])
        changed, linked = proposition_variants(record, seed)
        variants.extend(changed)
        relations.extend(linked)
    relations.extend(batch_relations(canonical, seed))
    return variants, relations


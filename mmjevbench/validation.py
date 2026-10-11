from __future__ import annotations

import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import jsonschema

from .io import read_jsonl


def semantic_errors(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    candidates = row.get("candidates", [])
    gold = row.get("gold", {})
    index = gold.get("label_index")
    probabilities = gold.get("outcome_distribution", [])
    if len(probabilities) != len(candidates):
        errors.append("gold distribution length differs from candidate count")
    if probabilities and (not all(math.isfinite(float(p)) and 0 <= float(p) <= 1 for p in probabilities) or abs(sum(probabilities) - 1) > 1e-6):
        errors.append("gold distribution is not a finite simplex")
    if not isinstance(index, int) or not 0 <= index < len(candidates):
        errors.append("gold label index is out of bounds")
    elif candidates[index].get("key") != gold.get("label_key"):
        errors.append("gold label key does not match candidate at label_index")
    keys = [candidate.get("key") for candidate in candidates]
    if len(keys) != len(set(keys)):
        errors.append("candidate keys are not unique")
    media = row.get("state", {}).get("media", {})
    declared = set(row.get("modalities", []))
    for modality in ("image", "audio", "video"):
        if media.get(modality) and modality not in declared:
            errors.append(f"media includes {modality} but modalities does not")
    return errors


def validate_rows(rows: Iterable[dict[str, Any]], schema_path: str | Path) -> dict[str, Any]:
    import json

    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    issues: list[dict[str, Any]] = []
    ids: Counter[str] = Counter()
    group_splits: dict[str, set[str]] = defaultdict(set)
    count = 0
    for row in rows:
        count += 1
        ids[str(row.get("id", ""))] += 1
        if row.get("group_id"):
            group_splits[str(row["group_id"])].add(str(row.get("split")))
        for error in validator.iter_errors(row):
            issues.append({"id": row.get("id"), "type": "schema", "message": error.message})
        for message in semantic_errors(row):
            issues.append({"id": row.get("id"), "type": "semantic", "message": message})
    for record_id, frequency in ids.items():
        if frequency != 1:
            issues.append({"id": record_id, "type": "duplicate_id", "message": f"seen {frequency} times"})
    for group_id, splits in group_splits.items():
        actual = splits - {"unassigned"}
        if len(actual) > 1:
            issues.append({"id": group_id, "type": "split_leakage", "message": f"group appears in {sorted(actual)}"})
    return {"records": count, "valid": not issues, "issue_count": len(issues), "issues": issues}


def validate_jsonl(path: str | Path, schema_path: str | Path) -> dict[str, Any]:
    return validate_rows(read_jsonl(path), schema_path)


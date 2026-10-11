from __future__ import annotations

from typing import Any, Sequence

from .io import stable_digest


def make_choice_record(
    *,
    record_id: str,
    track: str,
    domain: str,
    source_dataset: str,
    source_id: str,
    source_version: str,
    question: str,
    options: Sequence[str],
    label_index: int,
    media: dict[str, Any],
    context: str = "",
    history: Sequence[Any] | None = None,
    group_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if len(options) < 2:
        raise ValueError("choice records require at least two candidates")
    if not 0 <= label_index < len(options):
        raise ValueError("label_index is out of bounds")
    keys = [chr(ord("A") + index) for index in range(len(options))]
    distribution = [0.0] * len(options)
    distribution[label_index] = 1.0
    modalities = [name for name, value in media.items() if value]
    if question or context or history:
        modalities.append("text")
    return {
        "id": record_id,
        "schema_version": "1.0.0",
        "track": track,
        "task_type": "choice",
        "domain": domain,
        "language": "zh-CN",
        "modalities": sorted(set(modalities)),
        "state": {
            "context": context,
            "question": question,
            "media": media,
            "history": list(history or []),
        },
        "candidates": [
            {"key": key, "text": str(text), "value": None}
            for key, text in zip(keys, options)
        ],
        "gold": {
            "label_index": label_index,
            "label_key": keys[label_index],
            "outcome_distribution": distribution,
            "provenance": "source_gold",
        },
        "group_id": group_id or f"grp_{stable_digest(source_dataset, source_id)[:20]}",
        "split": "unassigned",
        "source": {
            "dataset": source_dataset,
            "source_id": str(source_id),
            "version": source_version,
        },
        "sampling": {},
        "annotations": {
            "modality_dependency": "unreviewed",
            "review_status": "unreviewed",
        },
        "metadata": metadata or {},
    }


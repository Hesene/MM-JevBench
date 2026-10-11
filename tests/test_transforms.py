from mmjevbench.records import make_choice_record
from mmjevbench.transforms import generate_coherence_suite


def _record():
    row = make_choice_record(
        record_id="case",
        track="academic_cmmmu",
        domain="science",
        source_dataset="x",
        source_id="1",
        source_version="v",
        question="q",
        options=["a", "b", "c", "d"],
        label_index=2,
        media={"image": ["x.png"], "audio": [], "video": []},
    )
    row["split"] = "test"
    return row


def test_suite_is_deterministic_and_preserves_groups():
    left = generate_coherence_suite([_record()], "seed", 3)
    right = generate_coherence_suite([_record()], "seed", 3)
    assert left == right
    variants, relations = left
    assert all(row["group_id"] == _record()["group_id"] for row in variants)
    assert {row["family"] for row in relations} >= {"REP", "MEA", "LOG", "CHO"}


def test_permutation_gold_stays_aligned():
    variants, relations = generate_coherence_suite([_record()], "seed", 3)
    for relation in (row for row in relations if row["family"] == "REP"):
        variant = next(row for row in variants if row["id"] == relation["variant_ids"][0])
        assert variant["gold"]["outcome_distribution"][variant["gold"]["label_index"]] == 1.0

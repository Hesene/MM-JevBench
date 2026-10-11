from mmjevbench.records import make_choice_record
from mmjevbench.validation import semantic_errors


def test_record_semantics_accept_well_formed_choice():
    row = make_choice_record(
        record_id="x",
        track="academic_cmmmu",
        domain="science",
        source_dataset="CMMMU",
        source_id="1",
        source_version="v",
        question="Q?",
        options=["a", "b"],
        label_index=1,
        media={"image": ["x.png"], "audio": [], "video": []},
    )
    assert semantic_errors(row) == []


def test_record_semantics_catches_misaligned_label():
    row = make_choice_record(
        record_id="x",
        track="academic_cmmmu",
        domain="science",
        source_dataset="CMMMU",
        source_id="1",
        source_version="v",
        question="Q?",
        options=["a", "b"],
        label_index=1,
        media={"image": ["x.png"], "audio": [], "video": []},
    )
    row["gold"]["label_key"] = "A"
    assert semantic_errors(row)

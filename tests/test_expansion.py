from mmjevbench.expansion import assign_splits_preserving_anchor


def _row(index: int, track: str = "track", stratum: str = "a") -> dict:
    return {
        "id": f"r{index}",
        "group_id": f"g{index}",
        "track": track,
        "split": "test",
        "sampling": {"stratum": stratum},
    }


def test_expansion_preserves_anchor_and_hits_exact_dev_target() -> None:
    rows = [_row(index, stratum="a" if index < 6 else "b") for index in range(10)]
    anchor = [dict(rows[0], split="dev"), dict(rows[1], split="test")]
    result = assign_splits_preserving_anchor(rows, anchor, {"track": 3}, "seed")
    by_id = {row["id"]: row for row in result}
    assert by_id["r0"]["split"] == "dev"
    assert by_id["r1"]["split"] == "test"
    assert sum(row["split"] == "dev" for row in result) == 3


def test_expansion_rejects_missing_anchor() -> None:
    rows = [_row(0)]
    anchor = [_row(1)]
    try:
        assign_splits_preserving_anchor(rows, anchor, {"track": 1}, "seed")
    except ValueError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("missing anchor must fail")


def test_expansion_keeps_new_sibling_with_anchor_group() -> None:
    rows = [_row(index) for index in range(5)]
    rows[1]["group_id"] = rows[0]["group_id"]
    anchor = [dict(rows[0], split="dev")]
    result = assign_splits_preserving_anchor(rows, anchor, {"track": 2}, "seed")
    by_id = {row["id"]: row for row in result}
    assert by_id["r0"]["split"] == "dev"
    assert by_id["r1"]["split"] == "dev"
    assert sum(row["split"] == "dev" for row in result) == 2

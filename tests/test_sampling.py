from mmjevbench.sampling import assign_dev_test, capped_allocate, stratified_hash_sample


def test_capped_allocation_respects_capacity_and_total():
    result = capped_allocate({"a": 2, "b": 100, "c": 100}, 20, minimum=3)
    assert sum(result.values()) == 20
    assert result["a"] == 2
    assert all(result[key] <= cap for key, cap in {"a": 2, "b": 100, "c": 100}.items())


def test_hash_sample_is_input_order_independent():
    rows = [
        {"id": str(i), "group_id": str(i), "source_id": str(i), "source_dataset": "x", "cell": i % 2}
        for i in range(20)
    ]
    quotas = {0: 3, 1: 3}
    left = stratified_hash_sample(rows, quotas, lambda row: row["cell"], "seed")
    right = stratified_hash_sample(list(reversed(rows)), quotas, lambda row: row["cell"], "seed")
    assert [row["id"] for row in left] == [row["id"] for row in right]


def test_group_aware_split_never_leaks():
    rows = [
        {"id": f"{group}-{i}", "group_id": group, "track": "x"}
        for group in ("a", "b", "c", "d", "e")
        for i in range(2)
    ]
    split = assign_dev_test(rows, "seed", dev_fraction=0.4)
    observed = {}
    for row in split:
        observed.setdefault(row["group_id"], set()).add(row["split"])
    assert all(len(value) == 1 for value in observed.values())


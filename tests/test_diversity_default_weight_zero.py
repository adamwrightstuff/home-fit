import main


def test_default_allocation_gives_diversity_zero_and_sums_to_100():
    alloc = main.parse_token_allocation(None)
    assert alloc["diversity"] == 0.0
    assert abs(sum(alloc.values()) - 100.0) < 1e-9
    assert all(v > 0 for k, v in alloc.items() if k != "diversity")


def test_user_can_still_set_diversity():
    assert main.parse_token_allocation("diversity:5,housing_value:5")["diversity"] == 50.0

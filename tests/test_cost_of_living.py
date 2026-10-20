"""Validation for pillars/cost_of_living.py.

Cross-checks use values computed by hand from the published brackets, and a BEA goods price
level read independently from FRED (NYC metro goods RPP, 2024 = 110.261).  The pillar is not
wired into the catalog; these tests cover the module and its data files only.
"""

import pytest

from pillars import cost_of_living as col


def test_state_tax_matches_hand_calculation():
    income = 78538.0
    # Pennsylvania: flat 3.07%, no deduction.
    assert col.state_income_tax("Pennsylvania", income) == pytest.approx(income * 0.0307)
    # Illinois: flat 4.95% after the $5,850 couple exemption.
    assert col.state_income_tax("Illinois", income) == pytest.approx((income - 5850) * 0.0495)
    # New York: $16,050 deduction, then 3.9% / 4.4% / 5.15% / 5.4% bands.
    expected_ny = 17150 * 0.039 + (23600 - 17150) * 0.044 + (27900 - 23600) * 0.0515 + (income - 16050 - 27900) * 0.054
    assert col.state_income_tax("New York", income) == pytest.approx(expected_ny)
    # No wage income tax.
    for state in ("Texas", "Florida", "Washington"):
        assert col.state_income_tax(state, income) == 0.0


def test_state_tax_is_monotonic_in_income():
    for state in ("California", "New York", "New Jersey", "Maryland", "Oregon"):
        taxes = [col.state_income_tax(state, i) for i in (30000, 60000, 120000, 250000, 600000)]
        assert taxes == sorted(taxes), state


def test_bea_goods_price_level_matches_fred():
    rpp, level = col.goods_rpp("35620", "New York")
    assert level == "msa"
    assert rpp == pytest.approx(110.261, abs=0.001)


def test_metro_falls_back_to_state_then_none():
    rpp, level = col.goods_rpp(None, "Texas")
    assert level == "state" and rpp > 0
    assert col.goods_rpp(None, "Atlantis") == (None, "none")


def test_no_income_uses_the_national_reference_household():
    score, det = col.get_cost_of_living_score("Pennsylvania", cbsa_code="37980")
    assert score is not None
    assert det["summary"]["income_basis"] == "us_median_reference"
    assert det["summary"]["household_income"] == round(col.reference_income())


def test_explicit_income_is_used_and_labelled():
    score, det = col.get_cost_of_living_score("Pennsylvania", cbsa_code="37980", income=150000)
    assert det["summary"]["income_basis"] == "caller"
    assert det["summary"]["household_income"] == 150000


def test_scores_are_bounded_and_ordered_by_tax_at_equal_prices():
    # Same metro price level; only state tax differs.
    tx, _ = col.get_cost_of_living_score("Texas", cbsa_code="19100")
    il, _ = col.get_cost_of_living_score("Illinois", cbsa_code="19100")
    ca, _ = col.get_cost_of_living_score("California", cbsa_code="19100")
    for s in (tx, il, ca):
        assert 0.0 <= s <= 100.0
    assert tx > il
    assert tx > ca


def test_city_income_tax_lowers_the_score():
    with_city, d1 = col.get_cost_of_living_score("New York", cbsa_code="35620", city="New York")
    without, d2 = col.get_cost_of_living_score("New York", cbsa_code="35620", city="Scarsdale")
    assert d1["summary"]["local_tax_jurisdiction"] == "New York city, New York"
    assert d2["summary"]["local_tax_jurisdiction"] is None
    assert with_city < without


def test_score_is_independent_of_place_income():
    # Same state, metro and city give the same score; place income is not an input.
    a, _ = col.get_cost_of_living_score("Illinois", cbsa_code="16980", city="Hinsdale")
    b, _ = col.get_cost_of_living_score("Illinois", cbsa_code="16980", city="Gary")
    assert a == b


def test_anchor_ordering_and_income_awareness():
    lo, hi = col.burden_anchors(78538)
    assert 0 < lo < hi < 1
    # Groceries are a fixed dollar amount, so the burden of a lower income is larger.
    lo_low, hi_low = col.burden_anchors(40000)
    assert lo_low > lo and hi_low > hi


def test_missing_inputs_degrade_instead_of_guessing():
    score, det = col.get_cost_of_living_score(None)
    assert score is None and det["status"] == "DEGRADED"
    score, det = col.get_cost_of_living_score("Atlantis")
    assert score is None and det["status"] == "DEGRADED"


def test_scale_covers_the_us():
    meta = col._scale["_meta"]
    assert meta["places_used"] > 150_000_000  # population in places of 2,500+
    assert meta["groups"] >= 50

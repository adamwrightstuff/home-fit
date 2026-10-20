"""Tests for comparison/relocation_equivalency.py (metro to metro, rent and owner)."""

import pytest

from comparison import relocation_equivalency as R

DALLAS = "19100"
NYC = "35620"
PHOENIX = "38060"
HOUSTON = "26420"


def test_covers_the_national_metro_set():
    assert len(R._msa) >= 380
    for code in (DALLAS, NYC, PHOENIX, HOUSTON):
        m = R.metro(code)
        assert m["median_gross_rent"] > 0 and m["median_home_value"] > 0 and m["goods"] > 0


def test_find_metro_by_name():
    assert NYC in R.find_metro("New York-Newark")
    assert R.find_metro("zzzz-not-a-metro") == []


def test_same_metro_needs_same_income():
    for tenure, h in (("rent", None), ("own", 30000)):
        r = R.equivalent_income(DALLAS, DALLAS, 100000, tenure=tenure, housing_year=h)
        assert r["equivalent_income_in_dest"] == pytest.approx(100000, abs=1)


def test_round_trip_returns_the_original_income():
    # The return leg must start from the housing cost the first leg produced.
    first = R.equivalent_income(DALLAS, NYC, 100000, housing_year=18000)
    back = R.equivalent_income(NYC, DALLAS, first["equivalent_income_in_dest"],
                               housing_year=first["dest_costs_at_equivalent_income"]["housing"])
    assert back["equivalent_income_in_dest"] == pytest.approx(100000, abs=5)


def test_left_over_money_is_actually_held_constant():
    r = R.equivalent_income(DALLAS, NYC, 100000)
    d = r["dest_costs_at_equivalent_income"]
    assert d["left_over"] == pytest.approx(r["left_over_held_constant"], abs=2)


def test_pricier_metro_needs_more_and_cheaper_needs_less():
    assert R.equivalent_income(DALLAS, NYC, 100000)["equivalent_income_in_dest"] > 100000
    assert R.equivalent_income(NYC, HOUSTON, 100000)["equivalent_income_in_dest"] < 100000


def test_renter_housing_scales_with_the_bea_housing_price_level_ratio():
    r = R.equivalent_income(DALLAS, NYC, 100000)
    assert r["housing_scale"] == pytest.approx(R.metro(NYC)["housing"] / R.metro(DALLAS)["housing"], abs=0.001)
    # With no rent given, origin housing is the origin median rent x 12.
    assert r["origin_costs"]["housing"] == round(R.metro(DALLAS)["median_gross_rent"] * 12)


def test_owner_housing_scales_with_median_home_value_ratio_and_needs_an_input():
    r = R.equivalent_income(DALLAS, NYC, 150000, tenure="own", housing_year=30000)
    assert r["housing_scale_source"] == "Zillow Home Value Index"
    assert r["housing_scale"] == pytest.approx(R.metro(NYC)["zhvi"] / R.metro(DALLAS)["zhvi"], abs=0.001)
    assert r["dest_costs_at_equivalent_income"]["housing"] == pytest.approx(30000 * r["housing_scale"], abs=40)
    with pytest.raises(ValueError):
        R.equivalent_income(DALLAS, NYC, 150000, tenure="own")


def test_a_users_own_rent_is_scaled_not_replaced_by_the_median():
    r = R.equivalent_income(DALLAS, NYC, 100000, housing_year=24000)
    assert r["origin_costs"]["housing"] == 24000
    assert r["dest_costs_at_equivalent_income"]["housing"] == pytest.approx(24000 * r["housing_scale"], abs=40)


def test_costs_match_hand_calculation():
    c = R.costs_in(DALLAS, 100000, 20000)
    assert c["tax"] == 0.0  # Texas has no wage income tax
    assert c["everyday"] == pytest.approx(R.BASKET_BASE * R.basket_index(DALLAS) / 100)
    assert c["left_over"] == pytest.approx(100000 - 20000 - c["everyday"])


def test_tax_state_defaults_to_first_listed_and_can_be_overridden():
    assert R.tax_state(NYC) == "New York"  # New York-Newark-Jersey City, NY-NJ
    assert R.tax_state(NYC, "NJ") == "New Jersey"
    ny = R.costs_in(NYC, 150000, 0)["tax"]
    nj = R.costs_in(NYC, 150000, 0, state="NJ")["tax"]
    assert ny != nj


def test_ranking_orders_every_metro_by_income_needed():
    ranked = R.rank_metros(DALLAS, 100000)
    assert len(ranked) == len(R._msa) - 1
    needs = [r["equivalent_income"] for r in ranked]
    assert needs == sorted(needs)
    assert needs[0] < 100000 < needs[-1]


def test_output_is_labelled_as_an_estimate():
    assert "Estimate" in R.equivalent_income(DALLAS, NYC, 100000)["estimate_note"]


def test_owner_scaling_falls_back_to_census_value_when_zillow_is_missing():
    dayton = R.find_metro("Dayton-Kettering")[0]  # no Zillow match
    r = R.equivalent_income(DALLAS, dayton, 100000, tenure="own", housing_year=24000)
    assert r["housing_scale_source"] == "Census median home value"
    assert r["housing_scale"] == pytest.approx(R.metro(dayton)["median_home_value"] / R.metro(DALLAS)["median_home_value"], abs=0.001)


def test_city_income_tax_applies_only_when_the_household_is_in_the_city():
    suburb = R.equivalent_income(DALLAS, NYC, 100000)
    city = R.equivalent_income(DALLAS, NYC, 100000, dest_city="New York")
    assert city["city_tax"]["dest"] == "New York" and suburb["city_tax"]["dest"] is None
    assert city["equivalent_income_in_dest"] > suburb["equivalent_income_in_dest"]
    philly = R.find_metro("Philadelphia-Camden")[0]
    assert R.equivalent_income(DALLAS, philly, 100000, dest_city="Philadelphia")["city_tax"]["dest"] == "Philadelphia"


def test_catalog_bridge_returns_both_views_when_a_housing_cost_is_given():
    from comparison.catalog_bridge import catalog_equivalency
    r = catalog_equivalency("dallas", "nyc", 120000, monthly_cost=2200, dest_state="NJ", dest_city="Hoboken")
    assert r["rent"]["equivalent_income_in_dest"] > 0 and r["own"]["equivalent_income_in_dest"] > 0
    assert r["rent"]["tax_states"]["dest"] == "New Jersey"
    assert r["rent"]["city_tax"]["dest"] is None  # Hoboken has no cited city tax


def test_catalog_bridge_renter_only_without_cost_and_skips_same_metro():
    from comparison.catalog_bridge import catalog_equivalency
    r = catalog_equivalency("dallas", "nyc", 120000, dest_city="New York")
    assert r["own"] is None and r["rent"]["city_tax"]["dest"] == "New York"
    same = catalog_equivalency("nyc", "nyc", 120000, monthly_cost=3000)
    assert same["same_metro"] and same["rent"] is None


def test_every_catalog_metro_key_maps_to_a_priced_metro():
    from comparison import catalog_bridge as B
    for key, code in B._CBSA.items():
        assert code in R._msa, key

import math

from pillars.healthcare_access import HEALTHCARE_BUDGETS, _pharmacy_distance_fraction, healthcare_total

MILE = 1.609344


def test_full_credit_inside_half_a_mile():
    assert _pharmacy_distance_fraction(0.0) == 1.0
    assert _pharmacy_distance_fraction(0.5 * MILE) == 1.0


def test_half_credit_at_one_mile():
    assert math.isclose(_pharmacy_distance_fraction(1.0 * MILE), 0.5, abs_tol=1e-9)


def test_five_percent_at_ten_miles():
    assert math.isclose(_pharmacy_distance_fraction(10.0 * MILE), 0.05, abs_tol=1e-9)


def test_curve_is_continuous_and_never_increases_with_distance():
    prev = 1.0
    for i in range(0, 400):
        f = _pharmacy_distance_fraction(i * 0.1)
        assert 0.0 <= f <= prev + 1e-12
        prev = f
    assert abs(_pharmacy_distance_fraction(MILE - 1e-6) - _pharmacy_distance_fraction(MILE + 1e-6)) < 1e-4


def test_total_is_plain_sum_when_every_component_is_present():
    parts = {k: v * 0.5 for k, v in HEALTHCARE_BUDGETS.items()}
    assert math.isclose(healthcare_total(parts), 50.0)
    assert math.isclose(healthcare_total(parts, hospital_bonus=2.0), 52.0)


def test_unknown_pharmacy_scales_over_the_remaining_components():
    parts = {k: v * 0.5 for k, v in HEALTHCARE_BUDGETS.items()}
    parts["pharmacies"] = None
    # half of every remaining budget is still 50, not 42.5
    assert math.isclose(healthcare_total(parts), 50.0)


def test_total_is_capped_at_100():
    parts = dict(HEALTHCARE_BUDGETS)
    assert healthcare_total(parts, hospital_bonus=5.0) == 100.0


def test_pillar_marks_pharmacies_unknown_when_other_facilities_are_mapped_but_no_pharmacy(monkeypatch):
    import pillars.healthcare_access as hc

    data = {
        "hospitals": [{"name": "H", "distance_km": 2.0, "tags": {"emergency": "yes"}}],
        "urgent_care": [], "clinics": [{"name": "C", "distance_km": 1.0}], "pharmacies": [], "doctors": [],
        "_overpass_outcome": "overpass_ok",
    }
    monkeypatch.setattr(hc, "_get_osm_healthcare", lambda *a, **k: dict(data))
    monkeypatch.setattr(hc.osm_api, "query_healthcare_facilities", lambda *a, **k: dict(data), raising=False)
    score, bd = hc.get_healthcare_access_score(40.7, -74.0, area_type="suburban", density=4000.0)
    assert bd["breakdown"]["pharmacies"] is None
    assert bd["summary"].get("pharmacies_unknown") is True
    assert score > 0


def test_capacity_score_is_half_credit_ish_at_the_catalog_median_and_none_without_residents():
    from pillars.healthcare_access import _ratio_score, capacity_score
    # 22 hospitals for 1,000,000 residents is 2.2 per 100,000, the scale's median
    at_median = capacity_score(22, 1_000_000, 2.2, 100000.0, 20.0)
    assert math.isclose(at_median, _ratio_score(1.0, 20.0))
    assert capacity_score(5, None, 2.2, 100000.0, 20.0) is None
    assert capacity_score(0, 500_000, 2.2, 100000.0, 20.0) == 0.0
    more = capacity_score(44, 1_000_000, 2.2, 100000.0, 20.0)
    assert more > at_median


def test_supply_scale_file_loads_with_the_primary_care_median():
    from pillars.healthcare_access import _load_supply_scale
    sc = _load_supply_scale()
    assert sc and sc["expected_clinics_doctors_per_1000"] > 0


def test_unknown_budget_override_scales_over_the_distance_part_only():
    from pillars.healthcare_access import HEALTHCARE_BUDGETS
    budgets = dict(HEALTHCARE_BUDGETS)
    budgets["hospital_access"] = 15.0
    parts = {"hospital_access": 7.5, "primary_care": None, "specialized_care": 7.5, "emergency_services": 5.0, "pharmacies": 7.5}
    assert math.isclose(healthcare_total(parts, 0.0, budgets), 50.0)


def test_pillar_scores_primary_care_per_resident_without_area_type_tables(monkeypatch):
    import pillars.healthcare_access as hc

    data = {
        "hospitals": [{"name": "H", "distance_km": 2.0, "tags": {"emergency": "yes"}}],
        "urgent_care": [], "clinics": [{"name": "C", "distance_km": 1.0}], "pharmacies": [{"name": "P", "distance_km": 0.5}],
        "doctors": [], "_query_failed": False,
    }
    monkeypatch.setattr(hc, "_get_osm_healthcare", lambda *a, **k: dict(data))
    monkeypatch.setattr(hc, "people_within", lambda *a, **k: 100_000.0)
    score_small, bd_small = hc.get_healthcare_access_score(40.7, -74.0, area_type="suburban", density=4000.0)
    monkeypatch.setattr(hc, "people_within", lambda *a, **k: 1_000_000.0)
    score_big, bd_big = hc.get_healthcare_access_score(40.7, -74.0, area_type="suburban", density=4000.0)
    # the same facilities serve ten times the residents: capacity parts fall, distance parts do not
    assert bd_small["breakdown"]["primary_care"] > bd_big["breakdown"]["primary_care"]
    assert bd_small["breakdown"]["emergency_services"] == bd_big["breakdown"]["emergency_services"]
    assert score_small > score_big
    # same inputs under another area type give the same score
    monkeypatch.setattr(hc, "people_within", lambda *a, **k: 100_000.0)
    score_rural, _ = hc.get_healthcare_access_score(40.7, -74.0, area_type="rural", density=100.0)
    assert math.isclose(score_rural, score_small)


def test_hospital_count_does_not_change_the_score_only_distance_does(monkeypatch):
    import pillars.healthcare_access as hc

    def run(n_hospitals):
        hospitals = [{"name": f"H{i}", "distance_km": 2.0, "tags": {"emergency": "yes"}} for i in range(n_hospitals)]
        data = {"hospitals": hospitals, "urgent_care": [], "clinics": [{"name": "C", "distance_km": 1.0}],
                "pharmacies": [{"name": "P", "distance_km": 0.5}], "doctors": [], "_query_failed": False}
        monkeypatch.setattr(hc, "_get_osm_healthcare", lambda *a, **k: dict(data))
        monkeypatch.setattr(hc, "people_within", lambda *a, **k: 500_000.0)
        return hc.get_healthcare_access_score(40.7, -74.0, area_type="suburban", density=4000.0)

    s1, bd1 = run(1)
    s9, bd9 = run(9)
    assert bd1["breakdown"]["hospital_access"] == bd9["breakdown"]["hospital_access"]
    # only the small bonus for extra hospitals differs
    assert 0 <= s9 - s1 <= 5.0


def test_pillar_reads_residents_from_the_place_context(monkeypatch):
    import pillars.healthcare_access as hc
    from data_sources.place_context import PlaceContext

    def boom(*a, **k):
        raise AssertionError("pillar recomputed residents although the context carries them")

    data = {
        "hospitals": [{"name": "H", "distance_km": 2.0, "tags": {"emergency": "yes"}}],
        "urgent_care": [], "clinics": [{"name": "C", "distance_km": 1.0}], "pharmacies": [{"name": "P", "distance_km": 0.4}],
        "doctors": [], "_query_failed": False,
    }
    monkeypatch.setattr(hc, "_get_osm_healthcare", lambda *a, **k: dict(data))
    monkeypatch.setattr(hc, "people_within", boom)
    ctx = PlaceContext(lat=40.7, lon=-74.0, city=None, area_type="suburban", density=4000.0, people_10km=250000.0)
    score, bd = hc.get_healthcare_access_score(40.7, -74.0, place_context=ctx)
    assert score > 0 and bd["breakdown"]["primary_care"] is not None


def _empty_read(monkeypatch):
    import pillars.healthcare_access as hc
    empty = {"hospitals": [], "urgent_care": [], "clinics": [], "pharmacies": [], "doctors": [], "_query_failed": False}
    monkeypatch.setattr(hc, "_get_osm_healthcare", lambda *a, **k: dict(empty))
    return hc


def test_empty_read_next_to_a_known_hospital_is_a_failed_read_not_a_zero(monkeypatch):
    import pytest
    hc = _empty_read(monkeypatch)
    # Mass General Hospital, Boston: the major hospital database lists it, so an all-empty read here cannot be real
    with pytest.raises(RuntimeError, match="known hospital"):
        hc.get_healthcare_access_score(42.3631, -71.0686, area_type="urban_residential", density=20000.0)


def test_empty_read_with_no_known_hospital_nearby_stays_a_real_zero(monkeypatch):
    hc = _empty_read(monkeypatch)
    score, bd = hc.get_healthcare_access_score(40.0, -105.5, area_type="rural", density=50.0)  # remote Colorado, no listed hospital within 10 km
    assert bd["breakdown"]["pharmacies"] == 0.0 and score < 10

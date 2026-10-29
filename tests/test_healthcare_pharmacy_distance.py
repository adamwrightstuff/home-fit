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

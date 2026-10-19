from scripts.catalog.build_prism_climate import build_profile


def test_build_profile_replaces_temp_and_precip_keeps_solar():
    old = {"months": [{"month": m, "month_name": "x", "avg_temp_f": 1.0, "avg_precip_in": 9.9, "solar_kwh_m2_day": 4.2} for m in range(1, 13)]}
    new = build_profile(old, [0.0] * 12, [100.0] * 12, "800m")
    assert new["months"][0]["avg_temp_f"] == 32.0
    assert new["months"][0]["avg_precip_in"] == 3.94
    assert new["months"][0]["solar_kwh_m2_day"] == 4.2
    assert new["temp_precip_source"] == "prism_1991_2020_800m"


def test_build_profile_returns_none_when_prism_has_no_answer():
    assert build_profile({"months": []}, [None] + [1.0] * 11, [1.0] * 12, "4km") is None

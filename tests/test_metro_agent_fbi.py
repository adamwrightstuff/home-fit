from scripts.metro_agent import fbi_probe as fp


def ag(name, ori, lat, lon, typ="City", nibrs=True):
    return {"agency_name": name, "ori": ori, "latitude": lat, "longitude": lon, "agency_type": typ, "is_nibrs": nibrs}


AGENCIES = [
    ag("Cedar Park Police Department", "TX2460100", 30.52, -97.82),
    ag("Georgetown Police Department", "TX2460200", 30.56, -97.75),
    ag("Williamson County Sheriff's Office", "TX2460000", 30.64, -97.68, "County"),
    ag("Travis County Sheriff's Office", "TX2270000", 30.27, -97.74, "County"),
    ag("Far Away Police Department", "TX9999999", 33.0, -100.0),
]


def rates(has):
    def fn(ori, offense, year, name):
        if ori in has and year <= has[ori]:
            return (250.0, "agency", 80000)
        return (400.0, "state", None)
    return fn


def test_agency_named_for_the_place_with_data_is_usable():
    r = fp.probe_place("Cedar Park", "Williamson", 30.5217, -97.8278, AGENCIES, rates({"TX2460100": 2024}), 2024)
    assert r["verdict"] == "USABLE" and r["best"]["ori"] == "TX2460100"


def test_only_neighbours_with_data_is_not_usable_and_says_do_not_borrow():
    r = fp.probe_place("Cedar Park", "Williamson", 30.5217, -97.8278, AGENCIES, rates({"TX2460200": 2024}), 2024)
    assert r["verdict"] == "NO_AGENCY_DATA" and "do not borrow" in r["note"]
    assert r["best"] is None


def test_unincorporated_place_falls_to_county_sheriff_with_a_confirmation_note():
    r = fp.probe_place("Manchaca", "Travis", 30.14, -97.82, AGENCIES, rates({"TX2270000": 2023}), 2024)
    assert r["verdict"] == "USABLE" and "Sheriff" in r["best"]["name"] and "Confirm" in r["note"]


def test_walks_back_years_to_the_latest_with_data():
    d = fp.agency_data("X", "n", rates({"X": 2022}), 2024)
    assert d["year"] == 2022
    assert fp.agency_data("X", "n", rates({}), 2024) is None


def test_nothing_nearby_is_no_agency():
    r = fp.probe_place("Nowhere", "Nowhere", 25.0, -90.0, AGENCIES, rates({}), 2024)
    assert r["verdict"] == "NO_AGENCY"


def test_run_only_probes_places_blocked_for_lack_of_a_source():
    row = {"catalog": {"name": "Cedar Park", "state_abbr": "TX", "county_borough": "Williamson", "lat": "30.5217", "lon": "-97.8278"},
           "success": True, "score": {"livability_pillars": {"community_safety": {"score": None, "breakdown": {"source": "fbi_cde_state"}}}}}
    ok = {"catalog": {"name": "Zilker", "state_abbr": "TX", "lat": "30.26", "lon": "-97.77"}, "success": True,
          "score": {"livability_pillars": {"community_safety": {"score": 60, "breakdown": {"source": "austin_open_data"}}}}}
    res = fp.run([row, ok], agencies_fn=lambda st: AGENCIES, rate_fn=rates({"TX2460100": 2024}), log=lambda s: None)
    assert [x["place"] for x in res] == ["Cedar Park"] and res[0]["verdict"] == "USABLE"

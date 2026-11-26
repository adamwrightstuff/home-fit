"""Surroundings builder: weighted neighbor averages from stored catalog numbers, display only."""
from scripts.catalog import build_catalog_surroundings as b


def _row(name, lat, lon, income=None, home=None, safety=None):
    return {"key": f"{name}|C|ST", "name": name, "ll": (lat, lon), "income": income, "home_value": home, "safety": safety}


def test_closest_neighbor_counts_most_and_self_is_excluded():
    rows = [_row("A", 40.0, -74.0, 50_000), _row("B", 40.0, -74.01, 200_000), _row("C", 40.0, -74.08, 100_000)]
    s = b.surroundings_for(rows)
    a = s["A|C|ST"]["income"]
    assert a["here"] == 50_000
    assert 100_000 < a["around"] < 200_000  # B (0.5 mi) outweighs C (4.2 mi); A itself is not in the average
    assert s["A|C|ST"]["neighbors"][0] == "B"


def test_too_little_nearby_weight_gives_no_figure():
    rows = [_row("A", 40.0, -74.0, 50_000), _row("Far", 40.0, -74.14, 90_000)]  # about 7.4 mi: weight ~0.002
    assert b.surroundings_for(rows) == {}


def test_place_at_the_census_cap_gets_no_comparison():
    rows = [_row("Rich", 40.0, -74.0, b.INCOME_CAP, 900_000),
            _row("B", 40.0, -74.005, 80_000, 500_000), _row("C", 40.0, -73.995, 90_000, 600_000)]
    rich = b.surroundings_for(rows)["Rich|C|ST"]
    assert "income" not in rich and rich["home_value"]["here"] == 900_000


def test_safety_zero_is_a_real_value_and_missing_neighbors_are_skipped():
    rows = [_row("A", 40.0, -74.0, safety=0.0), _row("B", 40.0, -74.005, safety=90.0),
            _row("C", 40.0, -73.995, safety=80.0), _row("CityRate", 40.0, -74.002, safety=None)]
    a = b.surroundings_for(rows)["A|C|ST"]["safety"]
    assert a["here"] == 0 and 80 <= a["around"] <= 90  # CityRate (no own rate) is not averaged in


def test_only_a_place_s_own_rate_counts():
    feed = {"source": "denver_open_data"}
    own = {"source": "fbi_nibrs_agency", "agency_name": "Dobbs Ferry Police Department"}
    assert b._safety_key("neighborhood", feed) == ("denver_open_data", "")
    assert b._safety_key("suburb", own) == ("fbi_nibrs_agency", "Dobbs Ferry Police Department")
    assert b._safety_key("neighborhood", {**own, "agency_name": "Denver Police Department"}) is None
    assert b._safety_key("suburb", {"source": "fbi_county_agency", "agency_name": "Jefferson County Sheriff's Office"}) is None
    assert b._safety_key("suburb", {"source": "ny_state_ucr", "agency_name": "Nassau County PD"}) is None
    assert b._safety_key("suburb", {"source": "lasd_station", "agency_name": "Lakewood"}) is None
    assert b._safety_key("suburb", {"source": "fbi_cde_state"}) is None


def test_live_point_uses_catalog_neighbors_and_drops_shared_city_rates(monkeypatch):
    import surroundings as s
    city = ("fbi_nibrs_agency", "Big City Police Department")
    rows = (
        {"key": "Twin|C|ST", "name": "Twin", "ll": (40.0, -74.0), "income": 90_000.0, "home_value": None, "safety": 50.0, "agency_key": ("x_open_data", "")},
        {"key": "N1|C|ST", "name": "N1", "ll": (40.0, -74.01), "income": 100_000.0, "home_value": None, "safety": 70.0, "agency_key": ("x_open_data", "")},
        {"key": "N2|C|ST", "name": "N2", "ll": (40.0, -73.99), "income": 120_000.0, "home_value": None, "safety": None, "agency_key": None, "agency_any": city},
        {"key": "N3|C|ST", "name": "N3", "ll": (40.008, -74.0), "income": 110_000.0, "home_value": None, "safety": 80.0, "agency_key": ("x_open_data", "")},
    )
    monkeypatch.setattr(s, "all_catalog_rows", lambda: rows)
    # A searched point named like a catalog place is that place: it is not its own neighbor.
    own = s.for_point(40.0, -74.0, name="Twin", income=80_000, safety=60, safety_source="x_open_data")
    assert own["neighbors"][0] != "Twin" and 100_000 <= own["income"]["around"] <= 120_000
    assert own["safety"]["here"] == 60
    # A point on an agency rate that a catalog place also uses (a city-wide rate) gets no safety row.
    shared = s.for_point(40.0, -74.0, name="Elsewhere", income=80_000, safety=20,
                         safety_source="fbi_nibrs_agency", agency_name="Big City Police Department")
    assert "safety" not in shared and "income" in shared

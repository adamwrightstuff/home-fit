"""800 m disk flood measure (data_sources/fema_flood.py): synthetic polygons, no network."""
import pytest

from data_sources import fema_flood as ff

LAT, LON = 40.0, -100.0
M_PER_DEG_LAT = 111320.0


def _feature(fld_zone, subty, sfha, west_m, east_m, half_height_m=5000.0):
    """A rectangle in metres around the pin as an Esri feature (clockwise outer ring, lon/lat)."""
    import math

    kx = M_PER_DEG_LAT * math.cos(math.radians(LAT))
    w, e = LON + west_m / kx, LON + east_m / kx
    s, n = LAT - half_height_m / M_PER_DEG_LAT, LAT + half_height_m / M_PER_DEG_LAT
    return {"attributes": {"FLD_ZONE": fld_zone, "ZONE_SUBTY": subty, "SFHA_TF": sfha},
            "geometry": {"rings": [[[w, s], [w, n], [e, n], [e, s], [w, s]]]}}


def _disk(feats):
    return ff.disk_flood_points(ff.zones_from_polygons(feats, LAT, LON), 0.0, 0.0)


def test_half_sfha_half_minimal_is_the_area_weighted_mean():
    feats = [_feature("AE", "", "T", -5000, 0), _feature("X", "AREA OF MINIMAL FLOOD HAZARD", "F", 0, 5000)]
    pts, mapped, shares = _disk(feats)
    assert pts == pytest.approx(0.5 * 30 * ff.SFHA_RETAINED + 0.5 * 30, abs=0.1)
    assert mapped == pytest.approx(1.0, abs=0.01)
    assert shares["sfha"] == pytest.approx(0.5, abs=0.01)


def test_floodway_wins_over_overlapping_sfha():
    feats = [_feature("AE", "", "T", -5000, 5000), _feature("AE", "FLOODWAY", "T", -5000, 5000)]
    pts, _, shares = _disk(feats)
    assert pts == pytest.approx(0.0, abs=0.01)
    assert "sfha" not in shares


def test_zone_d_only_is_no_data():
    pts, mapped, shares = _disk([_feature("D", "", "F", -5000, 5000)])
    assert pts is None
    assert mapped == pytest.approx(1.0, abs=0.01)
    assert ff.flood_zone_from_disk(pts, mapped, shares)["risk_tier"] == "d"


def test_no_polygon_is_unmapped_no_data():
    pts, mapped, shares = _disk([])
    assert pts is None and mapped == 0.0
    out = ff.flood_zone_from_disk(pts, mapped, shares)
    assert out["risk_tier"] == "unmapped" and out["flood_zone_pts"] is None


def test_zone_d_area_is_left_out_of_the_mean():
    feats = [_feature("D", "", "F", -5000, 0), _feature("X", "AREA OF MINIMAL FLOOD HAZARD", "F", 0, 5000)]
    pts, mapped, _ = _disk(feats)
    assert pts == pytest.approx(30.0, abs=0.01)
    assert mapped == pytest.approx(1.0, abs=0.01)


def test_flag_off_uses_the_pin_lookup(monkeypatch):
    monkeypatch.delenv("HOMEFIT_FLOOD_DISK", raising=False)
    monkeypatch.setattr(ff, "_get_fema_flood_zone_v3", lambda lat, lon: {"risk_tier": "minimal", "flood_zone_pts": 30.0})
    monkeypatch.setattr(ff, "_get_fema_flood_disk_v1", lambda lat, lon: pytest.fail("disk must not run with the flag off"))
    assert ff.get_fema_flood_zone(LAT, LON) == {"risk_tier": "minimal", "flood_zone_pts": 30.0}


def test_flag_on_returns_the_disk_result(monkeypatch):
    monkeypatch.setenv("HOMEFIT_FLOOD_DISK", "true")
    disk = {"risk_tier": "sfha", "flood_zone_pts": 17.25, "method": ff.FLOOD_DISK_METHOD}
    monkeypatch.setattr(ff, "_get_fema_flood_disk_v1", lambda lat, lon: disk)
    assert ff.get_fema_flood_zone(LAT, LON) == disk


def test_flag_on_failed_disk_falls_back_to_the_pin_and_says_so(monkeypatch):
    monkeypatch.setenv("HOMEFIT_FLOOD_DISK", "true")
    monkeypatch.setattr(ff, "_get_fema_flood_disk_v1", lambda lat, lon: None)
    monkeypatch.setattr(ff, "_get_fema_flood_zone_v3", lambda lat, lon: {"risk_tier": "minimal", "flood_zone_pts": 30.0})
    out = ff.get_fema_flood_zone(LAT, LON)
    assert out["method"] == "pin_fallback" and out["flood_zone_pts"] == 30.0


def test_flag_on_both_failing_is_no_data(monkeypatch):
    monkeypatch.setenv("HOMEFIT_FLOOD_DISK", "true")
    monkeypatch.setattr(ff, "_get_fema_flood_disk_v1", lambda lat, lon: None)
    monkeypatch.setattr(ff, "_get_fema_flood_zone_v3", lambda lat, lon: None)
    assert ff.get_fema_flood_zone(LAT, LON) is None


def test_live_disk_read_matches_the_catalog_calculation(monkeypatch):
    """The live function and the catalog path call the same code on the same polygons, so the points are identical."""
    feats = [_feature("AE", "", "T", -5000, 0), _feature("X", "AREA OF MINIMAL FLOOD HAZARD", "F", 0, 5000)]
    monkeypatch.setattr(ff, "fetch_flood_polygons", lambda lat, lon, fetch_m, **kw: feats)
    live = ff._get_fema_flood_disk_v1.__wrapped__(LAT, LON)
    pts, mapped, shares = _disk(feats)
    assert live["flood_zone_pts"] == round(pts, 2)
    assert live["mapped_fraction"] == round(mapped, 3)
    assert live["method"] == ff.FLOOD_DISK_METHOD and live["risk_tier"] == "sfha"


def test_failed_polygon_query_gives_none_not_a_number(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("FEMA answer without features")

    monkeypatch.setattr(ff, "fetch_flood_polygons", boom)
    assert ff._get_fema_flood_disk_v1.__wrapped__(LAT, LON) is None

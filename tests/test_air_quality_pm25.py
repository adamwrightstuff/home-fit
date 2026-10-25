"""PM2.5 tract table lookup: a missing tract is None, never a made-up value."""
import json

from data_sources import air_quality_pm25 as aq


def test_lookup_reads_the_table_and_missing_tracts_are_none(tmp_path, monkeypatch):
    f = tmp_path / "pm25.json"
    f.write_text(json.dumps({"_meta": {"years": [2021, 2022]}, "tracts": {"36061002902": 7.25}}))
    monkeypatch.setattr(aq, "TABLE_PATH", f)
    monkeypatch.setattr(aq, "_cache", None)
    got = aq.get_pm25_for_tract("36061002902")
    assert got["pm25_ugm3"] == 7.25 and got["years"] == [2021, 2022] and got["source"] == "cdc_tracking_epa_downscaler"
    assert aq.get_pm25_for_tract("99999999999") is None and aq.get_pm25_for_tract(None) is None


def test_missing_table_file_gives_no_data(tmp_path, monkeypatch):
    monkeypatch.setattr(aq, "TABLE_PATH", tmp_path / "absent.json")
    monkeypatch.setattr(aq, "_cache", None)
    assert aq.get_pm25_for_tract("36061002902") is None


def test_unmatched_tract_uses_the_nearest_centroid_within_range_and_is_flagged(tmp_path, monkeypatch):
    f = tmp_path / "pm25.json"
    f.write_text(json.dumps({"_meta": {"years": [2021, 2022]},
                             "tracts": {"09001000100": 8.0, "09001000200": 6.0, "36061002902": 7.0},
                             "centroids": {"09001000100": [41.00, -73.60], "09001000200": [41.20, -73.60], "36061002902": [41.001, -73.601]}}))
    monkeypatch.setattr(aq, "TABLE_PATH", f)
    monkeypatch.setattr(aq, "_cache", None)
    got = aq.get_pm25_for_point("09110000100", 41.001, -73.601)  # new Connecticut code, not in the table
    assert got["pm25_ugm3"] == 8.0 and got["match"] == "nearest_centroid" and got["match_km"] < 1.0  # other state ignored
    far = aq.get_pm25_for_point("09110000100", 41.60, -73.60)  # nothing within 5 km
    assert far is None
    exact = aq.get_pm25_for_point("09001000200", 41.2, -73.6)
    assert exact["pm25_ugm3"] == 6.0 and exact["match"] == "exact"

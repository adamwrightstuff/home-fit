"""Catalog list/detail endpoints and slimming (catalog_api.py). Uses a tiny synthetic data dir, never the real catalog."""
import gzip
import json
import math

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import catalog_api


def _place(name, **score_extra):
    return {
        "catalog": {"name": name, "county_borough": "Kings", "state_abbr": "NY", "type": "neighborhood"},
        "success": True,
        "cbd_transit_minutes": 33.0,
        "score": {
            "total_score": 70.0,
            "total_score_breakdown": {"big": "x" * 50},  # an UNUSED key at the score level
            "livability_pillars": {
                "natural_beauty": {
                    "score": 70.0,
                    "tree_analysis": {"big": "y" * 50},  # an UNUSED key inside a pillar
                    "v9_breakdown": {"gvi_score": 12.0, "heavy": "z" * 50},
                    "data_quality": {"fallback_used": False, "other": 1},
                },
                "quality_education": {
                    "score": 77.0,
                    "breakdown": {"split": {"elementary": 80}, "heavy": "h" * 50},
                    "summary": {"early_ed_note": "x"},
                },
                "social_fabric": {"score": 48.8, "summary": {"orgs_per_1k": 0.35}},
            },
            **score_extra,
        },
    }


@pytest.fixture()
def data(tmp_path, monkeypatch):
    d, cache = tmp_path / "data", tmp_path / "cache"
    d.mkdir()
    (d / "metro_registry.json").write_text(json.dumps({"metros": {
        "nyc": {"status": "live"}, "boston": {"status": "building"}, "la": {"status": "live"}}}))
    (d / "nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl").write_text(
        json.dumps(_place("Carroll Gardens")) + "\n" + json.dumps(_place("Park Slope")) + "\n"
        + json.dumps({"success": False, "catalog": {"name": "Bad"}}) + "\n")
    months = [{"month": m, "avg_temp_f": 30.0 + m, "avg_precip_in": 3.66, "solar_kwh_m2_day": 4.0} for m in range(1, 13)]
    (d / "catalog_climate_profiles.jsonl").write_text(
        json.dumps({"name": "Carroll Gardens", "source": "nyc_metro", "climate": {"months": months}}) + "\n")
    (d / "catalog_housing_costs.json").write_text(json.dumps({"places": {"nyc::Carroll Gardens|Kings|NY": {"rent": 1}}}))
    (d / "catalog_surroundings.json").write_text(json.dumps({"places": {"nyc::Carroll Gardens|Kings|NY": {
        "income": {"here": 150000, "around": 120000}, "neighbors": ["Park Slope"]}}}))
    monkeypatch.setattr(catalog_api, "DATA_DIR", d)
    monkeypatch.setattr(catalog_api, "CACHE_DIR", cache)
    monkeypatch.setattr(catalog_api, "LIST_JSON", cache / "catalog_list.json")
    monkeypatch.setattr(catalog_api, "LIST_GZ", cache / "catalog_list.json.gz")
    for fn in (catalog_api._climate_index, catalog_api._housing_costs, catalog_api._surroundings, catalog_api._metro_index):
        fn.cache_clear()
    app = FastAPI()
    app.include_router(catalog_api.router)
    return TestClient(app)


def test_slim_drops_unused_keys_keeps_list_paths_and_never_mutates():
    place = {"catalog": {}, "score": _place("A")["score"]}
    before = json.dumps(place, sort_keys=True)
    slim = catalog_api.slim_place(place)
    assert json.dumps(place, sort_keys=True) == before
    pillars = slim["score"]["livability_pillars"]
    assert "total_score_breakdown" not in slim["score"] and "tree_analysis" not in pillars["natural_beauty"]
    assert pillars["natural_beauty"]["v9_breakdown"] == {"gvi_score": 12.0}  # heavy key trimmed to the kept path
    assert pillars["natural_beauty"]["data_quality"] == {"fallback_used": False}
    assert pillars["quality_education"]["breakdown"] == {"split": {"elementary": 80}}  # kept path only
    assert "early_ed_note" not in pillars["quality_education"]["summary"]
    assert pillars["social_fabric"]["score"] == 48.8 and slim["score"]["total_score"] == 70.0


def test_every_kept_path_can_survive_the_unused_key_drop():
    for pillar, paths in catalog_api.KEEP_PATHS.items():
        for path in paths:
            assert not any(seg in catalog_api.UNUSED_KEYS for seg in path), (pillar, path)


def test_slim_returns_place_unchanged_without_pillars():
    place = {"catalog": {}, "score": {"total_score": 1}}
    assert catalog_api.slim_place(place) is place


def test_js_rounding_and_plain_sum_match_javascript():
    # Python 3.12+ sum() gives 49.85 for these; JavaScript reduce gives 49.849999999999994 and Math.round -> 49.8
    vals = [3.66, 3.09, 4.34, 4.11, 3.95, 4.55, 4.47, 4.43, 4.65, 4.39, 3.67, 4.54]
    assert catalog_api._js_round(catalog_api._plain_sum(vals), 1) == 49.8
    assert catalog_api._js_round(2.5, 0) == 3 and catalog_api._js_round(-0.2, 0) == 0


def test_list_endpoint_builds_slim_list_and_serves_gzip(data):
    r = data.get("/catalog/list", headers={"accept-encoding": "gzip"})
    assert r.status_code == 200 and "s-maxage=86400" in r.headers["cache-control"]
    body = r.json()
    assert body["source"] == "all:nyc" and len(body["places"]) == 2
    cg = next(p for p in body["places"] if p["catalog"]["name"] == "Carroll Gardens")
    assert cg["metro"] == "nyc" and cg["housing_cost"] == {"rent": 1} and cg["climate"]["jan_f"] == 31.0
    assert "tree_analysis" not in cg["score"]["livability_pillars"]["natural_beauty"]
    assert cg["surroundings"]["income"] == {"here": 150000, "around": 120000}
    ps = next(p for p in body["places"] if p["catalog"]["name"] == "Park Slope")
    assert "surroundings" not in ps  # no figure: the key is left out, never zero
    plain = data.get("/catalog/list", headers={"accept-encoding": "identity"})
    assert plain.status_code == 200 and plain.json() == body


def test_list_files_are_valid_gzip_json(data):
    n, source = catalog_api.build_list_files()
    assert n == 2 and source == "all:nyc"
    assert json.loads(gzip.decompress(catalog_api.LIST_GZ.read_bytes()))["source"] == "all:nyc"
    assert json.loads(catalog_api.LIST_JSON.read_text())["places"][0]["catalog"]["name"] == "Carroll Gardens"


def test_place_endpoint_returns_unslimmed_detail_and_errors(data):
    ok = data.get("/catalog/place", params={"metro": "nyc", "key": "Carroll Gardens|Kings|NY"})
    assert ok.status_code == 200
    pillars = ok.json()["place"]["score"]["livability_pillars"]
    assert "tree_analysis" in pillars["natural_beauty"] and pillars["social_fabric"]["summary"] == {"orgs_per_1k": 0.35}
    assert pillars["quality_education"]["breakdown"]["heavy"] == "h" * 50
    assert data.get("/catalog/place", params={"metro": "nyc", "key": "Nope|Kings|NY"}).status_code == 404
    assert data.get("/catalog/place", params={"metro": "boston", "key": "x"}).status_code == 400  # not a live metro
    assert data.get("/catalog/place", params={"metro": "zz", "key": "x"}).json() == {"error": "key needs a single metro"}


def test_missing_catalog_reports_missing_source(data, monkeypatch):
    monkeypatch.setattr(catalog_api, "live_metros", lambda: ["la"])
    n, source = catalog_api.build_list_files()
    assert (n, source) == (0, "missing")

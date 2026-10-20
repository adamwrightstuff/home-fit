"""Tests for the metro registry, generated frontend blocks, ship gate, place-list helpers and the finish decision rules."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.metro_agent import finish as fin
from scripts.metro_agent import place_list as pl
from scripts.metro_agent import registry as reg
from scripts.metro_agent import ship as sh


def metros():
    return {
        "aa": {"label": "AA", "long_label": "A metro", "color": "#111111", "bounds": [[-1.5, 2.5], [-0.5, 3.5]], "status": "live",
               "inference": {"state": "TX", "counties": ["Bexar", "Comal"]}},
        "bb": {"label": "BB", "long_label": "B metro", "color": "#222222", "bounds": [[-5.0, 6.0], [-4.0, 7.0]], "status": "building",
               "inference": {"state": "AZ"}},
        "cc": {"label": "CC", "long_label": "C's metro", "color": "#333333", "bounds": [[0.0, 0.0], [1.0, 1.0]], "status": "live",
               "inference": {"state": "NV"}},
    }


# ---------------------------------------------------------------------------------------------- registry
def test_render_includes_only_live_metros():
    out = reg.render(metros())
    assert "'aa'" in out["list"] and "'cc'" in out["list"] and "'bb'" not in out["list"]
    assert "bb:" not in out["meta"] and "bb_metro" not in out["files"] and "bb:" not in out["server"]


def test_render_escapes_quotes_and_orders_county_rules_first():
    out = reg.render(metros())
    assert "C\\'s metro" in out["meta"]
    infer = out["infer"]
    assert infer.index("'TX'") < infer.index("'NV'")          # county rule before the state-only rule
    assert "includes(county)) return 'aa'" in infer and "if (state === 'NV') return 'cc'" in infer
    assert "'bb'" not in infer                                # a building metro never tags places


def test_replace_block_handles_empty_and_filled_blocks_and_keeps_surroundings():
    text = "head\n  // BEGIN GENERATED x (old)\n  // END GENERATED x\ntail\n"
    once = reg._replace_block(text, "x", "  a\n  b", "//")
    assert once.startswith("head\n") and once.endswith("tail\n") and "  a\n  b\n" in once
    twice = reg._replace_block(once, "x", "  c", "//")
    assert "  c\n" in twice and "  a\n" not in twice and twice.count("BEGIN GENERATED x") == 1


def test_replace_block_missing_marker_raises():
    with pytest.raises(ValueError):
        reg._replace_block("nothing here", "x", "body", "//")


def test_cbsa_entries_feed_the_baseline_builder():
    m = {"aa": {"cbsa": {"11111": {"48": ["001", "003"]}}}, "bb": {}}
    counties, keys = reg.cbsa_entries(m)
    assert counties == {"11111": {"48": ["001", "003"]}} and keys == {"11111": "aa_metro"}


def test_real_registry_is_consistent():
    m = reg.load()
    for slug, e in m.items():
        assert e["status"] in reg.STATUSES, slug
        assert len(e["bounds"]) == 2 and e["bounds"][0][0] < e["bounds"][1][0], slug
        assert e["color"].startswith("#"), slug
    assert all(e.get("cbsa") for s, e in m.items() if s not in ("nyc", "la", "sf", "seattle", "austin", "chicago", "philadelphia"))


def test_generated_frontend_blocks_are_up_to_date():
    """The committed frontend files must equal what the registry generates (nothing hand-edited)."""
    assert reg.generate(write=False) == []


# ---------------------------------------------------------------------------------------------- ship gate
def test_ship_refuses_an_unhealthy_metro_and_changes_nothing(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "aa_metro_place_catalog_scores_merged.composites_recomputed.jsonl").write_text("{}\n")
    monkeypatch.setattr(sh, "REPO", tmp_path)
    monkeypatch.setattr(sh.registry, "load", lambda *a, **k: metros())
    calls = []
    monkeypatch.setattr(sh, "_git", lambda *a, **k: calls.append(a) or "")
    logs = []
    code = sh.ship("aa", gate=lambda m: "UNHEALTHY", log=logs.append)
    assert code == 1 and calls == [] and any("NOT SHIPPING" in x for x in logs)


def test_ship_unknown_metro_or_missing_scores(tmp_path, monkeypatch):
    monkeypatch.setattr(sh, "REPO", tmp_path)
    monkeypatch.setattr(sh.registry, "load", lambda *a, **k: metros())
    assert sh.ship("zz", gate=lambda m: "ATTENTION", log=lambda s: None) == 2
    assert sh.ship("aa", gate=lambda m: "ATTENTION", log=lambda s: None) == 2     # no scores file


def test_ship_allowlist_never_includes_another_metros_scores():
    files = sh.files_for("aa")
    assert "data/aa_metro_place_catalog_scores_merged.composites_recomputed.jsonl" in files
    assert not any("bb_metro" in f for f in files)


# ---------------------------------------------------------------------------------------------- place list helpers
def test_norm_and_miles():
    assert pl.norm("St. Petersburg") == pl.norm("Saint Petersburg") == "stpetersburg"
    assert pl.miles(33.4942, -111.9261, 33.4942, -111.9261) == pytest.approx(0, abs=1e-6)
    assert pl.miles(33.0, -112.0, 34.0, -112.0) == pytest.approx(69.0, abs=0.5)


# ---------------------------------------------------------------------------------------------- finish: crime rules
def cand(name, km, why, year=2024):
    return {"name": name, "km": km, "why": why, "data": {"year": year, "violent_per_100k": 10, "population": 1000}}


def result(place, cands, state="TX"):
    return {"place": place, "state": state, "note": "n", "candidates": cands}


def decide(monkeypatch, results, catalog, lsad=None):
    monkeypatch.setattr(fin, "_catalog_rows", lambda metro: catalog)
    return fin.crime_decisions(results, "m", lsad or {})


def test_c1_maps_a_place_to_its_own_police_department(monkeypatch):
    d = decide(monkeypatch, [result("Olmos Park", [cand("Olmos Park Police Department", 2.0, ["named for the place"])])],
               {"Olmos Park": {"type": "suburb"}})[0]
    assert d["action"] == "map" and d["kind"] == "own" and d["agency"] == "Olmos Park Police Department"
    assert "olmos park" in d["keys"] and "olmos park township" in d["keys"]


def test_c1_accepts_names_containing_park_but_not_park_rangers(monkeypatch):
    ok = decide(monkeypatch, [result("Hollywood Park", [cand("Hollywood Park Police Department", 1.0, ["named for the place"])])],
                {"Hollywood Park": {"type": "suburb"}})[0]
    assert ok["action"] == "map"
    bad = decide(monkeypatch, [result("Fort Washington", [cand("State Park Rangers: Fort Washington", 1.0, ["named for the place"])])],
                 {"Fort Washington": {"type": "suburb"}})[0]
    assert bad["action"] == "gap"


def test_c1_rejects_a_same_named_town_far_away(monkeypatch):
    """'Comfort' must not be mapped to 'Point Comfort Police Department' hundreds of miles away."""
    d = decide(monkeypatch, [result("Comfort", [cand("Point Comfort Police Department", 400.0, ["named for the place"])])],
               {"Comfort": {"type": "suburb"}})[0]
    assert d["action"] == "gap" and d["reason"].startswith("C4")


def test_c2_neighborhood_uses_its_citys_police_department(monkeypatch):
    d = decide(monkeypatch, [result("Oak Lawn", [cand("Dallas Police Department", 4.8, ["within 15 km"])])],
               {"Oak Lawn": {"type": "neighborhood", "search_query": "Oak Lawn, Dallas, TX"}})[0]
    assert d["action"] == "map" and d["agency"] == "Dallas Police Department" and d["keys"][0] == "dallas"


def test_c3_county_sheriff_only_for_unincorporated_census_designated_places(monkeypatch):
    sheriff = [cand("Comal County Sheriff's Office", 17.0, ["county agency"])]
    cdp = decide(monkeypatch, [result("Canyon Lake", sheriff)], {"Canyon Lake": {"type": "suburb"}}, {("TX", "Canyon Lake"): "57"})[0]
    assert cdp["action"] == "map" and cdp["kind"] == "county"
    incorporated = decide(monkeypatch, [result("Lucas", sheriff)], {"Lucas": {"type": "suburb"}}, {("TX", "Lucas"): "25"})[0]
    assert incorporated["action"] == "gap"


def test_c4_never_borrows_a_neighbours_numbers(monkeypatch):
    d = decide(monkeypatch, [result("Youngtown", [cand("Goodyear Police Department", 11.8, ["within 15 km"])])],
               {"Youngtown": {"type": "suburb"}}, {("AZ", "Youngtown"): "25"})[0]
    assert d["action"] == "gap" and "Goodyear Police Department" in d["reason"] and "not borrowed" in d["reason"]


def test_agencies_without_data_are_ignored(monkeypatch):
    c = cand("Alpha Police Department", 1.0, ["named for the place"])
    c["data"] = None
    d = decide(monkeypatch, [result("Alpha", [c])], {"Alpha": {"type": "suburb"}})[0]
    assert d["action"] == "gap"


def test_apply_map_writes_keys_for_each_decision(tmp_path, monkeypatch):
    p = tmp_path / "data"
    p.mkdir()
    (p / "crime_agency_map.json").write_text(json.dumps({"_doc": "x", "TX": {}}))
    monkeypatch.setattr(fin, "REPO", tmp_path)
    n = fin.apply_map([{"action": "map", "state": "TX", "kind": "own", "agency": "A PD", "keys": ["a", "a township"]},
                       {"action": "gap", "state": "TX"}])
    m = json.loads((p / "crime_agency_map.json").read_text())
    assert n == 1 and m["TX"]["a"] == {"agency": "A PD", "kind": "own"} and "a township" in m["TX"]


# ---------------------------------------------------------------------------------------------- finish: rule C5 (mismatch)
def scored(name, matched, lat=30.0, lon=-98.0, typ="suburb"):
    return {"success": True, "catalog": {"name": name, "type": typ, "state_abbr": "TX", "lat": str(lat), "lon": str(lon)},
            "score": {"livability_pillars": {"community_safety": {"breakdown": {"agency_name": matched}}}}}


def test_c5_remaps_a_place_scored_with_a_lookalike_agency(monkeypatch):
    monkeypatch.setattr(fin, "_catalog_rows", lambda metro: {"Highland Village": {"type": "suburb"}})
    agencies = [{"agency_name": "Highland Village Police Department", "ori": "X1", "latitude": 30.01, "longitude": -98.0},
                {"agency_name": "Houston Police Department", "ori": "X2", "latitude": 29.7, "longitude": -95.4}]
    rate = lambda ori, kind, yr, name: (5.0, "agency", 1000)  # noqa: E731
    out = fin.mismatch_decisions([scored("Highland Village", "Houston Police Department")], "m", lambda st: agencies, rate, 2024)
    assert len(out) == 1 and out[0]["agency"] == "Highland Village Police Department" and out[0]["reason"].startswith("C5")


def test_c5_leaves_correct_matches_and_far_agencies_alone(monkeypatch):
    monkeypatch.setattr(fin, "_catalog_rows", lambda metro: {"Plano": {"type": "suburb"}, "Comfort": {"type": "suburb"}})
    rate = lambda ori, kind, yr, name: (5.0, "agency", 1000)  # noqa: E731
    ok = fin.mismatch_decisions([scored("Plano", "Plano Police Department")], "m", lambda st: [], rate, 2024)
    far = fin.mismatch_decisions([scored("Comfort", "Kendall County Sheriff's Office")], "m",
                                 lambda st: [{"agency_name": "Point Comfort Police Department", "ori": "Y", "latitude": 28.6, "longitude": -96.5}],
                                 rate, 2024)
    assert ok == [] and far == []


def test_c5_skips_neighborhoods_and_unscored_rows(monkeypatch):
    monkeypatch.setattr(fin, "_catalog_rows", lambda metro: {"Uptown": {"type": "neighborhood"}})
    rows = [scored("Uptown", "Dallas Police Department", typ="neighborhood"), {"success": False, "catalog": {"name": "X", "type": "suburb"}}]
    assert fin.mismatch_decisions(rows, "m", lambda st: [], lambda *a: None, 2024) == []

"""The area type is settled once, before any pillar runs, and the Places top-up is paid for once."""

import pathlib

import pytest

from data_sources import place_context as pc
from data_sources.place_context import PlaceContext, resolve_area_type


def _biz(n, dist=300.0):
    return [{"name": f"b{i}", "distance_m": dist, "lat": 0.0, "lon": 0.0} for i in range(n)]


def _lists(tier1=0, far=0):
    return {"tier1_daily": _biz(tier1), "tier2_social": _biz(far, dist=1300.0), "tier3_culture": [], "tier4_services": []}


def _detect_by_count(lat, lon, *, business_count, **_):
    # stand-in for classify_morphology: more businesses means a denser class
    return "urban_residential" if business_count >= 40 else "suburban"


def _no_completeness(lat, lon, base, area_type, density=None):
    return 0.1


def test_osm_only_when_places_adds_nothing():
    calls = []

    def augment(base, lat, lon, radius, chains, completeness, **kw):
        calls.append((radius, kw.get("area_type")))
        return base, {"used": False, "reason": "completeness_above_threshold"}

    area, source, prov, merged, meta = resolve_area_type(
        1.0, 2.0, city="X", location_input="X", density=3000.0, osm_businesses=_lists(tier1=10),
        built_coverage=None, metro_distance_km=None,
        detect=_detect_by_count, augment=augment, completeness=_no_completeness,
    )
    assert (area, source, prov) == ("suburban", "osm_only", "suburban")
    assert calls == [(float(pc.PREFETCH_RADIUS_M), "suburban")]  # budgeted on the provisional type, one call
    assert merged is not None and meta["used"] is False


def test_places_topup_can_settle_a_denser_type_and_provisional_is_recorded():
    def augment(base, lat, lon, radius, chains, completeness, **kw):
        out = {k: list(v) for k, v in base.items()}
        out["tier1_daily"] += _biz(45)
        return out, {"used": True, "mapped_added": 45}

    area, source, prov, merged, meta = resolve_area_type(
        1.0, 2.0, city=None, location_input=None, density=9000.0, osm_businesses=_lists(tier1=5),
        built_coverage=None, metro_distance_km=None,
        detect=_detect_by_count, augment=augment, completeness=_no_completeness,
    )
    assert prov == "suburban"
    assert area == "urban_residential"
    assert source == "osm_plus_places"
    assert len(merged["tier1_daily"]) == 50


def test_count_for_classification_ignores_businesses_beyond_one_km():
    seen = []

    def detect(lat, lon, *, business_count, **_):
        seen.append(business_count)
        return "suburban"

    resolve_area_type(
        1.0, 2.0, city=None, location_input=None, density=1000.0,
        osm_businesses=_lists(tier1=7, far=30),  # 30 more sit at 1,300 m
        built_coverage=None, metro_distance_km=None, detect=detect,
        augment=lambda base, *a, **k: (base, {"used": False}), completeness=_no_completeness,
    )
    assert seen == [7]


def test_failed_osm_read_means_no_topup_and_nothing_handed_to_amenities():
    def augment(*a, **k):
        raise AssertionError("must not pay for a Places call when the OSM read failed")

    area, source, prov, merged, meta = resolve_area_type(
        1.0, 2.0, city=None, location_input=None, density=500.0, osm_businesses=None,
        built_coverage=None, metro_distance_km=None, detect=_detect_by_count, augment=augment,
    )
    assert merged is None and meta is None and source == "osm_only"


def test_places_failure_falls_back_to_osm_list():
    def augment(*a, **k):
        raise RuntimeError("quota")

    area, source, prov, merged, meta = resolve_area_type(
        1.0, 2.0, city=None, location_input=None, density=500.0, osm_businesses=_lists(tier1=3),
        built_coverage=None, metro_distance_km=None, detect=_detect_by_count, augment=augment,
        completeness=_no_completeness,
    )
    assert source == "osm_only" and len(merged["tier1_daily"]) == 3
    assert meta["used"] is False and "quota" in meta["error"]


def _ctx(businesses):
    return PlaceContext(lat=1.0, lon=2.0, city=None, area_type="suburban", density=1000.0,
                        prefetched_businesses=businesses)


def test_businesses_for_radius_trims_to_the_pillars_own_radius():
    lists = {"tier1_daily": _biz(2, 500.0) + _biz(3, 1400.0), "tier2_social": [], "tier3_culture": [], "tier4_services": []}
    out = _ctx(lists).businesses_for_radius(1200, True, False)
    assert len(out["tier1_daily"]) == 2


@pytest.mark.parametrize("radius,chains,vacation", [(1500, False, False), (1500, True, True), (3000, True, False)])
def test_prefetched_list_does_not_stand_in_when_the_query_would_differ(radius, chains, vacation):
    lists = {"tier1_daily": _biz(2), "tier2_social": [], "tier3_culture": [], "tier4_services": []}
    assert _ctx(lists).businesses_for_radius(radius, chains, vacation) is None


def test_no_prefetched_list_means_the_pillar_reads_for_itself():
    assert _ctx(None).businesses_for_radius(1500, True, False) is None


def test_context_is_frozen():
    with pytest.raises(Exception):
        _ctx(None).area_type = "rural"


def test_amenities_reuses_the_list_and_skips_its_own_places_call(monkeypatch):
    from pillars import neighborhood_amenities as na

    lists = {"tier1_daily": _biz(8, 200.0), "tier2_social": _biz(4, 400.0), "tier3_culture": _biz(2, 600.0), "tier4_services": _biz(3, 700.0)}
    for k, items in lists.items():
        for i, b in enumerate(items):
            b.update({"type": "cafe", "name": f"{k}{i}", "lat": 0.0, "lon": 0.0})
    ctx = PlaceContext(lat=1.0, lon=2.0, city=None, area_type="suburban", density=3000.0,
                       prefetched_businesses=lists, places_meta={"used": True, "mapped_added": 4})

    def no_osm(*a, **k):
        raise AssertionError("amenities must not re-read OSM when the context supplies the list")

    seen = {}

    def spy_augment(data, lat, lon, radius, chains, completeness, **kw):
        seen.update(kw)
        return data, {"used": False, "reason": "already_augmented"}

    monkeypatch.setattr(na.osm_api, "query_local_businesses", no_osm)
    monkeypatch.setattr(na, "maybe_augment_business_data_with_places", spy_augment)
    try:
        na.get_neighborhood_amenities_score(1.0, 2.0, area_type="suburban", density=3000.0, place_context=ctx)
    except Exception:
        pass  # scoring internals are covered elsewhere; this test is about the data hand-off
    assert seen.get("places_already_augmented") is True


def test_main_no_longer_overwrites_the_area_type_after_the_pillars():
    src = (pathlib.Path(__file__).resolve().parents[1] / "main.py").read_text()
    assert "_reclassify_area_type_post_pillars" not in src
    assert "_corrected_area_type" not in src
    assert src.count("'place_context': place_ctx") >= 2


def test_completeness_uses_the_density_it_was_given_and_does_not_refetch(monkeypatch):
    from data_sources import data_quality as dq

    def boom(lat, lon):
        raise AssertionError("must not re-fetch density when the caller supplied it")

    monkeypatch.setattr(dq, "get_population_density", boom)
    # 37,000 people per sq mi gives the urban expectations even though the area type string is not 'urban_core'
    exp = dq.data_quality_manager.get_expected_minimums(1.0, 2.0, "urban_residential", density=37000.0)
    assert exp["business_count"] == 50
    score = pc._default_completeness(1.0, 2.0, _lists(tier1=10), "urban_residential", 37000.0)
    assert score < 0.6  # thin against an urban expectation, so the Places top-up is triggered


def test_expected_minimums_without_density_still_fetches_it(monkeypatch):
    from data_sources import data_quality as dq
    monkeypatch.setattr(dq, "get_population_density", lambda lat, lon: 37000.0)
    assert dq.data_quality_manager.get_expected_minimums(1.0, 2.0, "urban_residential")["business_count"] == 50

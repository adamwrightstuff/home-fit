"""Healthcare: a failed OSM read is no data, never zero facilities or an invented component score (design principles v2, P9)."""
import pytest

import pillars.healthcare_access as hc
from data_sources import data_quality, regional_baselines

EMPTY = {"hospitals": [], "urgent_care": [], "pharmacies": [], "clinics": [], "doctors": []}
NO_PLACES = {"triggered": False, "hospitals_added": 0, "pharmacies_added": 0, "doctors_added": 0, "http_calls": 0}


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    mgr = regional_baselines.regional_baseline_manager
    monkeypatch.setattr(mgr, "_detect_metro_area", lambda *a, **k: None)
    monkeypatch.setattr(mgr, "_get_classification_confidence", lambda *a, **k: 1.0)
    monkeypatch.setattr(data_quality, "detect_area_type", lambda *a, **k: "suburban")
    monkeypatch.setattr(data_quality, "assess_pillar_data_quality",
                        lambda *a, **k: {"confidence": 80, "quality_tier": "good", "completeness": 0.8})
    monkeypatch.setattr(hc, "_npi_specialty_count", lambda *a, **k: 0)
    monkeypatch.setattr(hc, "maybe_augment_healthcare_with_places", lambda *a, **k: dict(NO_PLACES))


def _run():
    return hc.get_healthcare_access_score(38.0, -121.3, area_type="suburban", density=3000.0)


def test_failed_read_raises_so_the_pillar_shows_no_data(monkeypatch):
    monkeypatch.setattr(hc, "_get_osm_healthcare", lambda *a, **k: dict(EMPTY, _query_failed=True))
    with pytest.raises(RuntimeError):
        _run()


def test_successful_empty_read_is_a_real_zero_without_invented_scores(monkeypatch):
    monkeypatch.setattr(hc, "_get_osm_healthcare", lambda *a, **k: dict(EMPTY))
    score, bd = _run()
    parts = bd["breakdown"]
    assert parts["pharmacies"] == 0.0
    assert parts["primary_care"] == 0.0
    assert parts["specialized_care"] == 0.0


def test_failed_read_recovered_by_places_is_flagged_degraded(monkeypatch):
    monkeypatch.setattr(hc, "_get_osm_healthcare", lambda *a, **k: dict(EMPTY, _query_failed=True))
    recovered = dict(NO_PLACES, triggered=True, reason="osm_failed", pharmacies_added=2, hospitals_added=0, doctors_added=0)

    def fake_augment(lat, lon, radius_m, hospitals, urgent_care, pharmacies, clinics, doctors, query_failed):
        pharmacies.extend([{"name": "P1", "distance_km": 0.5}, {"name": "P2", "distance_km": 1.0}])
        return recovered

    monkeypatch.setattr(hc, "maybe_augment_healthcare_with_places", fake_augment)
    score, bd = _run()
    assert bd["data_quality"]["degraded"] is True
    assert "osm_query_failed_recovered_from_google_places" in bd["data_quality"]["degraded_reasons"]
    assert bd["breakdown"]["pharmacies"] > 0.0


def test_no_hard_coded_fallback_component_scores_remain():
    import inspect
    src = inspect.getsource(hc.get_healthcare_access_score)
    assert "apply_pharmacy_fallback" not in src
    assert "apply_primary_care_fallback" not in src

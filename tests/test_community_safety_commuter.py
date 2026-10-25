"""Community safety records an unavailable commuter adjustment instead of silent zeros."""
from pillars import community_safety as cs


def test_unavailable_grid_is_flagged_not_zero(monkeypatch):
    import data_sources.census_api as ca
    monkeypatch.setattr(ca, "estimate_community_safety_disk_population", lambda *a, **k: (5000, {}))
    monkeypatch.setattr(cs, "jobs_in_disk", lambda *a, **k: None)
    radius, ambient, meta = cs._neighborhood_ambient_population(41.88, -87.63, "urban_core", state="IL")
    assert meta["commuter_adjustment"] == "unavailable" and "workplace_jobs_in_radius" not in meta
    assert ambient == 5000


def test_covered_grid_applies_the_adjustment(monkeypatch):
    import data_sources.census_api as ca
    monkeypatch.setattr(ca, "estimate_community_safety_disk_population", lambda *a, **k: (5000, {}))
    monkeypatch.setattr(cs, "jobs_in_disk", lambda *a, **k: (8000.0, 2000.0))
    radius, ambient, meta = cs._neighborhood_ambient_population(30.27, -97.74, "urban_core", state="TX")
    assert meta["commuter_adjustment"] == "applied" and meta["workplace_jobs_in_radius"] == 8000
    assert ambient > 5000

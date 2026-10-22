"""Job access: coverage guard under the national LODES grid, and the offline economic recompute."""

import importlib.util
import os

import pytest

from data_sources import job_accessibility as J

_spec = importlib.util.spec_from_file_location(
    "recompute_econ", os.path.join(os.path.dirname(__file__), "..", "scripts", "catalog", "recompute_economic_job_access_offline.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def test_every_us_metro_core_is_covered_by_the_national_grid():
    for name, lat, lon in [("Boston", 42.36, -71.06), ("Las Vegas", 36.17, -115.14), ("Dallas", 32.78, -96.80),
                           ("Atlanta", 33.75, -84.39), ("Phoenix", 33.45, -112.07), ("Philadelphia", 39.95, -75.17)]:
        score = J.job_access_score(lat, lon)
        assert score is not None and score > 50, name


def test_points_far_from_any_grid_cell_return_no_data_not_zero():
    assert J.job_access_score(36.0, -60.0) is None  # open ocean
    assert J.job_access_score(39.6, -117.5) is None  # rural Nevada, more than COVERAGE_MAX_KM from a cell


def test_dense_core_outscores_exurb_in_the_same_metro():
    assert J.job_access_score(33.75, -84.39) > J.job_access_score(34.35, -84.05)  # Atlanta vs Dawsonville area


def _place(score=33.0, mq=73.4, weight=7.6923076923, ja_old=0.0, lat=42.36, lon=-71.06):
    return {"coordinates": {"lat": lat, "lon": lon},
            "livability_pillars": {"economic_opportunity": {"score": score, "weight": weight, "contribution": 0,
                                                            "summary": {"market_quality_score": mq, "job_access_score": ja_old}}}}


def test_recompute_blends_55_45_and_updates_contribution():
    p = _place()
    info = _mod.recompute_place(p, lambda la, lo: 84.5)
    eo = p["livability_pillars"]["economic_opportunity"]
    assert eo["score"] == round(0.55 * 84.5 + 0.45 * 73.4, 1) == info["after"]
    assert eo["contribution"] == pytest.approx(7.6923076923 * eo["score"] / 100, abs=1e-4)
    assert eo["summary"]["job_access_score"] == 84.5


def test_recompute_falls_back_to_market_quality_without_coverage():
    p = _place()
    _mod.recompute_place(p, lambda la, lo: None)
    eo = p["livability_pillars"]["economic_opportunity"]
    assert eo["score"] == 73.4 and eo["summary"]["job_access_score"] is None


def test_recompute_skips_places_without_stored_market_quality():
    p = _place()
    p["livability_pillars"]["economic_opportunity"]["summary"].pop("market_quality_score")
    assert _mod.recompute_place(p, lambda la, lo: 50.0) is None

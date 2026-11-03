"""Economic opportunity: failures and hard-coded fallbacks are visible, not silent."""
import pillars.economic_opportunity as eo


def test_normalize_records_the_hard_coded_fallback(monkeypatch):
    monkeypatch.setattr(eo, "normalize_national_0_100", lambda **k: None)
    used = []
    score = eo._normalize(metric="emp_pop_ratio", value=60.0, used_fallback=used)
    assert score is not None and used == ["emp_pop_ratio"]


def test_normalize_does_not_record_when_a_baseline_exists(monkeypatch):
    monkeypatch.setattr(eo, "normalize_national_0_100", lambda **k: 61.0)
    used = []
    assert eo._normalize(metric="emp_pop_ratio", value=60.0, used_fallback=used) == 61.0
    assert used == []


def test_job_access_status_ok_none_and_error(monkeypatch):
    import data_sources.job_accessibility as ja
    monkeypatch.setattr(ja, "job_access_score", lambda lat, lon: 72.5)
    assert eo._job_access_with_status(1.0, 2.0) == (72.5, "ok")
    monkeypatch.setattr(ja, "job_access_score", lambda lat, lon: None)
    assert eo._job_access_with_status(1.0, 2.0) == (None, "no_grid_coverage")

    def boom(lat, lon):
        raise OSError("grid file missing")
    monkeypatch.setattr(ja, "job_access_score", boom)
    assert eo._job_access_with_status(1.0, 2.0) == (None, "error")


def test_national_normalization_uses_the_all_all_baseline(monkeypatch):
    import data_sources.normalization as nm
    monkeypatch.setattr(nm, "load_economic_baselines", lambda: {"all": {"all": {"emp_pop_ratio": {"mean": 60.0, "std": 5.0}}}})
    assert nm.normalize_national_0_100(metric="emp_pop_ratio", value=60.0) == 50.0
    hi = nm.normalize_national_0_100(metric="emp_pop_ratio", value=70.0)
    assert hi > 95 and nm.normalize_national_0_100(metric="emp_pop_ratio", value=70.0, invert=True) == 100 - hi
    assert nm.normalize_national_0_100(metric="wage_p25_annual", value=40000.0) is None  # no baseline: caller flags the fallback
    assert nm.normalize_national_0_100(metric="emp_pop_ratio", value=None) is None


def test_market_components_blend_and_anchor_floor():
    sub = {"emp_pop_ratio": 60.0, "log10_employment": 80.0, "log10_establishments": 60.0, "estabs_per_1k": 50.0,
           "wage_p25_annual": 40.0, "qcew_employment_growth_pct": 10.0, "net_estab_entry_per_1k": 50.0,
           "wage_p75_annual": 70.0, "industry_diversity": 60.0, "anchored_balance": 80.0}
    out = eo.compute_market_components(sub)
    assert sub["scale"] == 70.0 and sub["qcew_employment_growth_pct"] == 40.0  # anchor floor lifts weak growth
    density = (0.25 * 60 + 0.30 * 70 + 0.25 * 50 + 0.20 * 40)
    mobility = (0.40 * 40 + 0.35 * 50 + 0.25 * 70)
    ecosystem = (0.70 * 60 + 0.30 * 50)
    resilience = (0.60 * 60 + 0.40 * 80)
    assert abs(out["density_score"] - density) < 1e-9 and abs(out["mobility_score"] - mobility) < 1e-9
    assert abs(out["base_final_score"] - (0.40 * density + 0.15 * mobility + 0.20 * ecosystem + 0.25 * resilience)) < 1e-9


def _geo():
    from data_sources.economic_security_data import EconomicGeo
    return EconomicGeo(level="cbsa", name="Test Metro", state_fips="36", county_fips="061", cbsa_code="35620")


def _stub_market_data(monkeypatch, normalized=50.0):
    monkeypatch.setattr(eo, "get_economic_geography", lambda *a, **k: _geo())
    monkeypatch.setattr(eo, "fetch_acs_profile_dp03", lambda **k: {"DP03_0001E": 1000, "DP03_0004E": 600})
    monkeypatch.setattr(eo, "fetch_acs_table", lambda **k: {"B01001_001E": 2000})
    monkeypatch.setattr(eo, "fetch_bds_establishment_dynamics", lambda **k: {})
    monkeypatch.setattr(eo, "fetch_cbp_employment", lambda **k: {})
    monkeypatch.setattr(eo.bls_data, "get_oews_wage_distribution", lambda area: None)
    monkeypatch.setattr(eo, "normalize_national_0_100", lambda **k: normalized)
    monkeypatch.setattr(eo, "assess_pillar_data_quality", lambda *a, **k: {"confidence": 80})


def test_unresolved_geography_raises_instead_of_scoring_zero(monkeypatch):
    import pytest
    monkeypatch.setattr(eo, "get_economic_geography", lambda *a, **k: None)
    with pytest.raises(eo.EconomicDataUnavailable, match="economic_geography_unresolved"):
        eo.get_economic_opportunity_score(40.7, -74.0)


def test_job_access_read_error_raises_instead_of_dropping_to_market_quality(monkeypatch):
    import pytest
    _stub_market_data(monkeypatch)
    monkeypatch.setattr(eo, "_job_access_with_status", lambda lat, lon: (None, "error"))
    with pytest.raises(eo.EconomicDataUnavailable, match="economic_job_access_error"):
        eo.get_economic_opportunity_score(40.7, -74.0)


def test_nothing_measurable_raises_instead_of_scoring_zero(monkeypatch):
    import pytest
    _stub_market_data(monkeypatch, normalized=None)
    monkeypatch.setattr(eo, "_fallback_normalize", lambda *a, **k: None)
    monkeypatch.setattr(eo, "_job_access_with_status", lambda lat, lon: (80.0, "ok"))
    with pytest.raises(eo.EconomicDataUnavailable, match="economic_market_quality_unmeasurable"):
        eo.get_economic_opportunity_score(40.7, -74.0)


def test_grid_not_covering_the_point_is_degraded_not_a_failure(monkeypatch):
    _stub_market_data(monkeypatch)
    monkeypatch.setattr(eo, "_job_access_with_status", lambda lat, lon: (None, "no_grid_coverage"))
    score, details = eo.get_economic_opportunity_score(40.7, -74.0)
    assert score == details["summary"]["market_quality_score"]
    assert details["data_quality"]["degraded"] is True
    assert any("economic_job_access_no_grid_coverage" in r for r in details["data_quality"]["degraded_reasons"])


def test_score_does_not_depend_on_area_type_label(monkeypatch):
    _stub_market_data(monkeypatch)
    monkeypatch.setattr(eo, "_job_access_with_status", lambda lat, lon: (77.0, "ok"))
    scores = {eo.get_economic_opportunity_score(40.7, -74.0, area_type=t)[0] for t in ("urban_core", "suburban", "rural", None)}
    assert len(scores) == 1

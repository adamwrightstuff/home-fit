"""Economic opportunity: failures and hard-coded fallbacks are visible, not silent."""
import pillars.economic_opportunity as eo


def test_normalize_records_the_hard_coded_fallback(monkeypatch):
    monkeypatch.setattr(eo, "normalize_national_0_100", lambda **k: None)
    used = []
    score = eo._normalize(metric="emp_pop_ratio", value=60.0, division="pacific", area_bucket="urban", used_fallback=used)
    assert score is not None and used == ["emp_pop_ratio"]


def test_normalize_does_not_record_when_a_baseline_exists(monkeypatch):
    monkeypatch.setattr(eo, "normalize_national_0_100", lambda **k: 61.0)
    used = []
    assert eo._normalize(metric="emp_pop_ratio", value=60.0, division="pacific", area_bucket="urban", used_fallback=used) == 61.0
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

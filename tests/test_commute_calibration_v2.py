"""Offline tests for commute calibration v2 (planted effects with known answers; no network)."""

import numpy as np
import pandas as pd

from scripts.baselines import build_commute_calibration as v1
from scripts.baselines import build_commute_calibration_v2 as v2


def _frame(n_states=40, per_state=60, seed=3, truth=1.5, noise=0.4, collinear=True):
    """Counties where the outcome depends only on the 45+ minute commute share (true coef = truth)."""
    rng = np.random.default_rng(seed)
    n = n_states * per_state
    states = np.repeat([f"{s:02d}" for s in range(1, n_states + 1)], per_state)
    base = rng.uniform(0.02, 0.2, n)  # latent 45-59 share
    if collinear:  # 60-89 and 90+ are near-exact multiples of 45-59, as in real workforces
        m60 = 0.8 * base + rng.normal(0, 0.002, n)
        m90 = 0.2 * base + rng.normal(0, 0.002, n)
    else:
        m60, m90 = rng.uniform(0.01, 0.1, n), rng.uniform(0.0, 0.04, n)
    m30 = rng.uniform(0.05, 0.25, n)
    m15 = rng.uniform(0.1, 0.3, n)
    lt15 = np.clip(1 - m15 - m30 - base - m60 - m90, 0.01, None)
    df = pd.DataFrame({"fips": [f"{s}{i:03d}" for i, s in enumerate(states)]})
    df["share_lt15"], df["share_m15_29"], df["share_m30_44"] = lt15, m15, m30
    df["share_m45_59"], df["share_m60_89"], df["share_m90p"] = base, m60, m90
    df["share_45p"] = base + m60 + m90
    df["share_30p"] = df["share_45p"] + m30
    df["share_60p"] = m60 + m90
    df["mean_minutes"] = 20 + 100 * df["share_45p"]
    for c, (a, b) in {"rent_burden_30p": (0.3, 0.6), "owner_burden_30p": (0.1, 0.4), "wfh_share": (0.02, 0.2),
                      "poverty_rate": (0.05, 0.3), "bachelors_share": (0.1, 0.5), "median_age": (30, 50),
                      "log_median_income": (10.3, 11.6)}.items():
        df[c] = rng.uniform(a, b, n)
    df["value"] = 10 + 6 * df["poverty_rate"] + truth * df["share_45p"] + rng.normal(0, noise, n)
    df["pop"] = rng.integers(5_000, 400_000, n)
    df["measure"] = "MHLTH"
    return df


def test_cumulative_recovers_truth_where_binned_design_fails():
    truth = 20.0
    df = _frame(truth=truth, noise=0.3)
    # Cumulative design: one exposure, recovered tightly.
    d, controls = v2._prepare(df, "MHLTH", ["share_45p"], v2.BASE_CONTROLS)
    est = v2.fit_model(d, ["share_45p"], v2.BASE_CONTROLS)["share_45p"]
    assert abs(est - truth) < 1.5, est
    # Old binned design: bins 45-59, 60-89, 90+ are near-collinear, so individual effects are unidentified.
    old = v1.fit_outcome(df, "MHLTH", state_fe=True)
    errs = [abs(old["coefficients"][f"share_{b}"][0] - truth) for b in ("m45_59", "m60_89", "m90p")]
    ses = [old["coefficients"][f"share_{b}"][1] for b in ("m45_59", "m60_89", "m90p")]
    se_cum = v2.fit_model  # noqa: F841 (cumulative SE is checked via the bootstrap test)
    assert max(ses) > 3.0 and max(errs) > 3.0, (errs, ses)  # binned estimates are wild; cumulative error is < 1.5


def test_bootstrap_interval_covers_known_coefficient_and_excludes_zero():
    truth = 8.0
    df = _frame(truth=truth, noise=0.5, collinear=False)
    d, controls = v2._prepare(df, "MHLTH", ["share_45p"], v2.BASE_CONTROLS)
    ci = v2.cluster_bootstrap(d, ["share_45p"], controls, n_boot=500)["share_45p"]
    assert ci[0] < truth < ci[1], ci
    assert ci[0] > 0


def test_bootstrap_interval_includes_zero_when_no_effect():
    df = _frame(truth=0.0, noise=1.0, collinear=False, seed=11)
    d, controls = v2._prepare(df, "MHLTH", ["share_45p"], v2.BASE_CONTROLS)
    lo, hi = v2.cluster_bootstrap(d, ["share_45p"], controls, n_boot=500)["share_45p"]
    assert lo < 0 < hi


def test_leave_one_region_out_signs_stable_for_planted_effect():
    df = _frame(truth=5.0, noise=0.4, collinear=False)
    d, controls = v2._prepare(df, "MHLTH", ["share_45p"], v2.BASE_CONTROLS)
    d = d.copy()
    d["region"] = ["Northeast", "Midwest", "South", "West"] * (len(d) // 4)
    loro = v2.leave_one_region_out(d, ["share_45p"], controls)
    assert set(loro) == set(v2.REGIONS)
    assert all(f["share_45p"] > 0 for f in loro.values())


def test_gate_rejects_beneficial_or_single_outcome_effects():
    est = lambda v, sup: {"estimate": v, "ci95": [v - 1, v + 1], "supported": sup}
    mk = lambda v, sup: {e: {e: est(v, sup)} for e in v2.EXPOSURES}
    result = {"outcomes": {
        "MHLTH": {"single": mk(-1.0, True), "spread_p90_p10": 5.0},
        "DEPRESSION": {"single": mk(-2.0, True), "spread_p90_p10": 8.0},
        "SLEEP": {"single": mk(3.0, True), "spread_p90_p10": 10.0},
    }}
    assert v2.derive_curve(result, v2.pass_table(result)) is None  # only one harmful outcome


def test_gate_produces_monotone_curve_with_at_most_four_points():
    est = lambda v: {"estimate": v, "ci95": [v * 0.5, v * 1.5], "supported": True}
    single = {e: {e: est(2.0 * (1 + i))} for i, e in enumerate(v2.EXPOSURES)}
    result = {"outcomes": {m: {"single": single, "spread_p90_p10": 8.0} for m in ("MHLTH", "SLEEP", "DEPRESSION")}}
    curve = v2.derive_curve(result, v2.pass_table(result))
    scores = [p["score"] for p in curve["points"]]
    assert len(scores) <= 4 and scores[0] == 100.0
    assert all(a >= b for a, b in zip(scores, scores[1:]))


def test_acs_features_cumulative_shares_mean_minutes_and_65p():
    raw = {"fips": ["36061"], "tt_total": [100.0], "agg_time": [3000.0],
           "tt_0": [10.0], "tt_1": [10.0], "tt_2": [10.0], "tt_3": [20.0], "tt_4": [10.0], "tt_5": [5.0],
           "rent_total": [100.0], "rent_nc": [10.0], "own_total": [50.0], "own_nc": [0.0],
           "workers": [200.0], "wfh": [20.0], "pov_total": [1000.0], "pov_below": [150.0],
           "edu_total": [800.0], "edu_ba": [100.0], "edu_ma": [50.0], "edu_pr": [10.0], "edu_dr": [10.0],
           "median_age": [38.0], "median_income": [80000.0], "home_value": [400000.0], "population": [10000.0],
           "tenure_total": [400.0], "renters": [100.0], "sex_age_total": [10000.0], "land_sqmi": [10.0]}
    for i in range(4):
        raw[f"rent_b{i}"], raw[f"own_b{i}"] = [10.0], [5.0 if i in (0, 3) else 0.0]
    for i in range(12):
        raw[f"age65_{i}"] = [100.0]
    f = v2.acs_features_v2(pd.DataFrame(raw)).iloc[0]
    assert abs(f["share_30p"] - 0.65) < 1e-9
    assert abs(f["share_45p"] - 0.35) < 1e-9
    assert abs(f["share_60p"] - 0.15) < 1e-9
    assert abs(f["mean_minutes"] - 30.0) < 1e-9
    assert abs(f["share_65p"] - 0.12) < 1e-9
    assert abs(f["renter_share"] - 0.25) < 1e-9
    assert abs(f["log_density"] - np.log(1000.0)) < 1e-9

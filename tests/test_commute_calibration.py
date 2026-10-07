"""Offline tests for the commute calibration's estimator and feature math (no network)."""

import numpy as np
import pandas as pd

from scripts.baselines import build_commute_calibration as cc


def _synthetic(n=3000, seed=7):
    """Counties whose outcome is built from known bin effects, so the fit can be checked."""
    rng = np.random.default_rng(seed)
    shares = rng.dirichlet([8, 4, 2, 1, 0.5, 0.2], size=n)  # lt15, 15-29, 30-44, 45-59, 60-89, 90+
    truth = {"m15_29": 0.5, "m30_44": 2.0, "m45_59": 4.0, "m60_89": 7.0, "m90p": 6.0}  # 90+ dips: non-monotone
    df = pd.DataFrame({"fips": [f"{(i % 40) + 1:02d}{i:03d}"[:5] for i in range(n)]})
    for j, b in enumerate(cc.TIME_BINS):
        df[f"share_{b}"] = shares[:, j]
    df["rent_burden_30p"] = rng.uniform(0.3, 0.6, n)
    df["owner_burden_30p"] = rng.uniform(0.1, 0.4, n)
    df["wfh_share"] = rng.uniform(0.02, 0.2, n)
    df["poverty_rate"] = rng.uniform(0.05, 0.3, n)
    df["bachelors_share"] = rng.uniform(0.1, 0.5, n)
    df["median_age"] = rng.uniform(30, 50, n)
    df["log_median_income"] = rng.uniform(10.3, 11.6, n)
    y = 12 + 8 * df["poverty_rate"] + 3 * df["rent_burden_30p"]
    for b, c in truth.items():
        y = y + c * df[f"share_{b}"]
    df["value"] = y + rng.normal(0, 0.3, n)
    df["pop"] = rng.integers(5_000, 500_000, n)
    df["measure"] = "MHLTH"
    return df, truth


def test_wls_recovers_known_bin_effects():
    df, truth = _synthetic()
    fit = cc.fit_outcome(df, "MHLTH", state_fe=False)
    for b, c in truth.items():
        est, se = fit["coefficients"][f"share_{b}"]
        assert abs(est - c) < max(4 * se, 0.5), (b, est, c)


def test_curve_is_monotone_and_flags_shape_adjustments():
    df, _ = _synthetic()
    curve = cc.harm_to_curve(cc.fit_outcome(df, "MHLTH", state_fe=False))
    scores = [p["score"] for p in curve["points"]]
    assert scores[0] == 100.0
    assert all(a >= b for a, b in zip(scores, scores[1:]))
    assert "m90p" in curve["shape_adjusted_bins"]  # the synthetic 90+ bin is less harmful than 60-89


def test_acs_features_shares_and_burden():
    raw = pd.DataFrame([{
        "fips": "36061", "tt_total": 100.0,
        **{f"tt_{b}_{i}": (10.0 if b == "lt15" else 0.0) for b, labs in cc.TIME_BINS.items() for i in range(len(labs))},
        "rent_total": 100.0, "rent_nc": 10.0, "rent_b0": 10.0, "rent_b1": 10.0, "rent_b2": 10.0, "rent_b3": 15.0,
        "own_total": 50.0, "own_nc": 0.0, "own_b0": 5.0, "own_b1": 0.0, "own_b2": 0.0, "own_b3": 5.0,
        "workers": 200.0, "wfh": 20.0, "pov_total": 1000.0, "pov_below": 150.0,
        "edu_total": 800.0, "edu_ba": 100.0, "edu_ma": 50.0, "edu_pr": 10.0, "edu_dr": 10.0,
        "median_age": 38.0, "median_income": 80000.0,
    }])
    f = cc.acs_features(raw).iloc[0]
    assert abs(f["share_lt15"] - 0.3) < 1e-9
    assert abs(f["wfh_share"] - 0.1) < 1e-9
    assert abs(f["rent_burden_30p"] - 45 / 90) < 1e-9
    assert abs(f["owner_burden_30p"] - 10 / 50) < 1e-9
    assert abs(f["poverty_rate"] - 0.15) < 1e-9
    assert abs(f["bachelors_share"] - 170 / 800) < 1e-9

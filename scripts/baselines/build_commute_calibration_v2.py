#!/usr/bin/env python3
"""
Second-pass commute calibration (v2). v1 (build_commute_calibration.py) is left untouched.

v1 regressed county health outcomes on five travel-time bin shares. Those bins are slices of the
same workforce and are collinear, so their effects zigzagged. v2 replaces them with CUMULATIVE
exposures: the share of workers (B08303, which excludes people working from home) commuting 30+,
45+ and 60+ minutes, plus the continuous mean one-way commute in minutes (B08013 aggregate travel
time divided by the non-WFH worker count). Each exposure is fitted one at a time, and the three
shares are also fitted jointly.

Controls are strengthened against wealth / place-type confounding: log population, log population
density (Census gazetteer land area), log median home value, income and income squared, renter
share, 65+ share, plus WFH share, poverty, bachelors share, median age, rent and owner burden, and
state fixed effects. Fits are weighted by county population.

Robustness decides what counts: an exposure is SUPPORTED for an outcome only if its coefficient has
the same sign in the full fit and in every leave-one-Census-region-out fit AND its state-clustered
bootstrap 95% interval excludes zero. A coarse monotone commute score (at most four points) is
derived only if at least one exposure is supported for at least two of the three outcomes.

County fits are ecological (they describe places, not individuals) and PLACES estimates are
model-based.

Usage (project root; needs data.cdc.gov, api.census.gov and www2.census.gov; CENSUS_API_KEY from env):
  PYTHONPATH=. python3 scripts/baselines/build_commute_calibration_v2.py \\
    --output data/commute_calibration_v2.json
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import zipfile
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import requests

from scripts.baselines.build_commute_calibration import (
    ACS_YEAR,
    OUTCOMES,
    _find,
    _get,
    _group_vars,
    fetch_places_county,
)

GAZETTEER_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    f"{ACS_YEAR}_Gazetteer/{ACS_YEAR}_Gaz_counties_national.zip"
)

EXPOSURES = ["share_30p", "share_45p", "share_60p", "mean_minutes"]
SHARE_EXPOSURES = ["share_30p", "share_45p", "share_60p"]
THRESHOLD_MINUTES = {"share_30p": 30, "share_45p": 45, "share_60p": 60}
BURDEN = ["rent_burden_30p", "owner_burden_30p"]
BASE_CONTROLS = ["wfh_share", "poverty_rate", "bachelors_share", "median_age", "log_median_income"]
EXTRA_CONTROLS = ["log_median_income_sq", "log_population", "log_density", "log_home_value", "renter_share", "share_65p"]
FULL_CONTROLS = BASE_CONTROLS + EXTRA_CONTROLS

# Per-unit scaling for reporting: shares per 10 points, mean minutes per 5 minutes.
REPORT_STEP = {"share_30p": 0.10, "share_45p": 0.10, "share_60p": 0.10, "mean_minutes": 5.0}

REGIONS: Dict[str, List[str]] = {
    "Northeast": ["09", "23", "25", "33", "44", "50", "34", "36", "42"],
    "Midwest": ["17", "18", "26", "39", "55", "19", "20", "27", "29", "31", "38", "46"],
    "South": ["10", "11", "12", "13", "24", "37", "45", "51", "54", "01", "21", "28", "47", "05", "22", "40", "48"],
    "West": ["04", "08", "16", "30", "32", "35", "49", "56", "02", "06", "15", "41", "53"],
}
STATE_TO_REGION = {s: r for r, ss in REGIONS.items() for s in ss}

MIN_BOOTSTRAP = 500


# --------------------------------------------------------------------------- fetching

def fetch_land_area(timeout: int = 60) -> Optional[pd.DataFrame]:
    """County land area (sq mi) from the Census gazetteer; None if the host is unreachable."""
    try:
        r = requests.get(GAZETTEER_URL, timeout=timeout)
        r.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            name = [n for n in z.namelist() if n.endswith(".txt")][0]
            g = pd.read_csv(z.open(name), sep="\t", dtype={"GEOID": str})
        g.columns = [c.strip() for c in g.columns]
        g["fips"] = g["GEOID"].str.zfill(5)
        return g[["fips", "ALAND_SQMI"]].rename(columns={"ALAND_SQMI": "land_sqmi"})
    except Exception as exc:  # density is optional; the caller records its absence
        print(f"WARNING: land area unavailable ({exc}); log_density dropped", file=sys.stderr)
        return None


def fetch_acs_counties_v2(year: int = ACS_YEAR, api_key: Optional[str] = None) -> Tuple[pd.DataFrame, Dict[str, str]]:
    wanted: Dict[str, str] = {}
    t = _group_vars("B08303", year)
    wanted["tt_total"] = _find(t, "Total:", must_not=["minutes"])
    for i, lab in enumerate(["30 to 34 minutes", "35 to 39 minutes", "40 to 44 minutes",
                             "45 to 59 minutes", "60 to 89 minutes", "90 or more minutes"]):
        wanted[f"tt_{i}"] = _find(t, lab)

    wanted["agg_time"] = "B08013_001E"
    r = _group_vars("B25070", year)
    wanted["rent_total"] = _find(r, "Total:", must_not=["percent", "Not computed"])
    wanted["rent_nc"] = _find(r, "Not computed")
    o = _group_vars("B25091", year)
    wanted["own_total"] = _find(o, "with a mortgage", must_not=["percent", "Not computed", "without"])
    wanted["own_nc"] = _find(o, "with a mortgage", "Not computed", must_not=["without"])
    for i, lab in enumerate(["30.0 to 34.9 percent", "35.0 to 39.9 percent", "40.0 to 49.9 percent", "50.0 percent or more"]):
        wanted[f"rent_b{i}"] = _find(r, lab)
        wanted[f"own_b{i}"] = _find(o, "with a mortgage", lab, must_not=["without"])

    w = _group_vars("B08301", year)
    wanted["workers"] = _find(w, "Total:", must_not=["Total:!!"])
    wanted["wfh"] = _find(w, "Worked from home")
    p = _group_vars("B17001", year)
    wanted["pov_total"] = _find(p, "Total:", must_not=["Total:!!"])
    wanted["pov_below"] = _find(p, "below poverty level", must_not=["Male", "Female", "years", "Not"])
    e = _group_vars("B15003", year)
    wanted["edu_total"] = _find(e, "Total:", must_not=["Total:!!"])
    for k, lab in {"edu_ba": "Bachelor's degree", "edu_ma": "Master's degree",
                   "edu_pr": "Professional school degree", "edu_dr": "Doctorate degree"}.items():
        wanted[k] = _find(e, lab)
    wanted["median_age"] = "B01002_001E"
    wanted["median_income"] = "B19013_001E"
    wanted["home_value"] = "B25077_001E"
    wanted["population"] = "B01003_001E"
    wanted["tenure_total"] = "B25003_001E"
    wanted["renters"] = "B25003_003E"
    wanted["sex_age_total"] = "B01001_001E"
    for i, code in enumerate([20, 21, 22, 23, 24, 25, 44, 45, 46, 47, 48, 49]):
        wanted[f"age65_{i}"] = f"B01001_{code:03d}E"

    names = list(wanted)
    frames = []
    for i in range(0, len(names), 40):
        chunk = names[i:i + 40]
        params = {"get": ",".join(wanted[n] for n in chunk), "for": "county:*", "in": "state:*"}
        if api_key:
            params["key"] = api_key
        data = _get(f"https://api.census.gov/data/{year}/acs/acs5", params)
        df = pd.DataFrame(data[1:], columns=data[0])
        df["fips"] = df["state"] + df["county"]
        df = df.rename(columns={wanted[n]: n for n in chunk}).drop(columns=["state", "county"])
        frames.append(df.set_index("fips"))
    raw = pd.concat(frames, axis=1).apply(pd.to_numeric, errors="coerce")
    raw[raw < -1_000_000] = np.nan
    raw = raw.reset_index()
    land = fetch_land_area()
    if land is not None:
        raw = raw.merge(land, on="fips", how="left")
    return acs_features_v2(raw), {"agg_time_label": "B08013_001E: Aggregate travel time to work (in minutes), workers 16+ who did not work at home"}


def acs_features_v2(raw: pd.DataFrame) -> pd.DataFrame:
    """Raw ACS counts -> model features (pure; tested offline)."""
    f = pd.DataFrame({"fips": raw["fips"]})
    tt = raw["tt_total"].replace(0, np.nan)
    f["share_30p"] = sum(raw[f"tt_{i}"] for i in range(0, 6)) / tt
    f["share_45p"] = sum(raw[f"tt_{i}"] for i in range(3, 6)) / tt
    f["share_60p"] = sum(raw[f"tt_{i}"] for i in range(4, 6)) / tt
    f["mean_minutes"] = raw["agg_time"] / tt
    f["wfh_share"] = raw["wfh"] / raw["workers"].replace(0, np.nan)
    rent_den = (raw["rent_total"] - raw["rent_nc"]).replace(0, np.nan)
    f["rent_burden_30p"] = sum(raw[f"rent_b{i}"] for i in range(4)) / rent_den
    own_den = (raw["own_total"] - raw["own_nc"]).replace(0, np.nan)
    f["owner_burden_30p"] = sum(raw[f"own_b{i}"] for i in range(4)) / own_den
    f["poverty_rate"] = raw["pov_below"] / raw["pov_total"].replace(0, np.nan)
    f["bachelors_share"] = (raw["edu_ba"] + raw["edu_ma"] + raw["edu_pr"] + raw["edu_dr"]) / raw["edu_total"].replace(0, np.nan)
    f["median_age"] = raw["median_age"]
    inc = np.log(raw["median_income"].where(raw["median_income"] > 0))
    f["log_median_income"] = inc
    f["log_median_income_sq"] = (inc - 11.0) ** 2  # centred near the county median to limit collinearity
    f["log_population"] = np.log(raw["population"].where(raw["population"] > 0))
    if "land_sqmi" in raw.columns:
        f["log_density"] = np.log((raw["population"] / raw["land_sqmi"]).where(raw["land_sqmi"] > 0).where(raw["population"] > 0))
    f["log_home_value"] = np.log(raw["home_value"].where(raw["home_value"] > 0))
    f["renter_share"] = raw["renters"] / raw["tenure_total"].replace(0, np.nan)
    f["share_65p"] = sum(raw[f"age65_{i}"] for i in range(12)) / raw["sex_age_total"].replace(0, np.nan)
    return f


# --------------------------------------------------------------------------- estimation

def _wls_beta(X: np.ndarray, y: np.ndarray, w: np.ndarray) -> np.ndarray:
    sw = np.sqrt(w)
    Xw = X * sw[:, None]
    return np.linalg.pinv(Xw.T @ Xw) @ (Xw.T @ (y * sw))


def _prepare(df: pd.DataFrame, outcome: str, exposures: Sequence[str], controls: Sequence[str]) -> Tuple[pd.DataFrame, List[str]]:
    controls = [c for c in controls if c in df.columns]
    d = df[df["measure"] == outcome].dropna(subset=list(exposures) + BURDEN + controls + ["value"]).copy()
    d["w"] = d["pop"].fillna(d["pop"].median()).clip(lower=1)
    d["state"] = d["fips"].str[:2]
    d["region"] = d["state"].map(STATE_TO_REGION)
    return d, controls


def _design(d: pd.DataFrame, exposures: Sequence[str], controls: Sequence[str]) -> Tuple[np.ndarray, List[str]]:
    feats = list(exposures) + BURDEN + list(controls)
    cols = [d[c].to_numpy(float) for c in feats]
    names = list(feats)
    for s in sorted(d["state"].unique())[1:]:
        cols.append((d["state"] == s).to_numpy(float))
        names.append(f"state_{s}")
    return np.column_stack([np.ones(len(d))] + cols), ["intercept"] + names


def fit_model(d: pd.DataFrame, exposures: Sequence[str], controls: Sequence[str]) -> Dict[str, float]:
    X, names = _design(d, exposures, controls)
    beta = _wls_beta(X, d["value"].to_numpy(float), d["w"].to_numpy(float))
    return {n: float(b) for n, b in zip(names, beta) if not n.startswith("state_")}


def leave_one_region_out(d: pd.DataFrame, exposures: Sequence[str], controls: Sequence[str]) -> Dict[str, Dict[str, float]]:
    out = {}
    for region in REGIONS:
        sub = d[d["region"] != region]
        if len(sub) < 200:
            continue
        out[region] = fit_model(sub, exposures, controls)
    return out


def cluster_bootstrap(d: pd.DataFrame, exposures: Sequence[str], controls: Sequence[str],
                      n_boot: int = MIN_BOOTSTRAP, seed: int = 20260101) -> Dict[str, Tuple[float, float]]:
    """State-clustered bootstrap: resample whole states with replacement; percentile 95% intervals."""
    X, names = _design(d, exposures, controls)
    y, w = d["value"].to_numpy(float), d["w"].to_numpy(float)
    states = d["state"].to_numpy()
    uniq = np.unique(states)
    members = [np.flatnonzero(states == s) for s in uniq]
    rng = np.random.default_rng(seed)
    keep = [i for i, n in enumerate(names) if n in exposures or n in BURDEN]
    draws = np.empty((n_boot, len(keep)))
    for b in range(n_boot):
        pick = rng.integers(0, len(uniq), len(uniq))
        idx = np.concatenate([members[i] for i in pick])
        draws[b] = _wls_beta(X[idx], y[idx], w[idx])[keep]
    return {names[k]: (float(np.percentile(draws[:, j], 2.5)), float(np.percentile(draws[:, j], 97.5)))
            for j, k in enumerate(keep)}


def assess(d: pd.DataFrame, exposures: Sequence[str], controls: Sequence[str], n_boot: int) -> dict:
    full = fit_model(d, exposures, controls)
    loro = leave_one_region_out(d, exposures, controls)
    ci = cluster_bootstrap(d, exposures, controls, n_boot)
    res = {}
    for e in list(exposures) + BURDEN:
        est = full[e]
        signs = {r: float(np.sign(f[e])) for r, f in loro.items()}
        same_sign = bool(est != 0 and all(s == np.sign(est) for s in signs.values()) and len(signs) == len(REGIONS))
        lo, hi = ci[e]
        excl = bool(lo > 0 or hi < 0)
        res[e] = {
            "estimate": round(est, 4), "ci95": [round(lo, 4), round(hi, 4)],
            "loro_estimates": {r: round(f[e], 4) for r, f in loro.items()},
            "same_sign_all_regions": same_sign, "ci_excludes_zero": excl,
            "supported": bool(same_sign and excl and e in exposures),
        }
    return res


def _spread(d: pd.DataFrame) -> float:
    p10, p90 = np.percentile(d["value"], [10, 90])
    return float(p90 - p10)


def run(df: pd.DataFrame, n_boot: int = MIN_BOOTSTRAP) -> dict:
    out = {"outcomes": {}}
    for m, label in OUTCOMES.items():
        if (df["measure"] == m).sum() < 100:
            continue
        d, controls = _prepare(df, m, EXPOSURES, FULL_CONTROLS)
        o = {"label": label, "n": int(len(d)), "spread_p90_p10": round(_spread(d), 3),
             "mean": round(float(np.average(d["value"], weights=d["w"])), 3), "single": {}, "joint": None}
        for e in EXPOSURES:
            o["single"][e] = assess(d, [e], controls, n_boot)
        o["joint"] = assess(d, SHARE_EXPOSURES, controls, n_boot)
        # Owner-burden sign check: v1-style controls vs strengthened controls, same sample and exposure.
        d_b, _ = _prepare(df, m, ["mean_minutes"], FULL_CONTROLS)
        base = fit_model(d_b, ["mean_minutes"], BASE_CONTROLS)
        full = fit_model(d_b, ["mean_minutes"], controls)
        o["owner_burden_check"] = {
            "base_controls_pp": round(base["owner_burden_30p"], 3), "strong_controls_pp": round(full["owner_burden_30p"], 3),
            "rent_base_pp": round(base["rent_burden_30p"], 3), "rent_strong_pp": round(full["rent_burden_30p"], 3),
        }
        out["outcomes"][m] = o
    return out


def pass_table(result: dict) -> Dict[str, Dict[str, bool]]:
    return {e: {m: o["single"][e][e]["supported"] for m, o in result["outcomes"].items()} for e in EXPOSURES}


def harmful_table(result: dict, table: Dict[str, Dict[str, bool]]) -> Dict[str, Dict[str, bool]]:
    """Supported AND harmful (positive coefficient: more commuting, worse outcome)."""
    return {e: {m: bool(table[e][m] and o["single"][e][e]["estimate"] > 0) for m, o in result["outcomes"].items()}
            for e in EXPOSURES}


def derive_curve(result: dict, table: Dict[str, Dict[str, bool]]) -> Optional[dict]:
    """
    Coarse monotone score (<= 4 points), or None if the gate fails. The gate needs an exposure that is
    supported AND harmful for at least two outcomes: a stable beneficial or mixed-sign effect cannot
    be turned into a penalty curve.
    """
    table = harmful_table(result, table)
    supported = [e for e in EXPOSURES if sum(table[e].values()) >= 2]
    if not supported:
        return None
    outcomes = result["outcomes"]

    def harm_pp(e: str, m: str) -> float:  # pp of prevalence for the full exposure, harmful direction only
        return max(outcomes[m]["single"][e][e]["estimate"], 0.0) if table[e][m] else 0.0

    scores_by_point: Dict[float, List[float]] = {}
    points: List[Tuple[float, Dict[str, float]]] = []
    if "mean_minutes" in supported:
        for minutes in (10.0, 25.0, 40.0, 60.0):
            points.append((minutes, {m: harm_pp("mean_minutes", m) * (minutes - 10.0) for m in outcomes if table["mean_minutes"][m]}))
    else:
        shares = [e for e in SHARE_EXPOSURES if e in supported]
        points.append((10.0, {m: 0.0 for m in outcomes}))
        running = {m: 0.0 for m in outcomes}
        for e in shares[:3]:
            for m in outcomes:
                if table[e][m]:
                    running[m] = max(running[m], harm_pp(e, m))
            points.append((float(THRESHOLD_MINUTES[e]), dict(running)))
    curve = []
    for minutes, harms in points:
        sc = [max(0.0, 100.0 * (1.0 - h / outcomes[m]["spread_p90_p10"])) for m, h in harms.items()]
        curve.append({"minutes": minutes, "score": round(float(np.mean(sc)), 1) if sc else 100.0,
                      "harm_pp_by_outcome": {m: round(h, 3) for m, h in harms.items()}})
    for i in range(1, len(curve)):  # monotone non-increasing by construction; enforce explicitly
        curve[i]["score"] = min(curve[i]["score"], curve[i - 1]["score"])
    return {"supported_exposures": supported, "points": curve,
            "scaling": "harm (pp) / p90-p10 county spread of the outcome, averaged over outcomes where supported"}


# --------------------------------------------------------------------------- orchestration

def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output", default="data/commute_calibration_v2.json")
    ap.add_argument("--bootstrap", type=int, default=MIN_BOOTSTRAP)
    args = ap.parse_args(argv)
    if args.bootstrap < MIN_BOOTSTRAP:
        ap.error(f"--bootstrap must be at least {MIN_BOOTSTRAP}")
    api_key = os.getenv("CENSUS_API_KEY")
    if not api_key:
        print("CENSUS_API_KEY is not set", file=sys.stderr)
        return 2

    places = fetch_places_county()
    acs, labels = fetch_acs_counties_v2(api_key=api_key)
    df = places.merge(acs, on="fips", how="inner")
    result = run(df, args.bootstrap)
    table = pass_table(result)
    curve = derive_curve(result, table)
    result["pass_table"] = table
    result["harmful_pass_table"] = harmful_table(result, table)
    result["curve"] = curve
    result["conclusion"] = (
        "At least one cumulative exposure is supported for two or more outcomes; a coarse curve is provided."
        if curve else
        "No cumulative exposure is both stable (same sign in every leave-one-region-out fit, bootstrap interval "
        "excluding zero) and harmful for two or more outcomes: county data cannot support a data-derived commute curve."
    )
    result["metadata"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "acs_year": ACS_YEAR, "geography": "county", "weights": "county population",
        "counties": int(df["fips"].nunique()), "bootstrap_resamples": args.bootstrap,
        "bootstrap": "state-clustered, percentile 95%", "controls": [c for c in FULL_CONTROLS if c in df.columns],
        "density_included": "log_density" in df.columns, "report_step": REPORT_STEP,
        "variable_check": labels,
        "caveat": "Ecological county-level fit; PLACES estimates are model-based; not individual effects.",
    }
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)

    for m, o in result["outcomes"].items():
        print(f"\n{m} ({o['label']}) n={o['n']} spread {o['spread_p90_p10']} pp; owner burden {o['owner_burden_check']}")
        for e in EXPOSURES:
            r = o["single"][e][e]
            step = REPORT_STEP[e]
            print(f"  {e:>13}: {r['estimate'] * step:+.3f} pp per {step:g}  CI [{r['ci95'][0] * step:+.3f},{r['ci95'][1] * step:+.3f}]"
                  f"  sameSign={r['same_sign_all_regions']} ciExclZero={r['ci_excludes_zero']} SUPPORTED={r['supported']}")
    print("\nconclusion:", result["conclusion"])
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

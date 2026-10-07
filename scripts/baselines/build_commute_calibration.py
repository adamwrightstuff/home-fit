#!/usr/bin/env python3
"""
Calibrate the commute-time curve against measured health outcomes, at county level.

Outcomes: CDC PLACES age-adjusted prevalence of frequent mental distress (MHLTH), depression
(DEPRESSION) and short sleep (SLEEP). Exposures: ACS 5-year share of workers by travel-time bin
(B08303, which excludes people working from home), controlling for work-from-home share, poverty,
education, median age, log median income, and state fixed effects. The coefficient on each
travel-time bin, relative to commutes under 15 minutes, is the expected change in prevalence if
the whole workforce moved into that bin. That is converted to a 0-100 score by dividing by the
10th-to-90th percentile spread of the county outcome, so a bin that moves expected prevalence by
the full spread scores 0 (no hand-picked target score).

Housing cost burden (share of renters and mortgaged owners paying 30%+ of income) is fitted in
the same model so the commute coefficients are net of it, and its coefficients are reported.

Why county: PLACES tract estimates are model-based from demographics, so regressing them on
tract demographics partly recovers the model itself. County estimates stay closest to the
underlying survey. Place-level fits are ecological: they describe places, not individuals.

Usage (project root; needs data.cdc.gov and api.census.gov reachable, CENSUS_API_KEY optional):
  PYTHONPATH=. python3 scripts/baselines/build_commute_calibration.py \\
    --output data/commute_calibration.json

Dataset ids default to the PLACES county release below; verify they still resolve with --check.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import requests

PLACES_COUNTY_DATASET = "swc5-untb"
ACS_YEAR = 2022
OUTCOMES = {"MHLTH": "frequent mental distress", "DEPRESSION": "depression", "SLEEP": "short sleep"}

# Travel-time bins: name -> ACS B08303 labels that make it up. "lt15" is the reference.
TIME_BINS: Dict[str, List[str]] = {
    "lt15": ["Less than 5 minutes", "5 to 9 minutes", "10 to 14 minutes"],
    "m15_29": ["15 to 19 minutes", "20 to 24 minutes", "25 to 29 minutes"],
    "m30_44": ["30 to 34 minutes", "35 to 39 minutes", "40 to 44 minutes"],
    "m45_59": ["45 to 59 minutes"],
    "m60_89": ["60 to 89 minutes"],
    "m90p": ["90 or more minutes"],
}
# Representative one-way minutes per bin, used only to place bins on the minutes axis.
BIN_MINUTES = {"lt15": 10.0, "m15_29": 22.0, "m30_44": 37.0, "m45_59": 52.0, "m60_89": 75.0, "m90p": 100.0}
REFERENCE_BIN = "lt15"
BINS_FITTED = [b for b in TIME_BINS if b != REFERENCE_BIN]

BURDEN_FEATURES = ["rent_burden_30p", "owner_burden_30p"]
CONTROLS = ["wfh_share", "poverty_rate", "bachelors_share", "median_age", "log_median_income"]


# --------------------------------------------------------------------------- fetching

def _get(url: str, params: Optional[dict] = None, timeout: int = 60):
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()


def fetch_places_county(dataset: str = PLACES_COUNTY_DATASET) -> pd.DataFrame:
    """Age-adjusted county prevalence for each outcome: columns fips, measure, value, pop."""
    rows: List[dict] = []
    offset = 0
    measures = ",".join(f"'{m}'" for m in OUTCOMES)
    while True:
        batch = _get(
            f"https://data.cdc.gov/resource/{dataset}.json",
            {
                "$select": "locationid,measureid,data_value,totalpopulation,year",
                "$where": f"measureid in({measures}) AND datavaluetypeid='AgeAdjPrv'",
                "$limit": 50000,
                "$offset": offset,
                "$order": "locationid,measureid",
            },
        )
        if not batch:
            break
        rows.extend(batch)
        offset += len(batch)
        if len(batch) < 50000:
            break
    if not rows:
        raise RuntimeError(f"No rows from PLACES dataset {dataset}; check the id with --check")
    df = pd.DataFrame(rows).rename(columns={"locationid": "fips", "measureid": "measure", "data_value": "value", "totalpopulation": "pop"})
    df["fips"] = df["fips"].astype(str).str.zfill(5)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["pop"] = pd.to_numeric(df.get("pop"), errors="coerce")
    return df.dropna(subset=["value"])[["fips", "measure", "value", "pop"]]


def _group_vars(group: str, year: int) -> Dict[str, str]:
    """{variable code (E, estimates only): label} for an ACS table group."""
    data = _get(f"https://api.census.gov/data/{year}/acs/acs5/groups/{group}.json")
    return {k: v["label"] for k, v in data["variables"].items() if k.endswith("E") and not k.endswith("EA")}


def _find(variables: Dict[str, str], *must: str, must_not: Sequence[str] = ()) -> str:
    hits = [k for k, lab in variables.items()
            if all(m.lower() in lab.lower() for m in must) and not any(n.lower() in lab.lower() for n in must_not)]
    if len(hits) != 1:
        raise RuntimeError(f"Expected exactly one ACS variable for {must} (not {must_not}); got {hits}")
    return hits[0]


def fetch_acs_counties(year: int = ACS_YEAR, api_key: Optional[str] = None) -> pd.DataFrame:
    """County features: travel-time bin shares, burden shares, and controls."""
    wanted: Dict[str, str] = {}  # name -> variable code

    t = _group_vars("B08303", year)
    wanted["tt_total"] = _find(t, "Total:", must_not=["minutes"])
    for b, labels in TIME_BINS.items():
        for i, lab in enumerate(labels):
            wanted[f"tt_{b}_{i}"] = _find(t, lab)

    r = _group_vars("B25070", year)
    wanted["rent_total"] = _find(r, "Total:", must_not=["percent", "Not computed"])
    wanted["rent_nc"] = _find(r, "Not computed")
    for i, lab in enumerate(["30.0 to 34.9 percent", "35.0 to 39.9 percent", "40.0 to 49.9 percent", "50.0 percent or more"]):
        wanted[f"rent_b{i}"] = _find(r, lab)

    o = _group_vars("B25091", year)
    wanted["own_total"] = _find(o, "with a mortgage", must_not=["percent", "Not computed", "without"])
    wanted["own_nc"] = _find(o, "with a mortgage", "Not computed", must_not=["without"])
    for i, lab in enumerate(["30.0 to 34.9 percent", "35.0 to 39.9 percent", "40.0 to 49.9 percent", "50.0 percent or more"]):
        wanted[f"own_b{i}"] = _find(o, "with a mortgage", lab, must_not=["without"])

    w = _group_vars("B08301", year)
    wanted["workers"] = _find(w, "Total:", must_not=["Total:!!"])
    wanted["wfh"] = _find(w, "Worked from home")

    p = _group_vars("B17001", year)
    wanted["pov_total"] = _find(p, "Total:", must_not=["Total:!!"])
    wanted["pov_below"] = _find(p, "below poverty level", must_not=["Male", "Female", "years", "Not"])

    e = _group_vars("B15003", year)
    wanted["edu_total"] = _find(e, "Total:", must_not=["Total:!!"])
    for k, lab in {"edu_ba": "Bachelor's degree", "edu_ma": "Master's degree", "edu_pr": "Professional school degree", "edu_dr": "Doctorate degree"}.items():
        wanted[k] = _find(e, lab)

    wanted["median_age"] = "B01002_001E"
    wanted["median_income"] = "B19013_001E"

    names = list(wanted)
    frames = []
    for i in range(0, len(names), 40):  # Census caps variables per call
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
    raw[raw < -1_000_000] = np.nan  # Census sentinel values for suppressed cells
    return acs_features(raw.reset_index())


def acs_features(raw: pd.DataFrame) -> pd.DataFrame:
    """Turn raw ACS counts into the model's features (pure; tested offline)."""
    f = pd.DataFrame({"fips": raw["fips"]})
    tt = raw["tt_total"].replace(0, np.nan)
    for b, labels in TIME_BINS.items():
        f[f"share_{b}"] = sum(raw[f"tt_{b}_{i}"] for i in range(len(labels))) / tt
    f["wfh_share"] = raw["wfh"] / raw["workers"].replace(0, np.nan)
    rent_den = (raw["rent_total"] - raw["rent_nc"]).replace(0, np.nan)
    f["rent_burden_30p"] = sum(raw[f"rent_b{i}"] for i in range(4)) / rent_den
    own_den = (raw["own_total"] - raw["own_nc"]).replace(0, np.nan)
    f["owner_burden_30p"] = sum(raw[f"own_b{i}"] for i in range(4)) / own_den
    f["poverty_rate"] = raw["pov_below"] / raw["pov_total"].replace(0, np.nan)
    f["bachelors_share"] = (raw["edu_ba"] + raw["edu_ma"] + raw["edu_pr"] + raw["edu_dr"]) / raw["edu_total"].replace(0, np.nan)
    f["median_age"] = raw["median_age"]
    f["log_median_income"] = np.log(raw["median_income"].where(raw["median_income"] > 0))
    return f


# --------------------------------------------------------------------------- estimation

def fit_wls(y: np.ndarray, X: np.ndarray, w: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Weighted least squares with HC1 robust standard errors. X includes the intercept."""
    sw = np.sqrt(w)
    Xw, yw = X * sw[:, None], y * sw
    XtX_inv = np.linalg.pinv(Xw.T @ Xw)
    beta = XtX_inv @ Xw.T @ yw
    resid = yw - Xw @ beta
    n, k = X.shape
    meat = (Xw * resid[:, None]).T @ (Xw * resid[:, None])
    cov = XtX_inv @ meat @ XtX_inv * (n / max(n - k, 1))
    return beta, np.sqrt(np.diag(cov))


def design_matrix(df: pd.DataFrame, features: Sequence[str], state_fe: bool) -> Tuple[np.ndarray, List[str]]:
    cols = [df[c].to_numpy(float) for c in features]
    names = list(features)
    if state_fe:
        states = df["fips"].str[:2]
        for s in sorted(states.unique())[1:]:  # first state is the baseline
            cols.append((states == s).to_numpy(float))
            names.append(f"state_{s}")
    X = np.column_stack([np.ones(len(df))] + cols)
    return X, ["intercept"] + names


def fit_outcome(df: pd.DataFrame, outcome: str, state_fe: bool = True) -> dict:
    d = df[df["measure"] == outcome].copy()
    feats = [f"share_{b}" for b in BINS_FITTED] + BURDEN_FEATURES + CONTROLS
    d = d.dropna(subset=feats + ["value"])
    w = d["pop"].fillna(d["pop"].median()).clip(lower=1).to_numpy(float)
    X, names = design_matrix(d, feats, state_fe)
    beta, se = fit_wls(d["value"].to_numpy(float), X, w)
    coefs = {n: (float(b), float(s)) for n, b, s in zip(names, beta, se) if not n.startswith("state_")}
    p10, p90 = np.percentile(d["value"], [10, 90])
    return {"n": int(len(d)), "coefficients": coefs, "spread_p90_p10": float(p90 - p10), "mean": float(np.average(d["value"], weights=w))}


def harm_to_curve(fit: dict) -> dict:
    """
    Per-bin harm (percentage points of prevalence, vs the reference bin) -> 0-100 score.
    Negative harms are clamped to zero and harm is made non-decreasing in commute length; both
    adjustments are recorded so a reader can see where the data disagreed with that shape.
    """
    spread = fit["spread_p90_p10"]
    raw = {b: fit["coefficients"][f"share_{b}"][0] for b in BINS_FITTED}
    se = {b: fit["coefficients"][f"share_{b}"][1] for b in BINS_FITTED}
    harm, adjusted, running = {REFERENCE_BIN: 0.0}, [], 0.0
    for b in BINS_FITTED:
        h = max(raw[b], 0.0)
        if h < running:
            adjusted.append(b)
            h = running
        elif raw[b] < 0:
            adjusted.append(b)
        harm[b] = h
        running = h
    points = [
        {"bin": b, "minutes": BIN_MINUTES[b], "harm_pp": round(harm[b], 3),
         "score": round(max(0.0, 100.0 * (1.0 - harm[b] / spread)), 1)}
        for b in TIME_BINS
    ]
    return {
        "points": points,
        "raw_coefficients_pp": {b: {"estimate": round(raw[b], 3), "se": round(se[b], 3)} for b in BINS_FITTED},
        "shape_adjusted_bins": adjusted,
    }


# --------------------------------------------------------------------------- orchestration

def build_dataset(api_key: Optional[str]) -> pd.DataFrame:
    places = fetch_places_county()
    acs = fetch_acs_counties(api_key=api_key)
    return places.merge(acs, on="fips", how="inner")


def run(df: pd.DataFrame, state_fe: bool = True) -> dict:
    out = {"outcomes": {}}
    for m, label in OUTCOMES.items():
        if (df["measure"] == m).sum() < 100:
            continue
        fit = fit_outcome(df, m, state_fe)
        out["outcomes"][m] = {"label": label, **fit, "curve": harm_to_curve(fit),
                              "burden_coefficients_pp": {k: {"estimate": round(fit["coefficients"][k][0], 3), "se": round(fit["coefficients"][k][1], 3)} for k in BURDEN_FEATURES}}
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output", default="data/commute_calibration.json")
    ap.add_argument("--no-state-fe", action="store_true", help="Skip state fixed effects")
    ap.add_argument("--check", action="store_true", help="Only verify the PLACES dataset and ACS groups resolve")
    args = ap.parse_args(argv)
    api_key = os.getenv("CENSUS_API_KEY")

    if args.check:
        p = fetch_places_county()
        print(f"PLACES {PLACES_COUNTY_DATASET}: {len(p)} rows, measures {sorted(p['measure'].unique())}")
        a = fetch_acs_counties(api_key=api_key)
        print(f"ACS {ACS_YEAR}: {len(a)} counties, columns {list(a.columns)}")
        return 0

    df = build_dataset(api_key)
    result = run(df, state_fe=not args.no_state_fe)
    result["metadata"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "places_dataset": PLACES_COUNTY_DATASET,
        "acs_year": ACS_YEAR,
        "geography": "county",
        "state_fixed_effects": not args.no_state_fe,
        "weights": "county population",
        "counties": int(df["fips"].nunique()),
        "reference_bin": REFERENCE_BIN,
        "caveat": "Ecological fit: describes places, not individuals. Bin minutes are representative midpoints.",
    }
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    for m, o in result["outcomes"].items():
        print(f"\n{m} ({o['label']}), n={o['n']}, mean {o['mean']:.1f}%, p90-p10 spread {o['spread_p90_p10']:.2f} pp")
        for p in o["curve"]["points"]:
            print(f"  {p['bin']:>7}  ~{p['minutes']:>5.0f} min  harm {p['harm_pp']:>6.2f} pp  score {p['score']:>5.1f}")
        if o["curve"]["shape_adjusted_bins"]:
            print(f"  (shape-adjusted: {o['curve']['shape_adjusted_bins']})")
    print(f"\nWrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

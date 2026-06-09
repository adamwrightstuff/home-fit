"""
Build data/zillow_zhvi_zip.json from Zillow Research public CSVs.

Downloads two tiers:
  - Middle tier (0.33–0.67): used to override Census $2M cap on median home values
  - Bottom tier (0.00–0.33): used for Up-and-Coming velocity signal (entry-level stock
    reprices first in gentrifying neighborhoods)

Output JSON structure:
{
  "as_of": "2026-04-30",
  "values": { "11201": 1250000, ... },          # middle-tier current (existing usage)
  "bottom_tier": { "11201": 850000, ... },       # bottom-tier current
  "appreciation_3yr": { "11201": 0.182, ... },   # middle-tier 3yr change (e.g. 0.182 = +18.2%)
  "appreciation_1yr": { "11201": 0.043, ... },   # middle-tier 1yr change
  "velocity_6mo": { "11201": 0.021, ... },       # bottom-tier 6mo change (momentum signal)
}

Run from repo root:
  PYTHONPATH=. python3 scripts/baselines/build_zillow_zhvi.py
"""

from __future__ import annotations

import csv
import io
import json
import os
import urllib.request
from datetime import date, timedelta
from typing import Optional

MIDDLE_TIER_URL = "https://files.zillowstatic.com/research/public_csvs/zhvi/Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
BOTTOM_TIER_URL = "https://files.zillowstatic.com/research/public_csvs/zhvi/Zip_zhvi_uc_sfrcondo_tier_0.0_0.33_sm_sa_month.csv"

OUT_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'zillow_zhvi_zip.json')


def _fetch_csv(url: str) -> list[dict]:
    print(f"Downloading {url} ...")
    with urllib.request.urlopen(url, timeout=120) as resp:
        content = resp.read().decode('utf-8')
    reader = csv.DictReader(io.StringIO(content))
    return list(reader)


def _date_cols(row: dict) -> list[str]:
    """Return all YYYY-MM-DD column names in chronological order."""
    return sorted([k for k in row.keys() if len(k) == 10 and k[4] == '-' and k[7] == '-'])


def _nearest_col(cols: list[str], target: date) -> Optional[str]:
    """Find the column closest to target date (within 45 days)."""
    target_str = target.isoformat()
    best = None
    best_delta = 999
    for c in cols:
        try:
            d = date.fromisoformat(c)
            delta = abs((d - target).days)
            if delta < best_delta:
                best_delta = delta
                best = c
        except ValueError:
            continue
    return best if best_delta <= 45 else None


def _extract(rows: list[dict], current_col: str, *prior_cols: str) -> tuple[dict, list[dict]]:
    """
    Returns (current_values, list_of_prior_value_dicts).
    Skips rows with missing values for current col.
    """
    current: dict[str, int] = {}
    priors: list[dict[str, Optional[int]]] = [{} for _ in prior_cols]

    for row in rows:
        zip_code = str(row.get('RegionName', '')).zfill(5)
        if not zip_code or zip_code == '00000':
            continue
        raw_cur = row.get(current_col, '').strip()
        if not raw_cur:
            continue
        try:
            cur_val = int(float(raw_cur))
        except ValueError:
            continue
        current[zip_code] = cur_val

        for i, col in enumerate(prior_cols):
            raw_p = row.get(col, '').strip() if col else ''
            priors[i][zip_code] = int(float(raw_p)) if raw_p else None

    return current, priors


def _appreciation(current: dict[str, int], prior: dict[str, Optional[int]]) -> dict[str, float]:
    """Compute (current - prior) / prior for each ZIP where both exist."""
    result: dict[str, float] = {}
    for zip_code, cur in current.items():
        p = prior.get(zip_code)
        if p and p > 0:
            result[zip_code] = round((cur - p) / p, 4)
    return result


def main() -> None:
    today = date.today()
    target_current = today - timedelta(days=30)   # ~1 month lag in Zillow data
    target_1yr     = today - timedelta(days=395)
    target_3yr     = today - timedelta(days=3 * 365 + 15)
    target_6mo     = today - timedelta(days=190)

    # ── Middle tier ──────────────────────────────────────────────────────────
    middle_rows = _fetch_csv(MIDDLE_TIER_URL)
    cols_m = _date_cols(middle_rows[0])

    col_cur   = _nearest_col(cols_m, target_current)
    col_1yr   = _nearest_col(cols_m, target_1yr)
    col_3yr   = _nearest_col(cols_m, target_3yr)

    print(f"Middle tier — current: {col_cur}  1yr: {col_1yr}  3yr: {col_3yr}")

    mid_current, (mid_1yr_vals, mid_3yr_vals) = _extract(
        middle_rows, col_cur, col_1yr, col_3yr
    )
    appr_1yr = _appreciation(mid_current, mid_1yr_vals)
    appr_3yr = _appreciation(mid_current, mid_3yr_vals)

    # ── Bottom tier ──────────────────────────────────────────────────────────
    bottom_rows = _fetch_csv(BOTTOM_TIER_URL)
    cols_b = _date_cols(bottom_rows[0])

    col_b_cur = _nearest_col(cols_b, target_current)
    col_b_6mo = _nearest_col(cols_b, target_6mo)

    print(f"Bottom tier — current: {col_b_cur}  6mo: {col_b_6mo}")

    bot_current, (bot_6mo_vals,) = _extract(bottom_rows, col_b_cur, col_b_6mo)
    velocity_6mo = _appreciation(bot_current, bot_6mo_vals)

    # ── Assemble output ───────────────────────────────────────────────────────
    as_of = col_cur or today.isoformat()
    out = {
        "as_of": as_of,
        "values": mid_current,            # existing field — middle-tier current
        "bottom_tier": bot_current,        # bottom-tier current
        "appreciation_1yr": appr_1yr,      # middle-tier 1yr % change
        "appreciation_3yr": appr_3yr,      # middle-tier 3yr % change
        "velocity_6mo": velocity_6mo,      # bottom-tier 6mo % change (momentum)
    }

    out_path = os.path.normpath(OUT_PATH)
    with open(out_path, 'w') as f:
        json.dump(out, f, separators=(',', ':'))

    print(f"\nWrote {out_path}")
    print(f"  Middle-tier ZIPs: {len(mid_current):,}")
    print(f"  Bottom-tier ZIPs: {len(bot_current):,}")
    print(f"  1yr appreciation: {len(appr_1yr):,} ZIPs")
    print(f"  3yr appreciation: {len(appr_3yr):,} ZIPs")
    print(f"  6mo velocity:     {len(velocity_6mo):,} ZIPs")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Offline social fabric engagement recompute.

Recomputes the engagement sub-score using stored orgs_per_1k + voter_turnout_rate
plus the newly integrated SCA ZIP-level volunteering rates — no API calls.
Stability and civic_gathering are unchanged (stored values reused).

Usage:
  PYTHONPATH=. python3 scripts/catalog/recompute_social_fabric_engagement.py \
    --input data/nyc_metro_place_catalog_scores_merged.jsonl \
    --output data/nyc_metro_place_catalog_scores_merged.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from data_sources import irs_bmf
from data_sources.community_participation import (
    _rate_to_z_score,
    _bmf_z_from_result,
    get_volunteering_score,
    _sca_vol_by_zip,
)


def _recompute_total(pillars: dict) -> float:
    total = weighted = 0.0
    for p in pillars.values():
        if not isinstance(p, dict):
            continue
        score = p.get("score")
        weight = p.get("weight")
        if score is not None and weight is not None:
            weighted += float(score) * float(weight)
            total += float(weight)
    return round(weighted / total, 4) if total > 0 else 0.0


def recompute_row(row: dict) -> tuple[bool, str]:
    score_doc = row.get("score", {})
    pillars = score_doc.get("livability_pillars", {})
    sf = pillars.get("social_fabric")
    if not sf or sf.get("status") != "success":
        return False, "no social_fabric or not success"

    summary = sf.get("summary", {})
    breakdown = sf.get("breakdown", {})

    orgs_per_1k: Optional[float] = summary.get("orgs_per_1k")
    turnout_rate: Optional[float] = summary.get("voter_turnout_rate")
    area_type: Optional[str] = (sf.get("area_classification") or {}).get("area_type")
    zip_code: Optional[str] = (score_doc.get("location_info") or {}).get("zip")
    coords = score_doc.get("coordinates", {})
    lat = coords.get("lat")
    lon = coords.get("lon")

    stability = breakdown.get("stability")
    civic = breakdown.get("civic_gathering")
    if stability is None or civic is None:
        return False, "missing stability or civic sub-score"

    # BMF z-score from stored orgs_per_1k + area_type baselines
    bmf_z: Optional[float] = None
    if orgs_per_1k is not None and lat is not None:
        r_ref = irs_bmf.get_civic_orgs_per_1k(
            lat, lon, tract=None, division_code=None,
            area_type=area_type, counts_mode="refined",
        )
        r_leg = irs_bmf.get_civic_orgs_per_1k(
            lat, lon, tract=None, division_code=None,
            area_type=area_type, counts_mode="legacy",
        )
        # Use stored orgs_per_1k but area-type stats from the module
        def _z_from_stored(result, orgs):
            if result is None:
                return None
            _, stats = result
            if not stats:
                return None
            mean = float(stats.get("mean", 0) or 0)
            std = float(stats.get("std", 0) or 0)
            if std <= 0:
                return None
            return _rate_to_z_score(orgs, mean, std)

        z_ref = _z_from_stored(r_ref, orgs_per_1k)
        z_leg = _z_from_stored(r_leg, orgs_per_1k)
        bmf_z = z_ref if z_ref is not None else z_leg

    # Volunteering z-score — SCA ZIP preferred, CPS state fallback
    vol = get_volunteering_score(zip_code, None)
    z_vol = vol[0] if vol else None
    vol_resolution = vol[1] if vol else None

    # Turnout z-score from stored rate
    z_turn: Optional[float] = None
    if turnout_rate is not None:
        z_turn = _rate_to_z_score(float(turnout_rate), 0.45, 0.12)

    # Blend (mirrors compute_participation_score logic)
    if bmf_z is not None and z_vol is not None and z_turn is not None:
        engagement = 0.40 * bmf_z + 0.40 * z_vol + 0.20 * z_turn
        mix = "full"
    elif z_vol is None and bmf_z is not None and z_turn is not None:
        engagement = 0.60 * bmf_z + 0.40 * z_turn
        mix = "no_vol_60_40_bmf_turn"
    elif z_turn is None and bmf_z is not None and z_vol is not None:
        engagement = 0.60 * bmf_z + 0.40 * z_vol
        mix = "no_turn_60_40_bmf_vol"
    elif bmf_z is not None and z_vol is not None:
        engagement = 0.60 * bmf_z + 0.40 * z_vol
        mix = "bmf_vol_only"
    elif bmf_z is not None and z_turn is not None:
        engagement = 0.60 * bmf_z + 0.40 * z_turn
        mix = "bmf_turn_only"
    elif bmf_z is None and z_vol is not None and z_turn is not None:
        engagement = 0.50 * z_vol + 0.50 * z_turn
        mix = "vol_turn_no_bmf"
    elif bmf_z is not None:
        engagement = bmf_z
        mix = "bmf_only"
    elif z_vol is not None:
        engagement = z_vol
        mix = "vol_only"
    elif z_turn is not None:
        engagement = z_turn
        mix = "turn_only"
    else:
        return False, "no engagement inputs"

    engagement = max(0.0, min(100.0, engagement))

    # Recompute overall social fabric score
    raw = 1.2 * float(stability) + 1.2 * float(civic) + 1.2 * engagement
    new_score = round(max(0.0, min(100.0, raw / 3.6)), 1)

    # Update in place
    breakdown["engagement"] = round(engagement, 4)
    sf["score"] = new_score
    summary["participation_mix"] = mix
    summary["volunteering_resolution"] = vol_resolution or summary.get("volunteering_resolution")

    score_doc["total_score"] = _recompute_total(pillars)
    return True, f"vol={vol_resolution or 'none'}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    rows = [json.loads(l) for l in Path(args.input).read_text().splitlines() if l.strip()]

    sca_zip_count = len(_sca_vol_by_zip)
    print(f"SCA ZIP rates loaded: {sca_zip_count}")

    ok = skip = err = 0
    sca_hits = cps_hits = 0
    reasons: dict[str, int] = {}

    for row in rows:
        success, reason = recompute_row(row)
        if success:
            ok += 1
            if "sca_zip" in reason:
                sca_hits += 1
            else:
                cps_hits += 1
        else:
            if "no social_fabric" in reason:
                skip += 1
            else:
                err += 1
            reasons[reason] = reasons.get(reason, 0) + 1

    Path(args.output).write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"Done: {ok} recomputed ({sca_hits} SCA ZIP, {cps_hits} CPS state), {skip} skipped, {err} errors")
    for r, n in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"  {n:4d}  {r}")


if __name__ == "__main__":
    main()

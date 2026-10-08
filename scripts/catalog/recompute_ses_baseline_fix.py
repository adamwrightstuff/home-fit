#!/usr/bin/env python3
"""
Offline fix for mis-baselined Status Signal / Socioeconomic Standing scores.

Recomputes only status_signal, status_signal_breakdown and it_score (hotness) from stored
pillar data, forcing the metro baseline via a synthetic tract (CBSA code) instead of a live
Census lookup, so there is no tract-boundary drift. Only places whose stored education score
does NOT reproduce under their file's metro baseline are touched (see --scope).

  PYTHONPATH=. python3 scripts/catalog/recompute_ses_baseline_fix.py --metro sf            # dry run
  PYTHONPATH=. python3 scripts/catalog/recompute_ses_baseline_fix.py --metro nyc --write
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

CBSA = {"nyc": "35620", "sf": "41860", "la": "31080", "seattle": "42660"}
KEY = {"nyc": "nyc_metro", "sf": "sf_metro", "la": "la_metro", "seattle": "seattle_metro"}
# Places whose mismatch has an unexplained cause; left untouched.
SKIP = {"East Harlem", "Thousand Oaks", "Bainbridge Island"}


def _mm(v, lo, hi):
    return 50.0 if hi <= lo else max(0.0, min(100.0, (v - lo) / (hi - lo) * 100.0))


def _edu_under(b, key, e):
    g = b[key]["education"]["grad_pct"]
    c = b[key]["education"]["bach_pct"]
    return 0.8 * _mm(e["grad_pct"], g["min"], g["max"]) + 0.2 * _mm(e["bachelor_pct"], c["min"], c["max"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--metro", required=True, choices=list(CBSA))
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    from data_sources import census_api
    census_api.get_diversity_data = lambda *a, **k: {}  # no network
    from pillars.composite_indices import _area_type_from_payload, compute_hotness_score
    from pillars.status_signal import compute_status_signal_with_breakdown

    path = REPO / "data" / f"{args.metro}_metro_place_catalog_scores_merged.composites_recomputed.jsonl"
    baselines = json.load(open(REPO / "data" / "status_signal_baselines.json"))
    key = KEY[args.metro]

    out_lines, changes = [], []
    for line in open(path, encoding="utf-8"):
        raw = line.rstrip("\n")
        if not raw.strip():
            continue
        r = json.loads(raw)
        s = r.get("score") if r.get("success") else None
        name = r["catalog"]["name"]
        if isinstance(s, dict) and name not in SKIP:
            bd = s.get("status_signal_breakdown") or {}
            e = ((s.get("livability_pillars") or {}).get("diversity") or {}).get("education_attainment")
            stored = bd.get("education")
            mismatched = (
                stored is not None and e and e.get("grad_pct") is not None
                and abs(_edu_under(baselines, key, e) - stored) >= 0.15
            )
            if mismatched:
                p = s["livability_pillars"]
                li = s.get("location_info") or {}
                co = s.get("coordinates") or {}
                res = compute_status_signal_with_breakdown(
                    p.get("housing_value"), p.get("social_fabric"), p.get("economic_opportunity"),
                    ((p.get("neighborhood_amenities") or {}).get("breakdown") or {}).get("business_list") or [],
                    {"cbsa_code": CBSA[args.metro]},
                    (li.get("state") or "").strip() or None,
                    city=(li.get("city") or "").strip() or None,
                    lat=co.get("lat"), lon=co.get("lon"),
                    diversity_details=p.get("diversity") if isinstance(p.get("diversity"), dict) else None,
                    area_type=_area_type_from_payload(s),
                    zip_code=(li.get("zip") or "").strip() or None,
                )
                if res and res[0] is not None:
                    new, nbd = res
                    old = s.get("status_signal")
                    old_arch = bd.get("archetype")
                    s["status_signal"] = max(0.0, min(100.0, float(new)))
                    s["status_signal_breakdown"] = nbd
                    hc = nbd.get("home_cost")
                    s["it_score"] = compute_hotness_score(
                        s["status_signal"], s.get("local_scene_score"),
                        hc if isinstance(hc, (int, float)) else None,
                        s.get("happiness_index"), s.get("total_score"),
                    )
                    changes.append((name, r["catalog"]["state_abbr"], old, s["status_signal"], old_arch, nbd.get("archetype"), stored, nbd.get("education")))
        out_lines.append(json.dumps(r, ensure_ascii=False))

    print(f"{args.metro}: {len(changes)} places recomputed")
    for n, st, o, nw, oa, na, oe, ne in sorted(changes, key=lambda c: -abs(c[3] - c[2]))[:60]:
        print(f"  {n:<26}{st} {o:5.1f} -> {nw:5.1f} ({nw-o:+.1f})  edu {oe:5.1f}->{ne:5.1f}  {oa}->{na}")
    if changes:
        d = [abs(c[3] - c[2]) for c in changes]
        print(f"  mean |delta| {sum(d)/len(d):.1f}, max {max(d):.1f}")
    if args.write:
        path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

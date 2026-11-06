#!/usr/bin/env python3
"""
Offline recompute of status_signal under the class-position method (DPv2, 2026-11-04). No API calls.

For every place in every metro catalog it keeps the stored class label, computes the 0-100 class-position score
from the stored housing_value summary and the class cutoffs, and refreshes the fields that read the score
(signal strength, top drivers, aura it_score). Writes NEW files only, to --out-dir (default data/status_class_position/);
the originals are never touched.

It also re-derives the class from the stored inputs and reports any place where that differs from the stored class,
which would mean the metro cutoff key used here differs from the one the catalog was scored with.

  PYTHONPATH=. python3 scripts/catalog/recompute_status_class_position.py [--metro dallas] [--out-dir DIR]
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--metro", default=None)
    ap.add_argument("--out-dir", default=str(REPO / "data" / "status_class_position"))
    ap.add_argument("--pooled", default=None,
                    help="pooled_inputs.json from pool_status_class_inputs_offline.py: single-tract places read the pooled "
                         "income and home value (same pool as the housing pillar, D14) and the class is re-derived from them")
    ap.add_argument("--ring-m", type=int, default=700, help="ring radius of the pooled file, recorded in the breakdown (350 is the label pool)")
    args = ap.parse_args()

    from pillars.composite_indices import AURA_WEIGHTS
    from pillars import status_signal as ss

    baselines = json.load(open(REPO / "data" / "status_signal_baselines.json"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = f"{args.metro}_metro_place_catalog_scores_merged.composites_recomputed.jsonl" if args.metro else "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"
    pooled_in = json.load(open(args.pooled)) if args.pooled else {}
    summary = collections.Counter()
    class_mismatch = []
    for path in sorted(glob.glob(str(REPO / "data" / pattern))):
        metro = Path(path).name.split("_metro_")[0]
        keys = [f"{metro}_metro", "all"]
        rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
        for r in rows:
            s = r.get("score") if r.get("success") else None
            if not isinstance(s, dict):
                continue
            bd = s.get("status_signal_breakdown")
            if not isinstance(bd, dict):
                continue
            hv = (s.get("livability_pillars") or {}).get("housing_value") or {}
            sm = hv.get("summary") if isinstance(hv.get("summary"), dict) else hv
            arch = bd.get("archetype")
            # Household route to Affluent (round 2): share of households at $150,000 or more from the stored B19001 bins
            # (single tract or place; not pooled, the pooled pull has no income bins).
            sm = dict(sm)
            br = ((((s.get("livability_pillars") or {}).get("diversity") or {}).get("raw_shares")) or {}).get("income_brackets")
            if isinstance(br, list) and len(br) == 16 and all(isinstance(v, (int, float)) for v in br[-2:]):
                sm["share_households_150k_plus"] = float(br[-2]) + float(br[-1])
                bd["households_150k_plus_share"] = round(sm["share_households_150k_plus"], 1)
            pin = pooled_in.get(f"{metro}|{r['catalog']['name']}")
            if pin and sm.get("geo_level") == "tract":
                # Pooled income and home value. The ACS monthly housing cost (B25105) is not in the cached pull, so the
                # single-tract burden ratio (cost / income) is held and applied to the pooled income.
                inc1, cost1 = sm.get("median_household_income"), sm.get("median_monthly_housing_cost")
                sm = dict(sm)
                sm["median_household_income"] = pin["income"]
                if pin.get("home_value"):
                    sm["median_home_value"] = pin["home_value"]
                if isinstance(cost1, (int, float)) and cost1 > 0 and isinstance(inc1, (int, float)) and inc1 > 0:
                    sm["median_monthly_housing_cost"] = cost1 * pin["income"] / inc1
                bd["pooled_inputs"] = {"income": round(pin["income"]), "home_value": round(pin["home_value"] or 0),
                                       "tracts": pin["tracts"], "method": f"disk_approx_{args.ring_m}m_ring_occupied_weighted"}
                summary["pooled_places"] += 1
                new_cls = ss._classify_class(sm, keys, baselines)
                if new_cls is not None:
                    if new_cls[0] != arch:
                        summary["class_changed_by_pooling"] += 1
                    arch = new_cls[0]
                    bd["archetype"], bd["archetype_rule"] = new_cls
                    bd["status_label"] = ss._get_status_label(arch)
                    bd["status_insight"] = ss._get_status_insight(arch, new_cls[1])
                re_cls = None  # class was just derived from the pooled inputs
            else:
                re_cls = ss._classify_class(sm, keys, baselines)
                if re_cls is not None and (re_cls[0] != arch or re_cls[1] != bd.get("archetype_rule")):
                    if re_cls[0] != arch:
                        class_mismatch.append((r["catalog"]["name"], arch, re_cls[0]))
                        summary["class_changed_at_stored_inputs"] += 1
                    arch = re_cls[0]
                    bd["archetype"], bd["archetype_rule"] = re_cls
                    bd["status_label"] = ss._get_status_label(arch)
                    bd["status_insight"] = ss._get_status_insight(arch, re_cls[1])
            if re_cls is None and arch is not None and not (pin and sm.get("geo_level") == "tract"):
                # No income: no class (the old fallback defaulted to Struggling).
                for k in ("archetype", "archetype_rule", "status_label", "status_insight", "trajectory", "trajectory_rule"):
                    bd[k] = None
                bd["insufficient_data"] = True
                arch = None
                summary["class_cleared_no_income"] += 1
            new = ss.class_position_score(arch, sm, keys, baselines)
            old = s.get("status_signal")
            s["status_signal_old"] = old
            s["status_signal"] = new
            bd["education"] = None
            bd["occupation"] = None
            if new is None:
                bd["composite_score"] = bd["signal_strength"] = bd["signal_strength_label"] = None
                summary["no_score"] += 1
            else:
                k, lab = ss._signal_strength_band(new)
                bd["composite_score"], bd["signal_strength"], bd["signal_strength_label"] = new, k, lab
                bd["score_method"] = ss.SCORE_METHOD
                m = sm.get("median_monthly_housing_cost")
                if not (isinstance(m, (int, float)) and m > 0):
                    bd["degraded"], bd["degraded_reasons"] = True, ["housing_cost_missing_burden_test_skipped"]
                    summary["degraded_housing_cost_missing"] += 1
            bd["top_drivers"] = ss._build_top_drivers(bd.get("wealth"), bd.get("home_cost"), None, None, arch or "")
            bd["provisional_composite_score"] = None
            s["it_score_old"] = s.get("it_score")
            # Aura is linear in status_signal (weight AURA_WEIGHTS["status_signal"]). Apply only the status change to the
            # stored aura so unrelated drift in other stored inputs does not leak into this diff.
            old_it = s["it_score_old"]
            if old_it is None or new is None or old is None:
                s["it_score"] = None
            else:
                s["it_score"] = round(min(100.0, max(0.0, old_it + AURA_WEIGHTS["status_signal"] * (new - old))), 2)
            summary["places"] += 1
        out = out_dir / Path(path).name.replace(".composites_recomputed.jsonl", ".status_class_position.jsonl")
        out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
        print(f"wrote {out}")
    print(dict(summary))
    print(f"class re-derivation mismatches vs stored label: {len(class_mismatch)}")
    for m in class_mismatch[:15]:
        print("  ", m)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
    args = ap.parse_args()

    from pillars.composite_indices import AURA_WEIGHTS
    from pillars import status_signal as ss

    baselines = json.load(open(REPO / "data" / "status_signal_baselines.json"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = f"{args.metro}_metro_place_catalog_scores_merged.composites_recomputed.jsonl" if args.metro else "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"
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
            re_cls = ss._classify_class(sm, keys, baselines)
            if re_cls is not None and re_cls[0] != arch:
                class_mismatch.append((r["catalog"]["name"], arch, re_cls[0]))
            if re_cls is None and arch is not None:
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

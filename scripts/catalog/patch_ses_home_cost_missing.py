#!/usr/bin/env python3
"""
Offline patch: drop SES home_cost when the Census median home value is missing/non-positive.

Works purely from stored breakdown components (wealth, education, occupation, archetype),
so nothing else moves: no baseline lookups, no Census calls. Reweights the composite with the
stored archetype's weights over the components that are present, then refreshes top_drivers,
provisional score, signal strength and hotness (it_score).

Also restores an occupation value lost by an earlier offline recompute when --restore-from
(a git rev holding the pre-loss file) has it.

  PYTHONPATH=. python3 scripts/catalog/patch_ses_home_cost_missing.py --metro nyc            # dry run
  PYTHONPATH=. python3 scripts/catalog/patch_ses_home_cost_missing.py --metro nyc --write --restore-from 73f5676
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


def _recompose(b):
    from pillars.status_signal import (
        PROVISIONAL_COMPOSITE_WEIGHTS, _build_top_drivers, _composite_score_from_weights,
        _get_archetype_weights, _signal_strength_band,
    )
    ww, wh, we, wo = _get_archetype_weights(b["archetype"])
    parts = [(ww, b.get("wealth")), (wh, b.get("home_cost")), (we, b.get("education")), (wo, b.get("occupation"))]
    tot = sum(w for w, v in parts if v is not None)
    if tot <= 0:
        return None
    final = round(max(0.0, min(100.0, sum(w * v for w, v in parts if v is not None) / tot)), 1)
    pw, ph, pe, po = PROVISIONAL_COMPOSITE_WEIGHTS
    prov = _composite_score_from_weights(pw, ph, pe, po, b.get("wealth"), b.get("home_cost"), b.get("education"), b.get("occupation"))
    b["provisional_composite_score"] = round(prov, 1) if prov is not None else None
    b["top_drivers"] = _build_top_drivers(b.get("wealth"), b.get("home_cost"), b.get("education"), b.get("occupation"), b["archetype"])
    key, label = _signal_strength_band(final)
    b["composite_score"] = final
    b["signal_strength"] = key
    b["signal_strength_label"] = label
    return final


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--metro", required=True)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--restore-from", help="git rev with the pre-loss file, to restore lost occupation")
    args = ap.parse_args()

    from pillars.composite_indices import compute_hotness_score

    rel = f"data/{args.metro}_metro_place_catalog_scores_merged.composites_recomputed.jsonl"
    path = REPO / rel
    old_occ = {}
    if args.restore_from:
        txt = subprocess.run(["git", "show", f"{args.restore_from}:{rel}"], capture_output=True, text=True, cwd=REPO).stdout
        for l in txt.splitlines():
            r = json.loads(l)
            bd = (r.get("score") or {}).get("status_signal_breakdown") or {}
            if bd.get("occupation") is not None:
                old_occ[r["catalog"]["name"]] = bd["occupation"]

    out, changes = [], []
    for line in open(path, encoding="utf-8"):
        raw = line.rstrip("\n")
        if not raw.strip():
            continue
        r = json.loads(raw)
        s = r.get("score") if r.get("success") else None
        b = (s or {}).get("status_signal_breakdown")
        if isinstance(b, dict) and b.get("archetype"):
            name = r["catalog"]["name"]
            hv = (((s.get("livability_pillars") or {}).get("housing_value") or {}).get("summary") or {}).get("median_home_value")
            # Wealth also missing (non-residential/campus tracts): only education and occupation
            # would remain, so hold those rows back for a separate decision.
            fix_hc = (
                (not isinstance(hv, (int, float)) or hv <= 0)
                and b.get("home_cost") == 0
                and b.get("wealth") is not None
            )
            fix_occ = b.get("occupation") is None and name in old_occ
            if fix_hc or fix_occ:
                old = s["status_signal"]
                if fix_hc:
                    b["home_cost"] = None
                    (b.get("classifier_inputs") or {})["home_cost"] = None
                if fix_occ:
                    b["occupation"] = old_occ[name]
                    (b.get("classifier_inputs") or {})["occupation"] = old_occ[name]
                new = _recompose(b)
                if new is not None:
                    s["status_signal"] = new
                    hc = b.get("home_cost")
                    s["it_score"] = compute_hotness_score(
                        new, s.get("local_scene_score"), hc if isinstance(hc, (int, float)) else None,
                        s.get("happiness_index"), s.get("total_score"),
                    )
                    changes.append((name, old, new, b["archetype"], b.get("wealth"), fix_hc, fix_occ))
        out.append(json.dumps(r, ensure_ascii=False))

    print(f"{args.metro}: {len(changes)} places patched")
    for n, o, nw, a, w, hc, oc in sorted(changes, key=lambda c: -abs(c[2] - c[1])):
        tag = ("home_cost " if hc else "") + ("occupation-restored" if oc else "")
        print(f"  {n:<22}{a:<14}{o:5.1f} -> {nw:5.1f} ({nw-o:+.1f})  wealth={None if w is None else round(w,1)}  {tag}")
    if args.write:
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
        print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Offline: bring stored SES wealth up to the current compute_wealth formula (income + home value only).

NYC and LA stored wealth predates the 2026-07-22 F04 change (it still folds education and
occupation into wealth). Recomputes wealth from the stored housing inputs, keeps stored
education / occupation / home_cost, re-derives archetype and trajectory (both wealth-driven),
reweights the composite, and refreshes labels, top drivers, signal strength and hotness.
No Census or API calls.

  PYTHONPATH=. python3 scripts/catalog/recompute_ses_wealth_offline.py --metro nyc          # dry run
  PYTHONPATH=. python3 scripts/catalog/recompute_ses_wealth_offline.py --metro nyc --write
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
KEY = {"nyc": "nyc_metro", "la": "la_metro", "sf": "sf_metro", "seattle": "seattle_metro"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--metro", required=True, choices=list(KEY))
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    from pillars.composite_indices import _area_type_from_payload, compute_hotness_score
    from pillars.status_signal import (
        _build_top_drivers, _classify_archetype, _classify_trajectory, _get_archetype_weights,
        _get_status_insight, _get_status_label, _load_baselines, _signal_strength_band,
        PROVISIONAL_COMPOSITE_WEIGHTS, _composite_score_from_weights, compute_wealth,
    )
    from data_sources.us_census_divisions import get_division

    baselines = _load_baselines()
    path = REPO / "data" / f"{args.metro}_metro_place_catalog_scores_merged.composites_recomputed.jsonl"
    out, ch = [], []
    skipped = Counter()
    for line in open(path, encoding="utf-8"):
        raw = line.rstrip("\n")
        if not raw.strip():
            continue
        r = json.loads(raw)
        s = r.get("score") if r.get("success") else None
        b = (s or {}).get("status_signal_breakdown")
        if not (isinstance(b, dict) and b.get("archetype") and s.get("status_signal") is not None):
            out.append(json.dumps(r, ensure_ascii=False)); continue
        p = s["livability_pillars"]
        li = s.get("location_info") or {}
        state = (li.get("state") or "").strip()
        from data_sources.us_census_divisions import get_division as _gd
        try:
            division = _gd(state)
        except Exception:
            division = "all"
        keys = [KEY[args.metro]]
        for k in (division, "all"):
            if k not in keys:
                keys.append(k)
        new_w = compute_wealth(p["housing_value"], keys, baselines)
        old_w = b.get("wealth")
        if new_w is None or old_w is None:
            skipped["wealth_missing"] += 1
            out.append(json.dumps(r, ensure_ascii=False)); continue
        if b.get("downgrade_reason") or b.get("original_archetype"):
            skipped["has_downgrade_override"] += 1
            out.append(json.dumps(r, ensure_ascii=False)); continue
        if abs(new_w - old_w) < 0.05:
            skipped["unchanged"] += 1
            out.append(json.dumps(r, ensure_ascii=False)); continue

        old_score, old_arch, old_traj = s["status_signal"], b["archetype"], b.get("trajectory")
        ci = b.get("classifier_inputs") or {}
        sm = p["housing_value"].get("summary") or {}
        arch, rule = _classify_archetype(
            education=b.get("education"), wealth=new_w, home_cost=b.get("home_cost"),
            wealth_gap=ci.get("wealth_gap"), occupation_neutral=b.get("occupation"),
            stability=ci.get("stability"), diversity_score=None,
            appreciation_3yr=ci.get("appreciation_3yr"), velocity_6mo=ci.get("velocity_6mo"),
            renter_pct=sm.get("renter_pct"), area_type=_area_type_from_payload(s),
        )
        traj, traj_rule = _classify_trajectory(
            wealth=new_w, home_cost=b.get("home_cost"), stability=ci.get("stability"),
            appreciation_3yr=ci.get("appreciation_3yr"), velocity_6mo=ci.get("velocity_6mo"),
            renter_pct=sm.get("renter_pct"), area_type=_area_type_from_payload(s),
        )
        b.update({"wealth": new_w, "archetype": arch, "archetype_rule": rule, "trajectory": traj,
                  "trajectory_rule": traj_rule, "status_label": _get_status_label(arch),
                  "status_insight": _get_status_insight(arch)})
        ci["wealth"] = new_w
        b["classifier_inputs"] = ci
        ww, wh, we, wo = _get_archetype_weights(arch)
        parts = [(ww, new_w), (wh, b.get("home_cost")), (we, b.get("education")), (wo, b.get("occupation"))]
        tot = sum(w for w, v in parts if v is not None)
        final = round(max(0.0, min(100.0, sum(w * v for w, v in parts if v is not None) / tot)), 1)
        pw, ph, pe, po = PROVISIONAL_COMPOSITE_WEIGHTS
        prov = _composite_score_from_weights(pw, ph, pe, po, new_w, b.get("home_cost"), b.get("education"), b.get("occupation"))
        b["provisional_composite_score"] = round(prov, 1) if prov is not None else None
        b["top_drivers"] = _build_top_drivers(new_w, b.get("home_cost"), b.get("education"), b.get("occupation"), arch)
        key, label = _signal_strength_band(final)
        b.update({"composite_score": final, "signal_strength": key, "signal_strength_label": label})
        s["status_signal"] = final
        hc = b.get("home_cost")
        s["it_score"] = compute_hotness_score(final, s.get("local_scene_score"), hc if isinstance(hc, (int, float)) else None,
                                              s.get("happiness_index"), s.get("total_score"))
        ch.append((r["catalog"]["name"], old_w, new_w, old_score, final, old_arch, arch, old_traj, traj))
        out.append(json.dumps(r, ensure_ascii=False))

    print(f"{args.metro}: {len(ch)} changed; skipped {dict(skipped)}")
    if ch:
        d = [c[4] - c[3] for c in ch]
        print(f"  score delta mean {sum(d)/len(d):+.1f}, mean|d| {sum(map(abs,d))/len(d):.1f}, max up {max(d):+.1f}, max down {min(d):+.1f}")
        print("  archetype changes:", Counter((c[5], c[6]) for c in ch if c[5] != c[6]).most_common(12))
        print("  trajectory changes:", sum(1 for c in ch if c[7] != c[8]))
        for c in sorted(ch, key=lambda c: -abs(c[4] - c[3]))[:15]:
            print(f"    {c[0]:<22}wealth {c[1]:5.1f}->{c[2]:5.1f}  score {c[3]:5.1f}->{c[4]:5.1f}  {c[5]}->{c[6]}")
    if args.write:
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
        print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

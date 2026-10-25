#!/usr/bin/env python3
"""
Offline: rewrite the economic_opportunity pillar in catalog composites files with the national baseline.

Uses the per-area metrics built by scripts/baselines/build_economic_national_baseline.py
(data/economic_area_metrics_national.json), the same normalizer and market-components helper the live
pillar uses (data_sources.normalization.normalize_national_0_100, pillars.economic_opportunity
.compute_market_components), and the stored job_access_score. No API calls. Each place is matched to its
metro or micro area by principal city and state; a place is skipped (and listed) if the match is not
unique or if the stored raw metrics disagree with the matched area's (a wrong match). Afterwards run
recompute_catalog_composites.py --in-place --no-census so the composites that read economic follow.

  PYTHONPATH=. python3 scripts/catalog/recompute_economic_national_offline.py                  # dry run
  PYTHONPATH=. python3 scripts/catalog/recompute_economic_national_offline.py --write --backup-dir <dir>
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)  # normalization reads data/economic_baselines.json relative to the repo root

from data_sources.normalization import normalize_national_0_100  # noqa: E402
from pillars.economic_opportunity import _fallback_normalize, compute_market_components  # noqa: E402

JOB_WEIGHT, MARKET_WEIGHT = 0.55, 0.45  # keep in step with pillars/economic_opportunity.py
SCALE = [("unemployment_rate", "unemployment_rate", True), ("emp_pop_ratio", "emp_pop_ratio", False),
         ("net_estab_entry_per_1k", "net_estab_entry_per_1k", False), ("estabs_per_1k", "estabs_per_1k", False),
         ("wage_p25_annual", "wage_p25_annual", False), ("wage_p75_annual", "wage_p75_annual", False),
         ("qcew_employment_per_1k", "qcew_employment_per_1k", False),
         ("qcew_employment_growth_pct", "qcew_employment_growth_pct", False),
         ("log10_employment", "log10_employment", False), ("log10_establishments", "log10_establishments", False),
         ("industry_hhi", "industry_diversity", True), ("anchored_balance", "anchored_balance", False)]
# stored summary key -> (area metric, tolerance for the wrong-match guard)
GUARD = {"employment_to_population_pct": ("emp_pop_ratio", 0.06), "estabs_per_1k": ("estabs_per_1k", 0.006),
         "net_estab_entry_per_1k": ("net_estab_entry_per_1k", 0.006), "industry_diversity_hhi": ("industry_hhi", 0.00006)}


def area_key(name: str) -> str:
    s = re.sub(r"\s+(Metro|Micro) Area$", "", name or "").strip().lower()
    city, _, st = s.partition(",")
    return city.split("-")[0].strip() + "|" + st.strip().split("-")[0].strip()


def recompute(score: dict, area: dict):
    eo = (score.get("livability_pillars") or {}).get("economic_opportunity")
    if not eo or not isinstance(eo.get("score"), (int, float)):
        return None
    summary = eo.get("summary") or {}
    fallback = []
    sub = {}
    for metric, key, invert in SCALE:
        v = area.get(metric)
        if v is None:
            sub[key] = None
            continue
        sc = normalize_national_0_100(metric=metric, value=v, invert=invert)
        if sc is None:
            sc = _fallback_normalize(metric, v, invert=invert)
            if sc is not None:
                fallback.append(metric)
        sub[key] = sc
    mc = compute_market_components(sub)
    mq = mc["base_final_score"]
    ja = summary.get("job_access_score")
    final = round(JOB_WEIGHT * ja + MARKET_WEIGHT * mq, 1) if isinstance(ja, (int, float)) else round(mq, 1)

    def block(prefix, weights):
        return {"score": float(mc[f"{prefix}_score"] or 0.0), "weights": mc[f"{prefix}_renorm"],
                "metrics": {k: sub.get(k) for k in weights}}
    from pillars.economic_opportunity import DENSITY_WEIGHTS, ECOSYSTEM_WEIGHTS, MOBILITY_WEIGHTS, RESILIENCE_WEIGHTS
    breakdown = {k: v for k, v in (eo.get("breakdown") or {}).items()}
    breakdown.update({"density": block("density", DENSITY_WEIGHTS), "mobility": block("mobility", MOBILITY_WEIGHTS),
                      "ecosystem": block("ecosystem", ECOSYSTEM_WEIGHTS), "resilience": block("resilience", RESILIENCE_WEIGHTS),
                      "component_weights": mc["base_component_renorm"]})
    eo["breakdown"] = breakdown
    r = lambda v, n: round(float(v), n) if isinstance(v, (int, float)) else None
    summary.update({
        "unemployment_rate_pct": r(area.get("unemployment_rate"), 1),
        "employment_to_population_pct": r(area.get("emp_pop_ratio"), 1),
        "estabs_per_1k": r(area.get("estabs_per_1k"), 2),
        "net_estab_entry_per_1k": r(area.get("net_estab_entry_per_1k"), 2),
        "wage_p25_annual": int(area["wage_p25_annual"]) if "wage_p25_annual" in area else None,
        "wage_p75_annual": int(area["wage_p75_annual"]) if "wage_p75_annual" in area else None,
        "qcew_employment_per_1k": r(area.get("qcew_employment_per_1k"), 2),
        "qcew_employment_growth_pct": r(area.get("qcew_employment_growth_pct"), 2),
        "industry_diversity_hhi": r(area.get("industry_hhi"), 4),
        "anchored_balance": r(area.get("anchored_balance"), 3),
        "market_quality_score": round(mq, 1),
        "employment_source": "census_cbp",
        "job_access_status": "ok" if isinstance(ja, (int, float)) else "no_grid_coverage",
        "baseline_fallback_metrics": sorted(set(fallback)),
    })
    eo["summary"] = summary
    old = eo["score"]
    eo["base_score"] = round(mq, 1)
    eo["score"] = final
    if isinstance(eo.get("weight"), (int, float)):
        eo["contribution"] = round(eo["weight"] * final / 100.0, 4)
    return old, final


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--backup-dir")
    ap.add_argument("--glob", default=str(ROOT / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))
    a = ap.parse_args()
    if a.write and not a.backup_dir:
        sys.exit("--write requires --backup-dir")
    areas = json.loads((ROOT / "data" / "economic_area_metrics_national.json").read_text())
    by_key = {}
    for code, v in areas.items():
        by_key.setdefault(area_key(v["name"]), []).append(v)
    skipped = {"no_match": [], "ambiguous": [], "guard": [], "no_pillar": 0}
    changed = 0
    deltas, tdeltas = [], []
    per_metro = {}
    for path in sorted(glob.glob(a.glob)):
        metro = os.path.basename(path).split("_metro")[0]
        mtime = os.path.getmtime(path)
        lines = Path(path).read_text(encoding="utf-8").split("\n")
        out, old_vals, n = [], {}, 0
        for line in lines:
            if not line.strip():
                out.append(line)
                continue
            try:
                rec = json.loads(line)
            except Exception:
                out.append(line)
                continue
            s = rec.get("score") or {}
            eo = (s.get("livability_pillars") or {}).get("economic_opportunity")
            if not eo or not isinstance(eo.get("score"), (int, float)):
                skipped["no_pillar"] += 1
                out.append(line)
                continue
            summ = eo.get("summary") or {}
            cat = rec.get("catalog")
            nm = cat.get("name") if isinstance(cat, dict) else s.get("input")
            matches = by_key.get(area_key(summ.get("geo_name") or ""), [])
            if not matches:
                skipped["no_match"].append(f"{metro}|{nm}|{summ.get('geo_name')}")
                out.append(line)
                continue
            if len(matches) > 1:
                skipped["ambiguous"].append(f"{metro}|{nm}|{summ.get('geo_name')}")
                out.append(line)
                continue
            area = matches[0]
            bad = [k for k, (m, tol) in GUARD.items() if isinstance(summ.get(k), (int, float)) and m in area and abs(summ[k] - area[m]) > tol]
            if bad:
                skipped["guard"].append(f"{metro}|{nm}|{summ.get('geo_name')}|{bad}")
                out.append(line)
                continue
            P = s["livability_pillars"]
            old_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
            old_total = s.get("total_score")
            old_snapshot = json.loads(json.dumps(eo))
            res = recompute(s, area)
            tb = (s.get("total_score_breakdown") or {}).get("economic_opportunity")
            if isinstance(tb, dict):
                tb["score"], tb["contribution"] = eo["score"], eo["contribution"]
            new_sum = sum((v.get("contribution") or 0) for v in P.values() if isinstance(v, dict))
            if old_total is not None:
                if abs(round(old_sum, 2) - old_total) <= 0.0051:
                    s["total_score"] = round(new_sum, 2)
                else:
                    s["total_score"] = round(old_total + (new_sum - old_sum), 2)
                tdeltas.append(s["total_score"] - old_total)
            old_vals[f"{metro}|{nm}"] = {"economic_opportunity": old_snapshot, "total_score": old_total,
                                         "total_score_breakdown_economic_opportunity": (s.get("total_score_breakdown") or {}).get("economic_opportunity")}
            deltas.append(res[1] - res[0])
            out.append(json.dumps(rec, ensure_ascii=False))
            n += 1
        per_metro[metro] = n
        changed += n
        if a.write and n:
            if os.path.getmtime(path) != mtime:
                sys.exit(f"{path} changed while running; aborting")
            b = Path(a.backup_dir)
            b.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, b / os.path.basename(path))
            (b / f"{metro}_old_economic_values.json").write_text(json.dumps(old_vals))
            tmp = path + ".tmp"
            Path(tmp).write_text("\n".join(out), encoding="utf-8")
            os.replace(tmp, path)
    print("mode:", "WRITE" if a.write else "DRY RUN")
    print("records changed:", changed, per_metro)
    print("skipped:", {k: (len(v) if isinstance(v, list) else v) for k, v in skipped.items()})
    for k in ("no_match", "ambiguous", "guard"):
        for x in skipped[k][:6]:
            print("  ", k, x)
    if deltas:
        import statistics as st
        print("economic score delta: mean %.2f min %.1f max %.1f | total_score delta mean %.3f min %.2f max %.2f" % (
            st.mean(deltas), min(deltas), max(deltas), st.mean(tdeltas), min(tdeltas), max(tdeltas)))
    Path(a.backup_dir or ROOT / "analysis").mkdir(parents=True, exist_ok=True)
    (Path(a.backup_dir) / "skipped_economic_places.json" if a.backup_dir else ROOT / "analysis" / "skipped_economic_places_dryrun.json").write_text(json.dumps(skipped, indent=1))


if __name__ == "__main__":
    main()

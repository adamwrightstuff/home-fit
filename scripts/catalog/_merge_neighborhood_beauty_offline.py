#!/usr/bin/env python3
"""
Offline merge of built_beauty + natural_beauty -> neighborhood_beauty in the catalogs.

NO live scoring. Uses each row's already-stored built_beauty / natural_beauty scores
and details, blends them with the validated density+area-type formula
(pillars.neighborhood_beauty.blend_scores), and emits a single neighborhood_beauty
pillar with the exact structure main.py produces live (sub-scores + nested details +
summaries via main.py's own helper functions). Then recomputes equal-weight totals
(13-pillar, schools-off, matching the catalog convention) and composites.

Run from repo root with PYTHONPATH=. . Pass --check to print Chelsea only (no write).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pillars import neighborhood_beauty as nb  # noqa: E402
from pillars.composite_indices import recompute_composites_from_payload  # noqa: E402

# main.py's exact summary builders (reuse so catalog == live shape).
from main import (  # noqa: E402
    _extract_built_beauty_summary,
    _natural_beauty_summary_with_preference,
)

FILES = [
    "data/la_metro_place_catalog_scores_merged.jsonl",
    "data/nyc_metro_place_catalog_scores_merged.jsonl",
]


def _load_rerun():
    path = REPO / "scripts" / "catalog" / "rerun_failed_catalog_pillars.py"
    spec = importlib.util.spec_from_file_location("rerun_failed_catalog_pillars", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_RERUN = _load_rerun()


def _merge_one(score: dict) -> bool:
    """Replace built_beauty + natural_beauty with neighborhood_beauty in-place. Returns True if merged."""
    lp = score.get("livability_pillars")
    if not isinstance(lp, dict):
        return False
    if "neighborhood_beauty" in lp:
        return False
    bb = lp.get("built_beauty")
    nbp = lp.get("natural_beauty")
    if not isinstance(bb, dict) or not isinstance(nbp, dict):
        return False

    built_score = float(bb.get("score") or 0.0)
    natural_score = float(nbp.get("score") or 0.0)
    built_details = bb.get("details") or {}
    natural_details = nbp.get("details") or {}

    cls = (built_details.get("architectural_analysis") or {}).get("classification") or {}
    density = cls.get("density")
    eff_at = cls.get("effective_area_type")

    blend = nb.blend_scores(built_score, natural_score, density, eff_at)
    score_val = blend["score"]
    bw = blend["built_weight"]

    merged = {
        "score": score_val,
        "weight": 0.0,           # set by recompute_totals
        "importance_level": None,
        "contribution": 0.0,     # set by recompute_totals
        "breakdown": {
            "built_beauty_score": built_score,
            "natural_beauty_score": natural_score,
            "built_weight": bw,
            "effective_area_type": eff_at,
            "density": density,
        },
        "summary": {
            "built_beauty": _extract_built_beauty_summary(built_details),
            "natural_beauty": _natural_beauty_summary_with_preference(natural_details, None),
            "built_weight": bw,
        },
        "built_beauty_score": built_score,
        "natural_beauty_score": natural_score,
        "built_weight": bw,
        "details": {
            "built_beauty": built_details,
            "natural_beauty": natural_details,
            "built_weight": bw,
            "effective_area_type": eff_at,
            "density": density,
            "source": "neighborhood_beauty_offline_blend",
        },
        "confidence": bb.get("confidence", 0),
        "data_quality": bb.get("data_quality", {}),
        "area_classification": bb.get("area_classification", {}),
    }

    # Rebuild dict preserving order, neighborhood_beauty where active_outdoors-adjacent.
    new_lp = {}
    for k, v in lp.items():
        if k == "built_beauty":
            new_lp["neighborhood_beauty"] = merged
        elif k == "natural_beauty":
            continue
        else:
            new_lp[k] = v
    if "neighborhood_beauty" not in new_lp:
        new_lp["neighborhood_beauty"] = merged
    score["livability_pillars"] = new_lp
    return True


def _recompute(score: dict) -> None:
    _RERUN.recompute_totals(score)
    comp = recompute_composites_from_payload(score)
    for k in (
        "longevity_index", "longevity_index_contributions", "longevity_index_breakdown",
        "status_signal", "status_signal_breakdown",
        "happiness_index", "happiness_index_breakdown", "total_score_breakdown",
    ):
        if comp.get(k) is not None:
            score[k] = comp[k]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="Print Chelsea result only, no write")
    args = ap.parse_args()

    if args.check:
        f = "data/nyc_metro_place_catalog_scores_merged.jsonl"
        for line in (REPO / f).read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if (rec.get("catalog") or {}).get("name") != "Chelsea":
                continue
            sc = rec["score"]
            ok = _merge_one(sc)
            _recompute(sc)
            nbp = sc["livability_pillars"]["neighborhood_beauty"]
            print("merged:", ok)
            print("  built=", nbp["built_beauty_score"], "natural=", nbp["natural_beauty_score"],
                  "built_weight=", nbp["built_weight"], "-> neighborhood_beauty=", nbp["score"])
            print("  weight=", nbp["weight"], "contribution=", nbp["contribution"])
            print("  total_score=", sc.get("total_score"), "longevity=", sc.get("longevity_index"),
                  "happiness=", sc.get("happiness_index"), "status=", sc.get("status_signal"))
            print("  has built_beauty key still?", "built_beauty" in sc["livability_pillars"])
            print("  summary.built_beauty keys:", list(nbp["summary"]["built_beauty"].keys())[:6])
            print("  summary.natural_beauty keys:", list(nbp["summary"]["natural_beauty"].keys())[:6])
            return 0
        print("Chelsea not found")
        return 1

    for f in FILES:
        out = []
        merged = 0
        for line in (REPO / f).read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            sc = rec.get("score")
            if isinstance(sc, dict) and rec.get("success") and _merge_one(sc):
                _recompute(sc)
                rec["score"] = sc
                merged += 1
            out.append(json.dumps(rec, ensure_ascii=False))
        (REPO / f).write_text("\n".join(out) + "\n", encoding="utf-8")
        print(f"{f}: merged={merged} rows={len(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

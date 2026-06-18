#!/usr/bin/env python3
"""
Offline built_beauty rescorer (preview-safe).

Recomputes built_beauty for every place from the catalog's STORED OSM-derived inputs plus
fast GEE calls (GHSL height, Microsoft footprint coverage) and the coherence fix -- NO live
OSM fetch. Writes the rescored catalog to --output (never overwrites the input unless you
point --output at it explicitly), so you can inspect before committing anything.

Compares the new self-consistent score against the catalog's stored headline (which is known
to be a stale orphan inconsistent with its own components -- see session diagnosis).

Usage (preview, originals untouched):
  PYTHONPATH=. python3 scripts/catalog/rescore_built_beauty_offline.py \
    --input data/la_metro_place_catalog_scores_merged.jsonl \
    --output /tmp/la_rescored_preview.jsonl
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except Exception:
    pass

from data_sources.arch_diversity import (
    score_architectural_diversity_as_beauty,
    _calibrate_ghsl_height_diversity,
)
from data_sources.gee_api import (
    get_building_height_diversity_ghsl,
    get_building_coverage_ms_footprints,
)
from pillars.beauty_common import normalize_beauty_score


def recompute_arch(aa, m, lat, lon):
    """Recompute the 0-50 architecture component with current code + GHSL/MS/coherence fixes,
    from stored inputs only (no live OSM). Returns (new_arch_0_50, substitution_notes)."""
    area_type = aa["classification"]["effective_area_type"]
    hs = dict(aa.get("height_stats") or {})
    hd = m.get("height_diversity", 0)
    cov = m.get("built_coverage_ratio")
    warning = aa.get("data_warning")
    notes = []

    # Height: only on genuine height fabrication
    if warning == "suspiciously_low_height_diversity":
        ghsl = get_building_height_diversity_ghsl(lat, lon)
        if ghsl:
            hd = _calibrate_ghsl_height_diversity(ghsl["std_height_m"])
            hs["mean_levels"] = max(1.0, ghsl["mean_height_m"] / 3.0)
            hs["std_levels"] = ghsl["std_height_m"] / 3.0
            hs["single_story_share"] = min(1.0, max(0.0, 1.0 - (ghsl["std_height_m"] / 3.0) / 1.5))
            notes.append("ghsl_height")

    # Coverage: only when Microsoft shows MORE than OSM (real undercount)
    if warning == "low_building_coverage":
        ms = get_building_coverage_ms_footprints(lat, lon)
        if ms and ms["built_coverage_ratio"] > (cov or 0.0):
            cov = ms["built_coverage_ratio"]
            notes.append("ms_coverage")

    kw = dict(
        area_type=area_type, density=aa["classification"].get("density"),
        built_coverage_ratio=cov,
        historic_landmarks=aa.get("historic_context", {}).get("landmarks"),
        median_year_built=aa.get("historic_context", {}).get("median_year_built"),
        vintage_share=aa.get("historic_context", {}).get("vintage_pct"),
        lat=None, lon=None,
        material_profile=aa.get("material_profile"), heritage_profile=aa.get("heritage_profile"),
        type_category_diversity=m.get("type_category_diversity"), height_stats=hs,
        contextual_tags=aa["classification"].get("contextual_tags"),
        pre_1940_pct=None, nrhp_count=aa.get("historic_context", {}).get("nrhp_count"),
        form_metrics_confidence_override=aa.get("form_metrics_confidence") or {},
        metric_overrides={k: m[k] for k in
                          ("block_grain", "streetwall_continuity", "setback_consistency", "facade_rhythm")
                          if m.get(k) is not None},
    )
    arch, meta = score_architectural_diversity_as_beauty(
        hd, m.get("type_diversity", 0), m.get("footprint_variation", 0), **kw)
    return arch, meta, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True, help="preview output path; input is never modified")
    args = ap.parse_args()
    if Path(args.output).resolve() == Path(args.input).resolve():
        print("Refusing to overwrite input. Point --output elsewhere.", file=sys.stderr)
        sys.exit(1)

    rows = [json.loads(l) for l in open(args.input) if l.strip()]
    rep = []
    for rec in rows:
        bb = rec.get("score", {}).get("livability_pillars", {}).get("built_beauty")
        if not bb:
            continue
        d = bb["details"]; aa = d["architectural_analysis"]; m = aa["metrics"]
        cat = rec["catalog"]; name = cat.get("name", "?")
        try:
            lat, lon = float(cat["lat"]), float(cat["lon"])
        except (TypeError, ValueError, KeyError):
            continue

        old_pillar = bb.get("score")

        # api_error places have error-fallback inputs, not real measurements -- offline
        # recompute would produce garbage. Leave them untouched; they need a live re-fetch.
        if aa.get("data_warning") == "api_error" or aa.get("error"):
            rep.append((name, old_pillar, old_pillar, None, "NEEDS-REFETCH", "api_error"))
            continue

        new_arch, meta, notes = recompute_arch(aa, m, lat, lon)

        # Rebuild the 0-100 pillar with the same assembly the catalog uses:
        # (arch + enhancer_bonus_scaled) * 2, capped 100, then normalized.
        enh = d.get("enhancer_bonus_scaled", 0.0) or 0.0
        raw = min(100.0, max(0.0, new_arch + enh) * 2.0)
        new_pillar, _ = normalize_beauty_score(raw, aa["classification"]["effective_area_type"])

        # Write updated values back into the record (preview copy only)
        aa["score"] = round(new_arch, 1)
        d["component_score_0_50"] = round(new_arch, 2)
        d["score_before_normalization"] = round(raw, 2)
        bb["score"] = round(new_pillar, 2)

        rep.append((name, old_pillar, round(new_pillar, 1),
                    round((new_pillar - old_pillar), 1) if old_pillar is not None else None,
                    ",".join(notes) or "-", aa.get("data_warning")))

    with open(args.output, "w") as fh:
        for rec in rows:
            fh.write(json.dumps(rec) + "\n")

    print(f"\n=== {Path(args.input).name}: {len(rep)} places rescored -> {args.output} (input untouched) ===")
    print(f"{'place':26s} {'OLD':>7s} {'NEW':>7s} {'Δ':>7s}  subs           warning")
    for name, o, n, dlt, subs, w in sorted(rep, key=lambda r: (r[3] if r[3] is not None else 0)):
        os = f"{o:.1f}" if o is not None else "  -  "
        ds = f"{dlt:+.1f}" if dlt is not None else "  -  "
        print(f"{name:26s} {os:>7s} {n:>7.1f} {ds:>7s}  {subs:14s} {w or ''}")
    deltas = [r[3] for r in rep if r[3] is not None]
    if deltas:
        ups = sum(1 for x in deltas if x > 0.5); downs = sum(1 for x in deltas if x < -0.5)
        print(f"\nsummary: {len(deltas)} places | up {ups} | down {downs} | "
              f"mean Δ {sum(deltas)/len(deltas):+.1f} | min {min(deltas):+.1f} | max {max(deltas):+.1f}")


if __name__ == "__main__":
    main()

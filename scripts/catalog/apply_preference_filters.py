#!/usr/bin/env python3
"""
Local mirror of Trovamo's filter + weight UI — all levers configurable, no hardcoded profile.

Mirrors:
  - CatalogWeightPanel  → --weight <pillar>=<None|Low|Medium|High>
  - FilterSheet chips   → --archetype, --trajectory, --local-scene, --political-lean,
                          --housing, --nb-pref, --ao-pref, --waterfront-sub, --built-form
  - Saves/loads profile → --profile <path.json>  (--save-profile to write current flags)

Usage:
  # Run with a saved profile:
  python3 scripts/catalog/apply_preference_filters.py \\
      --catalog data/nyc_metro_place_catalog_scores_merged.jsonl \\
      --profile scripts/catalog/profiles/default.json

  # Inline flags (override or replace profile):
  python3 scripts/catalog/apply_preference_filters.py \\
      --catalog data/nyc_metro_place_catalog_scores_merged.jsonl \\
      --weight community_safety=High --weight diversity=Medium \\
      --archetype Elite --archetype Affluent \\
      --trajectory Arrived \\
      --local-scene High \\
      --political-lean lean_d --political-lean moderate \\
      --nb-pref ocean --nb-pref canopy \\
      --ao-pref local_parks --ao-pref waterfront \\
      --housing sf_townhouse

  # Save current flags as a named profile:
  python3 scripts/catalog/apply_preference_filters.py ... --save-profile scripts/catalog/profiles/mine.json

  # Run tests:
  pytest tests/test_preference_filters.py -v
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Pillar keys (matches Trovamo / agent_recommend.py)
# ---------------------------------------------------------------------------

ALL_PILLARS = [
    "community_safety", "quality_education", "social_fabric",
    "neighborhood_amenities", "natural_beauty", "active_outdoors",
    "healthcare_access", "public_transit_access", "housing_value",
    "diversity", "air_travel_access", "economic_opportunity",
    "climate_risk", "political_lean", "built_environment",
]

PRIORITY_TO_NUMERIC = {"None": 0, "Low": 33, "Medium": 66, "High": 100}

# ---------------------------------------------------------------------------
# OWA helpers — mirrors frontend/lib/nbPreference.ts + aoPreference.ts
# ---------------------------------------------------------------------------

_V9_OWA_WEIGHTS = [0.62, 0.25, 0.10, 0.02, 0.01, 0.0]
_V9_COMPONENT_KEYS = ["gvi_score", "water_score", "canopy_score", "topo_score", "landcover_score", "bio_score"]
_PREFERENCE_V9_COMPONENTS: dict[str, list[str]] = {
    "mountains":    ["topo_score"],
    "ocean":        ["water_score"],
    "lakes_rivers": ["water_score"],
    "canopy":       ["gvi_score"],
}

_AO_OWA_WEIGHTS = [0.62, 0.25, 0.13]
_AO_COMPONENT_MAX = {"daily_urban_outdoors": 35.0, "wild_adventure": 50.0, "waterfront_lifestyle": 25.0}
_PREFERENCE_AO_COMPONENTS: dict[str, str] = {
    "local_parks":      "daily_urban_outdoors",
    "trails_regional":  "wild_adventure",
    "waterfront":       "waterfront_lifestyle",
}

_WATERFRONT_OWA_WEIGHTS = [0.62, 0.25, 0.13]
_WATERFRONT_KEYS = ["ocean_beach", "lake_river", "bay_harbor"]


def apply_nb_preferences_v9(v9: dict, preferences: list[str]) -> Optional[float]:
    """Re-weight NB score toward selected scenery preferences using OWA (mirrors nbPreference.ts)."""
    if not v9 or not preferences:
        return None
    water_type = (v9.get("inputs") or {}).get("water_type", "") or ""
    effective: dict[str, float] = {}
    for key in _V9_COMPONENT_KEYS:
        val = v9.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            effective[key] = float(val)
    for pref in preferences:
        if pref in ("ocean", "lakes_rivers") and "water_score" in effective:
            is_coastal = bool(re.search(r"ocean|coast|bay|harbor|sea", water_type, re.I))
            is_lake_river = bool(re.search(r"lake|reservoir|river|stream|canal", water_type, re.I))
            match = is_coastal if pref == "ocean" else is_lake_river
            if not match:
                effective["water_score"] *= 0.25
    targets: set[str] = set(c for p in preferences for c in _PREFERENCE_V9_COMPONENTS.get(p, []))
    pref_vals = [effective[t] for t in targets if t in effective]
    if not pref_vals:
        return None
    preferred = sum(pref_vals) / len(pref_vals)
    others = sorted([v for k, v in effective.items() if k not in targets], reverse=True)
    dynamic_lead = min(1.0, 0.62 + 0.38 * (preferred / 100))
    ranked = [preferred] + others
    weights = [dynamic_lead] + _V9_OWA_WEIGHTS[1:len(ranked)]
    tot = sum(weights) or 1
    return round(sum(w / tot * s for w, s in zip(weights, ranked)), 2)


def apply_ao_preferences(ao_bd: dict, preferences: list[str]) -> Optional[float]:
    """Re-weight AO score toward selected sub-components using OWA (mirrors aoPreference.ts)."""
    if not ao_bd or not preferences:
        return None
    normalized: dict[str, float] = {}
    for key, cap in _AO_COMPONENT_MAX.items():
        raw = ao_bd.get(key)
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            normalized[key] = min(100.0, float(raw) / cap * 100)
    targets: set[str] = {_PREFERENCE_AO_COMPONENTS[p] for p in preferences if p in _PREFERENCE_AO_COMPONENTS}
    pref_vals = [normalized[t] for t in targets if t in normalized]
    if not pref_vals:
        return None
    preferred = sum(pref_vals) / len(pref_vals)
    others = sorted([v for k, v in normalized.items() if k not in targets], reverse=True)
    dynamic_lead = min(1.0, 0.62 + 0.38 * (preferred / 100))
    ranked = [preferred] + others
    weights = [dynamic_lead] + _AO_OWA_WEIGHTS[1:len(ranked)]
    tot = sum(weights) or 1
    return round(sum(w / tot * s for w, s in zip(weights, ranked)), 2)


def apply_waterfront_sub_preference(ao_bd: dict, preference: str) -> Optional[float]:
    """Re-weight waterfront_lifestyle toward a specific water type (mirrors aoPreference.ts)."""
    wb = (ao_bd or {}).get("waterfront_breakdown", {})
    if not wb:
        return None
    vals = [wb.get(k, 0.0) for k in _WATERFRONT_KEYS]
    if all(v == 0 for v in vals):
        return None
    pref_idx = _WATERFRONT_KEYS.index(preference) if preference in _WATERFRONT_KEYS else -1
    if pref_idx < 0:
        return None
    pref_val = float(vals[pref_idx])
    if pref_val == 0:
        return 0.0
    others = sorted([float(v) for i, v in enumerate(vals) if i != pref_idx], reverse=True)
    dynamic_lead = min(1.0, 0.62 + 0.38 * (pref_val / 100))
    ranked = [pref_val] + others
    weights = [dynamic_lead] + _WATERFRONT_OWA_WEIGHTS[1:len(ranked)]
    tot = sum(weights) or 1
    return round(sum(w / tot * s for w, s in zip(weights, ranked)), 2)


# ---------------------------------------------------------------------------
# Core scoring helpers
# ---------------------------------------------------------------------------

def pillar_score(lp: dict, key: str) -> Optional[float]:
    p = lp.get(key, {})
    if not isinstance(p, dict):
        return None
    s = p.get("score")
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        return float(s)
    return None


def weighted_score(
    lp: dict,
    weights: dict[str, int],
    nb_adjusted: Optional[float] = None,
    ao_adjusted: Optional[float] = None,
) -> float:
    total_weight = 0
    total = 0.0
    for key, w in weights.items():
        if key == "natural_beauty" and nb_adjusted is not None:
            s: Optional[float] = nb_adjusted
        elif key == "active_outdoors" and ao_adjusted is not None:
            s = ao_adjusted
        else:
            s = pillar_score(lp, key)
        if s is None:
            continue  # skip degraded/missing pillars — don't penalise as 0
        total_weight += w
        total += w * s
    return round(total / total_weight, 2) if total_weight else 0.0


# ---------------------------------------------------------------------------
# Heritage / built character filter
# ---------------------------------------------------------------------------

# Places with heritage_count >= this are classified as "historic".
# Calibrate once we have empirical benchmarks; current value is an eyeball split
# (NYC distribution: ~73/187 above 20, ~73 in 6–20 range, ~32 at 1–5, ~4 at 0).
HERITAGE_HISTORIC_THRESHOLD = 10


def passes_heritage_filter(heritage_count: Optional[int], preference: Optional[str]) -> bool:
    """
    True when the place satisfies the built-character preference.
    Fails open (returns True) when heritage_count is None — SF has no data yet.
    'no_preference' and None preference always pass.
    """
    if not preference or preference == "no_preference":
        return True
    if heritage_count is None:
        return True
    if preference == "historic":
        return heritage_count >= HERITAGE_HISTORIC_THRESHOLD
    if preference == "contemporary":
        return heritage_count < HERITAGE_HISTORIC_THRESHOLD
    return True


# ---------------------------------------------------------------------------
# Housing stock classification — mirrors catalog-page-client.tsx thresholds
# ---------------------------------------------------------------------------

def housing_type_for(pct_low: Optional[float]) -> Optional[str]:
    if pct_low is None:
        return None
    if pct_low >= 0.25:
        return "sf_townhouse"
    if pct_low >= 0.10:
        return "small_multifamily"
    return "apartment"


def passes_housing_filter(pct_low: Optional[float], filter_types: list[str]) -> bool:
    if not filter_types:
        return True
    if pct_low is None:
        return True
    return any(
        (t == "sf_townhouse"      and pct_low >= 0.25) or
        (t == "small_multifamily" and 0.10 <= pct_low < 0.70) or
        (t == "apartment"         and pct_low < 0.30)
        for t in filter_types
    )


# ---------------------------------------------------------------------------
# Political lean classification — mirrors catalog-page-client.tsx thresholds
# ---------------------------------------------------------------------------

LEAN_THRESHOLDS = {
    "strong_d": (0.50,  1.01),
    "lean_d":   (0.15,  0.50),
    "moderate": (-0.15, 0.15),
    "lean_r":   (-0.50, -0.15),
    "strong_r": (-1.01, -0.50),
}


def lean_label_for(lean_2024: Optional[float]) -> Optional[str]:
    if lean_2024 is None:
        return None
    for label, (lo, hi) in LEAN_THRESHOLDS.items():
        if lo <= lean_2024 < hi:
            return label
    return None


def passes_political_filter(lean_2024: Optional[float], filter_labels: list[str]) -> bool:
    if not filter_labels:
        return True
    if lean_2024 is None:
        return False
    return any(
        lo <= lean_2024 < hi
        for label in filter_labels
        for lo, hi in [LEAN_THRESHOLDS.get(label, (999, 999))]
    )


# ---------------------------------------------------------------------------
# Hard filter application
# ---------------------------------------------------------------------------

def passes_hard_filters(row: dict, cfg: dict) -> tuple[bool, str]:
    score = row.get("score", {})
    lp = score.get("livability_pillars", {})
    ss = score.get("status_signal_breakdown", {}) or {}

    archetypes = cfg.get("archetypes", [])
    if archetypes:
        arch = ss.get("archetype") if isinstance(ss, dict) else None
        if arch not in archetypes:
            return False, f"archetype={arch}"

    trajectories = cfg.get("trajectories", [])
    if trajectories:
        traj = ss.get("trajectory") if isinstance(ss, dict) else None
        if traj not in trajectories:
            return False, f"trajectory={traj}"

    local_scene = cfg.get("local_scene")
    if local_scene and local_scene != "all":
        ls = score.get("local_scene_bucket")
        if local_scene == "High" and ls != "High":
            return False, f"local_scene={ls}"
        if local_scene == "Some" and ls == "Low":
            return False, f"local_scene={ls}"

    area_types = cfg.get("area_types", [])
    if area_types:
        nb_bd = (lp.get("neighborhood_beauty") or {}).get("breakdown") or {}
        effective_area_type = nb_bd.get("effective_area_type") if isinstance(nb_bd, dict) else None
        if effective_area_type not in area_types:
            return False, f"area_type={effective_area_type}"

    built_forms = cfg.get("built_forms", [])
    if built_forms:
        be_summary = (lp.get("built_environment") or {}).get("summary") or {}
        built_form = be_summary.get("built_form_label") if isinstance(be_summary, dict) else None
        if built_form not in built_forms:
            return False, f"built_form={built_form}"

    built_character = cfg.get("built_character")
    if built_character and built_character != "no_preference":
        be_summary = (lp.get("built_environment") or {}).get("summary") or {}
        hc = be_summary.get("heritage_count") if isinstance(be_summary, dict) else None
        hc = int(hc) if hc is not None else None
        if not passes_heritage_filter(hc, built_character):
            return False, f"heritage_count={hc}"

    political_lean = cfg.get("political_lean", [])
    if political_lean:
        pl_bd = (lp.get("political_lean") or {}).get("breakdown") or {}
        lean_2024 = pl_bd.get("lean_2024") if isinstance(pl_bd, dict) else None
        if not passes_political_filter(lean_2024, political_lean):
            label = pl_bd.get("label", "?") if isinstance(pl_bd, dict) else "?"
            return False, f"pol_lean={label}"

    housing = cfg.get("housing", [])
    if housing:
        hs = score.get("housing_stock") or {}
        pct_ld = hs.get("pct_low_density") if isinstance(hs, dict) else None
        if not passes_housing_filter(pct_ld, housing):
            return False, f"pct_low_density={pct_ld}"

    return True, "ok"


# ---------------------------------------------------------------------------
# Score row
# ---------------------------------------------------------------------------

def score_row(row: dict, weights: dict[str, int], nb_prefs: list[str], ao_prefs: list[str], waterfront_sub: Optional[str]) -> dict:
    catalog = row.get("catalog", {})
    score = row.get("score", {})
    lp = score.get("livability_pillars", {})

    nb = lp.get("natural_beauty") or {}
    v9 = nb.get("v9_breakdown") if isinstance(nb, dict) else {}
    v9 = v9 if isinstance(v9, dict) else {}
    nb_inp = v9.get("inputs") or {}
    water_type = nb_inp.get("water_type") if isinstance(nb_inp, dict) else None
    canopy_score = v9.get("canopy_score") if isinstance(v9, dict) else None

    ao_bd = (lp.get("active_outdoors") or {}).get("breakdown") or {}
    ao_bd = ao_bd if isinstance(ao_bd, dict) else {}
    waterfront_bd = ao_bd.get("waterfront_breakdown") or {}
    bay_harbor = waterfront_bd.get("bay_harbor", 0.0) if isinstance(waterfront_bd, dict) else 0.0
    daily_urban = ao_bd.get("daily_urban_outdoors", 0.0) if isinstance(ao_bd, dict) else 0.0
    wf_lifestyle = ao_bd.get("waterfront_lifestyle", 0.0) if isinstance(ao_bd, dict) else 0.0

    nb_adjusted = apply_nb_preferences_v9(v9, nb_prefs)
    ao_adjusted = apply_ao_preferences(ao_bd, ao_prefs)

    if waterfront_sub and ao_adjusted is not None:
        wf_sub_score = apply_waterfront_sub_preference(ao_bd, waterfront_sub)
        if wf_sub_score is not None:
            ao_adjusted = wf_sub_score

    final = weighted_score(lp, weights, nb_adjusted=nb_adjusted, ao_adjusted=ao_adjusted)

    ss = score.get("status_signal_breakdown") or {}
    pl_bd = (lp.get("political_lean") or {}).get("breakdown") or {}
    hs = score.get("housing_stock") or {}
    pct_ld = hs.get("pct_low_density") if isinstance(hs, dict) else None
    be_summary = (lp.get("built_environment") or {}).get("summary") or {}
    built_form = be_summary.get("built_form_label") if isinstance(be_summary, dict) else None
    lean_2024 = pl_bd.get("lean_2024") if isinstance(pl_bd, dict) else None

    display_pillars = [k for k in ALL_PILLARS if weights.get(k, 0) > 0]

    def _display_score(key: str) -> Optional[float]:
        if key == "natural_beauty" and nb_adjusted is not None:
            return round(nb_adjusted, 1)
        if key == "active_outdoors" and ao_adjusted is not None:
            return round(ao_adjusted, 1)
        s = pillar_score(lp, key)
        return round(s, 1) if s is not None else None

    return {
        "name":           catalog.get("name", "?"),
        "state":          catalog.get("state_abbr", "?"),
        "county":         catalog.get("county_borough", ""),
        "final_score":    final,
        "nb_adjusted":    round(nb_adjusted, 1) if nb_adjusted is not None else None,
        "ao_adjusted":    round(ao_adjusted, 1) if ao_adjusted is not None else None,
        "archetype":      ss.get("archetype") if isinstance(ss, dict) else None,
        "trajectory":     ss.get("trajectory") if isinstance(ss, dict) else None,
        "local_scene":    score.get("local_scene_bucket"),
        "built_form":     built_form,
        "pct_low_density": pct_ld,
        "housing_type":   housing_type_for(pct_ld),
        "water_type":     water_type,
        "canopy_score":   round(canopy_score, 1) if canopy_score else None,
        "bay_harbor":     round(bay_harbor, 2),
        "ao_daily_parks": round(daily_urban, 1),
        "ao_waterfront":  round(wf_lifestyle, 1),
        "pol_label":      lean_label_for(lean_2024),
        "lean_2024":      round(lean_2024, 3) if lean_2024 is not None else None,
        "pillar_scores":  {k: _display_score(k) for k in display_pillars},
    }


# ---------------------------------------------------------------------------
# Catalog processing
# ---------------------------------------------------------------------------

def process_catalog(path: Path, cfg: dict, weights: dict[str, int], results: list) -> tuple[int, int]:
    nb_prefs = cfg.get("nb_prefs", [])
    ao_prefs = cfg.get("ao_prefs", [])
    waterfront_sub = cfg.get("waterfront_sub")
    passed = failed = 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not row.get("success", True):
                continue
            ok, _ = passes_hard_filters(row, cfg)
            if ok:
                results.append(score_row(row, weights, nb_prefs, ao_prefs, waterfront_sub))
                passed += 1
            else:
                failed += 1
    return passed, failed


# ---------------------------------------------------------------------------
# Profile load / save
# ---------------------------------------------------------------------------

DEFAULT_PROFILE: dict = {
    "weights": {k: "None" for k in ALL_PILLARS},
    "filters": {
        "archetypes": [],
        "trajectories": [],
        "local_scene": "all",
        "built_forms": [],
        "political_lean": [],
        "housing": [],
        "built_character": None,
    },
    "preferences": {
        "nb": [],
        "ao": [],
        "waterfront_sub": None,
    },
}


def load_profile(path: str) -> dict:
    return json.loads(Path(path).read_text())


def save_profile(path: str, profile: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(profile, indent=2, ensure_ascii=False))
    print(f"Saved profile → {path}")


def resolve_weights(profile_weights: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for pillar in ALL_PILLARS:
        level = profile_weights.get(pillar, "None")
        out[pillar] = PRIORITY_TO_NUMERIC.get(level, 0)
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Local mirror of Trovamo filter + weight UI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--catalog", action="append", required=True,
                   help="Path to catalog JSONL (repeat for multiple metros)")
    p.add_argument("--profile", default=None,
                   help="Load settings from JSON profile file")
    p.add_argument("--save-profile", default=None, metavar="PATH",
                   help="Save resolved settings to JSON profile file")
    p.add_argument("--weight", action="append", default=[], metavar="PILLAR=LEVEL",
                   help="Set pillar weight, e.g. --weight diversity=Medium (None/Low/Medium/High). Repeatable.")
    p.add_argument("--archetype", action="append", default=[], metavar="NAME",
                   help="Allow archetype (Elite, Affluent, …). Repeatable. Empty = all.")
    p.add_argument("--trajectory", action="append", default=[], metavar="NAME",
                   help="Allow trajectory (Arrived, Stable, …). Repeatable. Empty = all.")
    p.add_argument("--local-scene", default=None, choices=["all", "Some", "High"],
                   help="Local scene minimum (all/Some/High)")
    p.add_argument("--built-form", action="append", default=[], metavar="LABEL",
                   help="Allow built form label. Repeatable. Empty = all.")
    p.add_argument("--political-lean", action="append", default=[], metavar="LABEL",
                   help="Allow political lean (strong_d/lean_d/moderate/lean_r/strong_r). Repeatable. Empty = all.")
    p.add_argument("--housing", action="append", default=[], metavar="TYPE",
                   help="Allow housing type (sf_townhouse/small_multifamily/apartment). Repeatable. Empty = all.")
    p.add_argument("--built-character", default=None,
                   choices=["historic", "contemporary", "no_preference"],
                   help="Filter by neighborhood character: historic (heritage_count >= threshold) or contemporary.")
    p.add_argument("--nb-pref", action="append", default=[], metavar="PREF",
                   help="Natural beauty sub-preference (mountains/ocean/lakes_rivers/canopy). Repeatable.")
    p.add_argument("--ao-pref", action="append", default=[], metavar="PREF",
                   help="Active outdoors sub-preference (local_parks/trails_regional/waterfront). Repeatable.")
    p.add_argument("--waterfront-sub", default=None,
                   choices=["ocean_beach", "lake_river", "bay_harbor"],
                   help="Waterfront sub-preference for OWA re-weighting")
    p.add_argument("--output", default=None, help="Write JSON results to file")
    p.add_argument("--top", type=int, default=30, help="Print top N results (default 30)")
    return p


def main(argv: Optional[list[str]] = None) -> None:
    args = build_parser().parse_args(argv)

    # Start from profile or empty defaults
    profile = load_profile(args.profile) if args.profile else json.loads(json.dumps(DEFAULT_PROFILE))

    # Apply CLI weight overrides
    for wstr in args.weight:
        if "=" not in wstr:
            print(f"ERROR: --weight must be PILLAR=LEVEL, got: {wstr}", file=sys.stderr)
            sys.exit(1)
        pillar, level = wstr.split("=", 1)
        if pillar not in ALL_PILLARS:
            print(f"ERROR: unknown pillar '{pillar}'. Valid: {ALL_PILLARS}", file=sys.stderr)
            sys.exit(1)
        if level not in PRIORITY_TO_NUMERIC:
            print(f"ERROR: unknown level '{level}'. Valid: {list(PRIORITY_TO_NUMERIC)}", file=sys.stderr)
            sys.exit(1)
        profile.setdefault("weights", {})[pillar] = level

    # Apply CLI filter overrides (only if provided)
    filters = profile.setdefault("filters", {})
    if args.archetype:
        filters["archetypes"] = args.archetype
    if args.trajectory:
        filters["trajectories"] = args.trajectory
    if args.local_scene:
        filters["local_scene"] = args.local_scene
    if args.built_form:
        filters["built_forms"] = args.built_form
    if args.political_lean:
        filters["political_lean"] = args.political_lean
    if args.housing:
        filters["housing"] = args.housing
    if args.built_character:
        filters["built_character"] = args.built_character

    prefs = profile.setdefault("preferences", {})
    if args.nb_pref:
        prefs["nb"] = args.nb_pref
    if args.ao_pref:
        prefs["ao"] = args.ao_pref
    if args.waterfront_sub:
        prefs["waterfront_sub"] = args.waterfront_sub

    # Build resolved config
    weights = resolve_weights(profile.get("weights", {}))
    cfg = {
        "archetypes":     filters.get("archetypes", []),
        "trajectories":   filters.get("trajectories", []),
        "local_scene":    filters.get("local_scene", "all"),
        "built_forms":    filters.get("built_forms", []),
        "political_lean": filters.get("political_lean", []),
        "housing":        filters.get("housing", []),
        "built_character": filters.get("built_character"),
        "nb_prefs":       prefs.get("nb", []),
        "ao_prefs":       prefs.get("ao", []),
        "waterfront_sub": prefs.get("waterfront_sub"),
    }

    if args.save_profile:
        save_profile(args.save_profile, profile)

    # Process catalogs
    results: list[dict] = []
    for p in args.catalog:
        path = Path(p)
        if not path.exists():
            print(f"WARN: {path} not found, skipping")
            continue
        passed, failed = process_catalog(path, cfg, weights, results)
        print(f"{path.name}: {passed} passed filters, {failed} excluded")

    results.sort(key=lambda x: x["final_score"], reverse=True)

    active_pillars = [k for k in ALL_PILLARS if weights.get(k, 0) > 0]
    print(f"\n=== TOP {min(args.top, len(results))} of {len(results)} passing filters ===")
    print(f"Weights: { {k: v for k, v in profile.get('weights', {}).items() if v != 'None'} }")
    print(f"Filters: archetypes={cfg['archetypes']} | trajectories={cfg['trajectories']} | "
          f"local_scene={cfg['local_scene']} | pol_lean={cfg['political_lean']} | housing={cfg['housing']}")
    if cfg["nb_prefs"] or cfg["ao_prefs"]:
        print(f"Prefs:   NB={cfg['nb_prefs']} | AO={cfg['ao_prefs']}"
              + (f" | waterfront_sub={cfg['waterfront_sub']}" if cfg["waterfront_sub"] else ""))
    print()

    col_pillars = active_pillars[:6]
    hdr = f"{'Rank':<5} {'Name':<26} {'St':<4} {'Score':>6} {'Arch':<10} {'Traj':<14} {'Scene':<6} {'Pol':<8} {'Housing':<14}"
    for pk in col_pillars:
        hdr += f" {pk[:5]:>6}"
    print(hdr)
    print("-" * (len(hdr) + 5))

    for i, r in enumerate(results[:args.top], 1):
        ps = r["pillar_scores"]
        row_str = (
            f"{i:<5} {r['name']:<26} {r['state']:<4} {r['final_score']:>6.1f} "
            f"{(r['archetype'] or '?'):<10} {(r['trajectory'] or '?'):<14} "
            f"{(r['local_scene'] or '?'):<6} {(r['pol_label'] or '?'):<8} "
            f"{(r['housing_type'] or '?'):<14}"
        )
        for pk in col_pillars:
            v = ps.get(pk)
            row_str += f" {'    —' if v is None else f'{v:>6.1f}'}"
        print(row_str)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        print(f"\nWrote {len(results)} results → {out_path}")


if __name__ == "__main__":
    main()

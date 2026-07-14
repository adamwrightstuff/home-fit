"""
Add best-fit preference labels to natural_beauty and built_environment breakdowns.

Pure computation from existing summary fields — no API calls, no GEE.

Usage:
    PYTHONPATH=. python3 scripts/catalog/patch_best_fit_labels.py \
        --input data/nyc_metro_place_catalog_scores_merged.jsonl --in-place
    PYTHONPATH=. python3 scripts/catalog/patch_best_fit_labels.py \
        --input data/la_metro_place_catalog_scores_merged.jsonl --in-place
"""

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _nb_best_fit(summary: dict) -> str:
    water_km = summary.get("water_proximity_km")
    relief = float(summary.get("terrain_relief_m") or 0)
    canopy = float(summary.get("weighted_canopy_pct") or 0)
    wtype = (summary.get("water_proximity_type") or "").lower()

    topo = min(1.0, max(0.0, (relief - 50) / 400))
    water = max(0.0, 1.0 - (water_km or 99) / 15) if water_km is not None else 0.0

    if wtype in ("coast", "ocean", "bay", "harbor", "sea"):
        ocean_s, lakes_s = water * 1.1, water * 0.4
    elif wtype == "lake":
        ocean_s, lakes_s = water * 0.3, water * 1.1
    else:  # river, stream, or unknown
        ocean_s, lakes_s = water * 0.2, water * 0.9

    canopy_s = min(1.0, max(0.0, (canopy - 15) / 65))

    scores = {
        "mountains": topo,
        "ocean": ocean_s,
        "lakes_rivers": lakes_s,
        "canopy": canopy_s,
    }
    return max(scores, key=scores.get)


_NB_LABELS = {
    "mountains": "Mountains",
    "ocean": "Ocean / Coast",
    "lakes_rivers": "Lakes & Rivers",
    "canopy": "Tree Canopy",
}

_BB_DENSITY_LABELS = {
    "Dense urban": "Dense urban",
    "Walkable suburban": "Walkable suburban",
    "Spread out": "Spread out / rural",
}

_BB_CHARACTER_LABELS = {
    "Historic": "Historic",
    "Contemporary": "Contemporary",
    "Mixed era": "Mixed era",
}


def _bb_best_fit(summary: dict) -> tuple[str, str]:
    label = (summary.get("built_form_label") or "").lower()
    year = summary.get("median_year_built")
    heritage = int(summary.get("heritage_count") or 0)

    if "urban" in label:
        density = "Dense urban"
    elif "suburban" in label:
        density = "Walkable suburban"
    else:
        density = "Spread out"

    if (year and year < 1942) or heritage >= 4:
        character = "Historic"
    elif year and year > 1990:
        character = "Contemporary"
    else:
        character = "Mixed era"

    return density, character


def patch(input_path: Path, in_place: bool, no_backup: bool) -> None:
    lines = input_path.read_text(encoding="utf-8").splitlines()
    out_lines = []
    patched = 0

    for line in lines:
        line = line.strip()
        if not line:
            out_lines.append(line)
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            out_lines.append(line)
            continue

        pillars = (obj.get("score") or {}).get("livability_pillars") or {}

        nb = pillars.get("natural_beauty") or {}
        nb_summary = nb.get("summary") or {}
        if nb_summary:
            nb_bd = nb.setdefault("breakdown", {})
            fit = _nb_best_fit(nb_summary)
            nb_bd["nb_best_fit"] = fit
            nb_bd["nb_best_fit_label"] = _NB_LABELS[fit]
            patched += 1

        bb = pillars.get("built_environment") or {}
        bb_summary = bb.get("summary") or {}
        if bb_summary:
            bb_bd = bb.setdefault("breakdown", {})
            density, character = _bb_best_fit(bb_summary)
            bb_bd["bb_best_fit_density"] = density
            bb_bd["bb_best_fit_character"] = character

        out_lines.append(json.dumps(obj, ensure_ascii=False))

    print(f"Patched {patched} places")

    if in_place:
        if not no_backup:
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            bp = input_path.with_suffix(f".jsonl.bak.{ts}")
            shutil.copy2(input_path, bp)
            print(f"Backup: {bp}")
        input_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        print(f"Updated: {input_path}")
    else:
        out = input_path.with_suffix(".best_fit.jsonl")
        out.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        print(f"Written: {out}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--in-place", action="store_true")
    p.add_argument("--no-backup", action="store_true")
    args = p.parse_args()
    path = Path(args.input)
    if not path.is_absolute():
        path = _REPO_ROOT / path
    patch(path, args.in_place, args.no_backup)


if __name__ == "__main__":
    main()

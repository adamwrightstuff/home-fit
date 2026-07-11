"""
Patch school radius bleed for Westchester places pulling Bronx schools.

Pelham Manor: same district as Pelham — copy Pelham's school data exactly.
Mount Vernon, Eastchester: filter out schools with "Bronx" in the name (borough-specific,
not the same as Bronxville which is a Westchester town name).

Run:
    python3 scripts/catalog/patch_school_radius_bleed.py
"""

import json
import math

CATALOG = "data/nyc_metro_place_catalog_scores_merged.jsonl"


def recompute_score(by_level: dict, breakdown: dict) -> float:
    all_ratings = [s["rating"] for lvl in by_level.values() for s in (lvl or []) if s.get("rating") is not None]
    if not all_ratings:
        return 0.0
    sorted_ratings = sorted(all_ratings)
    n_base = max(1, math.ceil(len(sorted_ratings) * 2 / 3))
    base_ratings = sorted_ratings[:n_base]
    top_ratings = sorted_ratings[n_base:]
    base_avg = sum(base_ratings) / len(base_ratings)
    elite_count = sum(1 for r in top_ratings if r >= 85)
    access_bonus = min(5.0, elite_count * 2.0)
    early_ed_bonus = breakdown.get("early_ed_bonus", 0.0)
    return round(min(100.0, base_avg + access_bonus + early_ed_bonus), 2)


def main():
    lines = []
    pelham_edu = None

    # First pass: grab Pelham's education data
    with open(CATALOG) as f:
        raw = f.readlines()
    for line in raw:
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        if d["catalog"].get("name") == "Pelham":
            pelham_edu = d["score"]["livability_pillars"].get("quality_education", {})
            break

    if not pelham_edu:
        print("ERROR: Pelham not found in catalog")
        return

    patched = []
    for line in raw:
        line = line.strip()
        if not line:
            lines.append(line)
            continue
        d = json.loads(line)
        name = d["catalog"].get("name", "")
        edu = d["score"]["livability_pillars"].get("quality_education", {})
        by_level = edu.get("by_level")
        changed = False

        if name == "Pelham Manor":
            # Same district as Pelham — use identical school data
            d["score"]["livability_pillars"]["quality_education"] = dict(pelham_edu)
            changed = True
            print(f"Pelham Manor: replaced with Pelham district data (score={pelham_edu.get('score')})")

        elif name in ("Mount Vernon", "Eastchester") and by_level:
            # Remove schools with "Bronx" in name (Bronx borough schools bleeding across city line)
            # Keep "Bronxville" — that's a Westchester town, different word
            new_by_level = {}
            removed = []
            for lvl, schools in by_level.items():
                kept = []
                for s in (schools or []):
                    sname = s.get("name", "")
                    # Bronx borough prefix — but NOT Bronxville (a Westchester town)
                    sl = sname.lower()
                    if ("bronx " in sl or sl.startswith("bronx ")) and "bronxville" not in sl:
                        removed.append(sname)
                    else:
                        kept.append(s)
                new_by_level[lvl] = kept

            if removed:
                breakdown = edu.get("breakdown", {})
                new_score = recompute_score(new_by_level, breakdown)
                all_ratings = [s["rating"] for lvl in new_by_level.values() for s in lvl if s.get("rating") is not None]
                sorted_r = sorted(all_ratings)
                n_base = max(1, math.ceil(len(sorted_r) * 2 / 3))
                base_avg = sum(sorted_r[:n_base]) / n_base if sorted_r else 0
                elite = sum(1 for r in sorted_r[n_base:] if r >= 85)
                new_breakdown = {
                    **breakdown,
                    "base_avg_rating": round(base_avg, 2),
                    "access_bonus": round(min(5.0, elite * 2.0), 2),
                    "total_schools_rated": len(all_ratings),
                    "elite_schools_count": elite,
                }
                d["score"]["livability_pillars"]["quality_education"] = {
                    **edu,
                    "score": new_score,
                    "by_level": new_by_level,
                    "breakdown": new_breakdown,
                }
                changed = True
                print(f"{name}: removed {removed} → score {edu.get('score')} → {new_score}")

        lines.append(json.dumps(d, separators=(",", ":")))
        if changed:
            patched.append(name)

    with open(CATALOG, "w") as f:
        f.write("\n".join(lines))
        if lines and lines[-1]:
            f.write("\n")

    print(f"\nDone. Patched: {patched}")


if __name__ == "__main__":
    main()

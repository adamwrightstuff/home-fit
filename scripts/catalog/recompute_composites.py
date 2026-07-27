"""
Recompute catalog composites after two batched changes:

  1. River waterfront backfill — AO scores already updated in the JSONL.
     This script recomputes longevity_index (uses AO score) and total_score
     (uses AO contribution) to reflect those changes.

  2. NB weight migration — moves the composite weight from the blended
     neighborhood_beauty pillar to natural_beauty directly (same weight, same
     total allocation). The catalog was scored when neighborhood_beauty carried
     the full weight; the live system now uses natural_beauty as a primary pillar.

No live API calls. All computations derive from stored pillar scores.
Status_signal is preserved from storage (census-tract baseline needed for
correct z-scores is not available offline).
"""

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # repo root
from pillars.composite_indices import compute_longevity_index

CATALOGS = [
    Path("data/nyc_metro_place_catalog_scores_merged.jsonl"),
    Path("data/la_metro_place_catalog_scores_merged.jsonl"),
]

# Longevity pillar weights (from composite_indices.py LONGEVITY_INDEX_WEIGHTS)
LONGEVITY_WEIGHTS = {
    "active_outdoors": 22.0,
    "natural_beauty": 5.0,
    "neighborhood_amenities": 7.0,
    "healthcare_access": 16.0,
    "climate_risk": 10.0,
    "community_safety": 15.0,
    "social_fabric": 25.0,
}


def migrate_nb_weight(p: dict) -> tuple[float, float]:
    """
    Move weight from neighborhood_beauty to natural_beauty.
    Returns (delta_contribution, new_nat_weight).
    """
    lp = p["score"]["livability_pillars"]
    ts = p["score"].get("total_score_breakdown") or {}
    ta = p["score"].get("token_allocation") or {}

    nb = lp.get("neighborhood_beauty") or {}
    nat = lp.get("natural_beauty") or {}

    nb_weight = nb.get("weight")
    nb_contrib = nb.get("contribution")

    if not isinstance(nb_weight, (int, float)) or nb_weight == 0:
        return 0.0, 0.0  # nothing to migrate

    nat_score = nat.get("score")
    if not isinstance(nat_score, (int, float)):
        return 0.0, 0.0

    new_nat_contrib = round(nat_score * nb_weight / 100.0, 4)
    delta = new_nat_contrib - (nb_contrib or 0.0)

    # Update LP neighborhood_beauty
    nb["weight"] = None
    nb["contribution"] = None
    # Update LP natural_beauty
    nat["weight"] = nb_weight
    nat["contribution"] = new_nat_contrib

    # Update TS entries
    ts_nb = ts.get("neighborhood_beauty") or {}
    ts_nat = ts.get("natural_beauty") or {}
    if isinstance(ts_nb, dict):
        ts_nb["weight"] = None
        ts_nb["contribution"] = None
    if isinstance(ts_nat, dict):
        ts_nat["weight"] = nb_weight
        ts_nat["contribution"] = new_nat_contrib

    # Update token_allocation (move neighborhood_beauty → natural_beauty)
    if "neighborhood_beauty" in ta:
        ta["natural_beauty"] = ta.pop("neighborhood_beauty")

    return delta, nb_weight


def recompute_longevity(p: dict) -> float | None:
    """Recompute longevity_index from stored pillar scores + updated token_allocation."""
    lp = p["score"]["livability_pillars"]
    ta = p["score"].get("token_allocation")

    li, contrib = compute_longevity_index(lp, token_allocation=ta, only_pillars=None)
    if li is None:
        return None

    p["score"]["longevity_index"] = round(li, 2)
    p["score"]["longevity_index_contributions"] = contrib
    p["score"]["longevity_index_breakdown"] = dict(contrib)
    return round(li, 2)


def process_place(p: dict) -> str | None:
    """Apply weight migration + recompute composites. Returns change summary or None."""
    name = p.get("catalog", {}).get("name", "?")

    old_total = p["score"].get("total_score") or 0.0
    old_li = p["score"].get("longevity_index")

    # 1. Migrate NB weight → natural_beauty
    delta_nb, nb_weight = migrate_nb_weight(p)

    # 2. Propagate AO delta (already applied to pillar score; now reflect in contribution)
    #    Only needed for places where contribution is stored and we can compute it correctly.
    #    The river backfill already updated AO score + LP contribution + total_score; here
    #    we just make sure total_score is consistent after the NB migration.
    if delta_nb != 0.0:
        p["score"]["total_score"] = round(old_total + delta_nb, 4)

    # 3. Recompute longevity_index
    new_li = recompute_longevity(p)

    # Build summary
    parts = []
    if abs(delta_nb) > 0.001:
        parts.append(f"NB weight migrated ({nb_weight:.3f}) Δtotal={delta_nb:+.3f}")
    if new_li is not None and old_li is not None and abs(new_li - old_li) > 0.01:
        parts.append(f"longevity {old_li}→{new_li}")
    if new_li is not None and old_li is None:
        parts.append(f"longevity now {new_li}")

    return "; ".join(parts) if parts else None


def process_catalog(path: Path) -> int:
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    changed = 0
    changes = []
    for p in rows:
        summary = process_place(p)
        if summary:
            changed += 1
            changes.append((p.get("catalog", {}).get("name", "?"), summary))

    print(f"\n{'='*60}")
    print(f"  {path.name}  ({len(rows)} places, {changed} changed)")
    print(f"{'='*60}")
    for name, summary in changes[:30]:
        print(f"  {name}: {summary}")
    if len(changes) > 30:
        print(f"  ... and {len(changes)-30} more")

    if changed:
        backup = path.with_suffix(".jsonl.composites.bak")
        shutil.copy2(path, backup)
        print(f"\n  Backup → {backup.name}")
        with open(path, "w") as f:
            for row in rows:
                f.write(json.dumps(row, separators=(",", ":")) + "\n")
        print(f"  Wrote {path.name}")

    return changed


if __name__ == "__main__":
    import os
    os.chdir(Path(__file__).parent.parent.parent)

    total = 0
    for cat in CATALOGS:
        total += process_catalog(cat)
    print(f"\nTotal places updated: {total}")

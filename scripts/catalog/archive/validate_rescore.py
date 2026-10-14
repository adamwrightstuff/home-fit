"""
Post-rescore health check: compare every pillar score + confidence for rescored
places against the most recent backup, and block commit if regressions are found.

Usage:
    python3 scripts/catalog/validate_rescore.py --jsonl data/nyc_metro_place_catalog_scores_merged.jsonl
    python3 scripts/catalog/validate_rescore.py --jsonl data/nyc_metro_place_catalog_scores_merged.jsonl --backup data/nyc_metro_place_catalog_scores_merged.jsonl.bak.20260828-123811

Exit codes:
    0 = all clear
    1 = blocking regressions found (do not commit)
    2 = warnings only (commit with caution)
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]

PILLARS = [
    "active_outdoors", "neighborhood_amenities", "natural_beauty",
    "healthcare_access", "public_transit_access", "air_travel_access",
    "quality_education", "housing_value", "economic_opportunity",
    "climate_risk", "social_fabric", "diversity", "community_safety",
]

# built_environment is not scored in residential catalog mode — always null, never check it.

# A confidence crash: was >= this, now 0.
CONF_CRASH_THRESHOLD = 50
# A score zero-out: was >= this, now 0 or None.
ZERO_OUT_THRESHOLD = 5
# A score regression large enough to block.
SCORE_REGRESSION_BLOCK = 20
# A score regression worth warning about.
SCORE_REGRESSION_WARN = 10
# A suspicious score jump (sanity check for corrupt merges).
SCORE_JUMP_WARN = 40
# Max distance (meters) between catalog pin and scored pin before warning.
PIN_WARN_METERS = 300


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load_jsonl(path: Path) -> Dict[str, Any]:
    """Load a catalog JSONL; last record per place name wins."""
    records: Dict[str, Any] = {}
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            name = d.get("catalog", {}).get("name")
            if name:
                records[name] = d
    return records


def pillar_score(record: Dict, key: str) -> Optional[float]:
    p = (record.get("score", {}).get("livability_pillars") or {}).get(key)
    return (p or {}).get("score") if p else None


def pillar_conf(record: Dict, key: str) -> Optional[float]:
    p = (record.get("score", {}).get("livability_pillars") or {}).get(key)
    dq = (p or {}).get("data_quality") or {}
    return dq.get("confidence") if p else None


def find_latest_backup(jsonl_path: Path) -> Optional[Path]:
    pattern = str(jsonl_path) + ".bak.*"
    candidates = sorted(glob.glob(pattern))
    return Path(candidates[-1]) if candidates else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", type=Path, required=True, help="Current catalog JSONL to validate.")
    ap.add_argument("--backup", type=Path, default=None, help="Backup to compare against. Auto-detects latest if omitted.")
    ap.add_argument("--pin-check", action="store_true", help="Also verify scored pin is within PIN_WARN_METERS of catalog lat/lon.")
    args = ap.parse_args()

    jsonl_path = args.jsonl if args.jsonl.is_absolute() else REPO_ROOT / args.jsonl
    backup_path = args.backup
    if backup_path is None:
        backup_path = find_latest_backup(jsonl_path)
    if backup_path is None:
        print("ERROR: no backup found. Cannot validate without a baseline.")
        return 1

    print(f"Comparing:\n  current: {jsonl_path}\n  backup:  {backup_path}\n")

    current = load_jsonl(jsonl_path)
    backup = load_jsonl(backup_path)

    # Detect which places actually changed (any pillar score differs).
    changed = []
    for name, rec in current.items():
        old = backup.get(name)
        if old is None:
            continue
        for key in PILLARS:
            ns, os_ = pillar_score(rec, key), pillar_score(old, key)
            if ns != os_:
                changed.append(name)
                break

    if not changed:
        print("No changes detected between current and backup. Nothing to validate.")
        return 0

    print(f"Rescored places detected: {len(changed)}")
    print(", ".join(sorted(changed)))
    print()

    blocks: list[str] = []
    warnings: list[str] = []

    for name in sorted(changed):
        rec = current[name]
        old = backup.get(name, {})
        place_issues: list[Tuple[str, str, str]] = []  # (severity, pillar, message)

        for key in PILLARS:
            ns = pillar_score(rec, key)
            os_ = pillar_score(old, key)
            nc = pillar_conf(rec, key)
            oc = pillar_conf(old, key)

            # Confidence crash: was high, now 0.
            if oc is not None and oc >= CONF_CRASH_THRESHOLD and nc is not None and nc == 0:
                ns_str = f"{ns:.1f}" if ns is not None else "None"
                place_issues.append(("BLOCK", key, f"confidence crash {oc:.0f}→0 (score {os_:.1f}→{ns_str})"))

            # Score zero-out: had a real score, now 0 or None.
            if os_ is not None and os_ >= ZERO_OUT_THRESHOLD and (ns is None or ns == 0):
                place_issues.append(("BLOCK", key, f"score zeroed out {os_:.1f}→{ns}"))

            # Large regression — WARN only; a pin move legitimately shifts geographic pillars.
            # Only zero-outs and confidence crashes are hard blocks.
            if os_ is not None and ns is not None:
                delta = ns - os_
                if delta <= -SCORE_REGRESSION_WARN:
                    place_issues.append(("WARN", key, f"score dropped {os_:.1f}→{ns:.1f} (Δ{delta:+.1f}) — verify vs pin move"))

            # Suspicious jump (possible corrupt merge like Southport→100).
            if os_ is not None and ns is not None and (ns - os_) >= SCORE_JUMP_WARN:
                place_issues.append(("WARN", key, f"score jumped {os_:.1f}→{ns:.1f} (Δ{ns-os_:+.1f}) — verify not corrupt"))

        # Pin accuracy check.
        if args.pin_check:
            cat = rec.get("catalog", {})
            coords = rec.get("score", {}).get("coordinates", {})
            clat, clon = cat.get("lat"), cat.get("lon")
            slat, slon = coords.get("lat"), coords.get("lon")
            if all(x is not None for x in (clat, clon, slat, slon)):
                dist = haversine(float(clat), float(clon), float(slat), float(slon))
                if dist > PIN_WARN_METERS:
                    place_issues.append(("WARN", "pin", f"scored pin {dist:.0f}m from catalog lat/lon"))

        if place_issues:
            print(f"{'='*60}")
            print(f"  {name}")
            print(f"{'='*60}")
            for severity, pillar, msg in place_issues:
                tag = "🚫 BLOCK" if severity == "BLOCK" else "⚠️  WARN "
                print(f"  {tag}  {pillar:<25} {msg}")
                if severity == "BLOCK":
                    blocks.append(f"{name} / {pillar}: {msg}")
                else:
                    warnings.append(f"{name} / {pillar}: {msg}")
            print()

    print("=" * 60)
    if not blocks and not warnings:
        print("✅ All clear — no regressions detected.")
        return 0

    if warnings and not blocks:
        print(f"⚠️  {len(warnings)} warning(s), 0 blockers. Review before committing.")
        return 2

    print(f"🚫 {len(blocks)} blocking regression(s), {len(warnings)} warning(s).")
    print()
    print("DO NOT COMMIT. Restore affected pillars from backup and re-run:")
    print(f"  Backup: {backup_path}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

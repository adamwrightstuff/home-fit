#!/usr/bin/env python3
"""
Audit catalog places for stale confidence/data_warning fields -- cases where a place's
stored data_quality no longer matches what current scoring code would compute from its
own already-stored raw inputs. Catches the "scored under old logic, never refreshed"
class of bug (e.g. Hamilton Heights: osm_building_coverage=0 but data_warning=None
because it predated the coverage-threshold check).

Two tiers:
  1. Generic hard-failure floor check (all 13 pillars): if data_quality.data_warning(s)
     contains a known hard-failure marker, confidence must be floored to <=10. Catches
     drift like the healthcare_access query_failed bug (eab6652).
  2. Pillar-specific checks (registry below): built_environment's coverage-threshold
     consistency (osm_building_coverage vs data_warning/confidence_0_1).

Report-only -- does not modify the catalog. Add new pillar-specific checks to
PILLAR_SPECIFIC_CHECKS as new bug classes are found; don't assume this registry is
exhaustive.

Usage:
  PYTHONPATH=. python3 scripts/catalog/audit_pillar_confidence_staleness.py \\
    --input data/nyc_metro_place_catalog_scores_merged.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PILLAR_ORDER: List[str] = [
    "quality_education", "neighborhood_amenities", "economic_security", "climate_risk",
    "active_outdoors", "neighborhood_beauty", "diversity", "social_fabric",
    "healthcare_access", "public_transit_access", "air_travel_access", "housing_value",
    "community_safety",
]

HARD_FAILURE_MARKERS = frozenset({"api_error", "timeout", "query_failed"})
HARD_FAILURE_CONFIDENCE_CEILING = 10


def _warning_strings(dq: Dict[str, Any]) -> List[str]:
    out = []
    w = dq.get("data_warning")
    if isinstance(w, str):
        out.append(w)
    ws = dq.get("data_warnings")
    if isinstance(ws, list):
        out.extend(x for x in ws if isinstance(x, str))
    return out


def generic_floor_check(pillar_name: str, pillar: Dict[str, Any]) -> Optional[str]:
    """Tier 1: any pillar, any hard-failure marker -> confidence must be floored."""
    dq = pillar.get("data_quality")
    if not isinstance(dq, dict):
        return None
    warnings = _warning_strings(dq)
    if not any(w in HARD_FAILURE_MARKERS for w in warnings):
        return None
    conf = dq.get("confidence")
    if isinstance(conf, (int, float)) and conf > HARD_FAILURE_CONFIDENCE_CEILING:
        return (f"hard-failure marker {[w for w in warnings if w in HARD_FAILURE_MARKERS]} "
                f"present but confidence={conf} (should be <={HARD_FAILURE_CONFIDENCE_CEILING})")
    return None


def built_environment_coverage_check(pillar_name: str, pillar: Dict[str, Any]) -> Optional[str]:
    """Tier 2: neighborhood_beauty's nested built_environment coverage vs data_warning consistency."""
    if pillar_name != "neighborhood_beauty":
        return None
    aa = ((pillar.get("details") or {}).get("built_environment") or {}).get("architectural_analysis")
    if not isinstance(aa, dict):
        return None
    cov = aa.get("osm_building_coverage")
    if cov is None:
        cov = (aa.get("metrics") or {}).get("built_coverage_ratio")
    if cov is None:
        return None
    warning = aa.get("data_warning")
    expected_warning = "low_building_coverage" if cov < 0.50 else None
    if expected_warning == "low_building_coverage" and warning != "low_building_coverage":
        return f"osm_building_coverage={cov:.3f} (<0.50) but data_warning={warning!r} (stale -- predates threshold check)"
    return None


# Registry of pillar-specific checks. Each fn: (pillar_name, pillar_dict) -> Optional[issue_str]
PILLAR_SPECIFIC_CHECKS = [
    built_environment_coverage_check,
]


def audit_file(path: Path) -> List[Dict[str, Any]]:
    findings = []
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        name = (rec.get("catalog") or {}).get("name", "?")
        lp = (rec.get("score") or {}).get("livability_pillars") or {}
        for pillar_name in PILLAR_ORDER:
            pillar = lp.get(pillar_name)
            if not isinstance(pillar, dict):
                continue
            issue = generic_floor_check(pillar_name, pillar)
            if issue:
                findings.append({"place": name, "pillar": pillar_name, "tier": "generic_floor", "issue": issue})
            for check_fn in PILLAR_SPECIFIC_CHECKS:
                issue = check_fn(pillar_name, pillar)
                if issue:
                    findings.append({"place": name, "pillar": pillar_name, "tier": check_fn.__name__, "issue": issue})
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    args = ap.parse_args()

    findings = audit_file(args.input)
    print(f"=== {args.input.name}: {len(findings)} stale-confidence findings ===")
    by_tier: Dict[str, int] = {}
    for f in findings:
        by_tier[f["tier"]] = by_tier.get(f["tier"], 0) + 1
    for tier, count in sorted(by_tier.items(), key=lambda x: -x[1]):
        print(f"  {tier}: {count}")
    print()
    for f in findings[:200]:
        print(f"  [{f['tier']}] {f['place']:28s} {f['pillar']:24s} {f['issue']}")
    if len(findings) > 200:
        print(f"  ... {len(findings) - 200} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())

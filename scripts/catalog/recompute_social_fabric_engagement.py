#!/usr/bin/env python3
"""
Offline Social Fabric engagement recompute (no pillar APIs).

Uses stored breakdown.stability / civic_gathering and recomputes breakdown.engagement from
stored orgs_per_1k, voter_turnout_rate, turnout_source, ZIP, and area_type — matching
``community_participation.compute_participation_score`` (state turnout is diagnostic only
and is omitted from the blend).

BMF z uses area-type baselines only (``irs_bmf.engagement_100_from_orgs_area_type``), mirroring
the live pillar after the area-type-first BMF calibration.

Safety: by default rows are only patched when recomputed engagement matches the stored value
within ``--verify-tol``. Use ``--patch-state-turnout`` with ``--apply`` to rewrite rows whose
``turnout_source`` is ``state_turnout`` and the engagement delta exceeds the tolerance.

Default is dry-run (no write). Pass ``--apply --output PATH`` to write.

If engagement changes, recompute composites:

  PYTHONPATH=. python3 scripts/catalog/recompute_catalog_composites.py --in-place \\
    --input <your.jsonl>

Note: catalogs built while IRS BMF used division/area-type **hybrid** means/std will fail
offline verify against area-type-only math (common on older LA merges); those rows need a
fresh Social Fabric pillar rescore, not this script, unless tolerances are relaxed for a
one-off migration.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TOL_DEFAULT = 0.2


@dataclass
class RowEngagementResult:
    status: str
    old_engagement: Optional[float]
    new_engagement: Optional[float]
    mix: str = ""
    vol_resolution: Optional[str] = None
    detail: str = ""


@dataclass
class DryRunStats:
    total_rows: int = 0
    sf_success: int = 0
    patch_ok: int = 0
    would_change_state_turnout: int = 0
    skip_no_sf: int = 0
    skip_missing_subscores: int = 0
    skip_no_engagement_inputs: int = 0
    skip_bmf_verify_fail: int = 0
    skip_verify_mismatch: int = 0
    examples_mismatch: List[str] = field(default_factory=list)


def _recompute_total(pillars: dict) -> float:
    total = weighted = 0.0
    for p in pillars.values():
        if not isinstance(p, dict):
            continue
        score = p.get("score")
        w = p.get("weight")
        if score is not None and w is not None:
            weighted += float(score) * float(w)
            total += float(w)
    return round(weighted / total, 4) if total > 0 else 0.0


def _blend_engagement(
    bmf_slot: Optional[float],
    z_vol: Optional[float],
    z_turn: Optional[float],
) -> Tuple[Optional[float], str]:
    if bmf_slot is not None and z_vol is not None and z_turn is not None:
        return 0.40 * bmf_slot + 0.40 * z_vol + 0.20 * z_turn, "full"
    if z_vol is None and bmf_slot is not None and z_turn is not None:
        return 0.60 * bmf_slot + 0.40 * z_turn, "no_vol_60_40_bmf_turn"
    if z_turn is None and bmf_slot is not None and z_vol is not None:
        return 0.60 * bmf_slot + 0.40 * z_vol, "no_turn_60_40_bmf_vol"
    if bmf_slot is not None and z_vol is not None:
        return 0.60 * bmf_slot + 0.40 * z_vol, "bmf_vol_only"
    if bmf_slot is not None and z_turn is not None:
        return 0.60 * bmf_slot + 0.40 * z_turn, "bmf_turn_only"
    if bmf_slot is None and z_vol is not None and z_turn is not None:
        return 0.50 * z_vol + 0.50 * z_turn, "vol_turn_no_bmf"
    if bmf_slot is not None:
        return bmf_slot, "bmf_only"
    if z_vol is not None:
        return z_vol, "vol_only"
    if z_turn is not None:
        return z_turn, "turn_only"
    return None, "none"


def _turnout_z_offline(
    turnout_rate: Optional[float],
    turnout_source: Optional[str],
    area_type: Optional[str],
) -> Optional[float]:
    from data_sources.community_participation import _rate_to_z_score

    if turnout_rate is None:
        return None
    tsrc = (turnout_source or "").strip().lower()
    if tsrc == "state_turnout":
        return None
    if tsrc == "precinct":
        return _rate_to_z_score(float(turnout_rate), 0.45, 0.12)
    if tsrc == "tract_turnout":
        from data_sources import voter_turnout

        pack = voter_turnout.turnout_score_from_known_rate(float(turnout_rate), area_type)
        if pack is None:
            return None
        return pack[0]
    return None


def _tract_stub_for_volunteering(row: dict) -> Optional[dict]:
    """CPS volunteering fallback needs state_fips when ZIP is missing from location_info."""
    from data_sources.irs_bmf import STATE_FIPS_TO_ABBREV_IRS

    abbrev = (row.get("catalog") or {}).get("state_abbr")
    if not abbrev:
        return None
    abbrev = str(abbrev).strip().upper()
    for fips, ab in STATE_FIPS_TO_ABBREV_IRS.items():
        if ab == abbrev:
            return {"state_fips": fips}
    return None


def audit_row_engagement(row: dict, tol: float) -> RowEngagementResult:
    from data_sources import irs_bmf
    from data_sources.community_participation import get_volunteering_score

    score_doc = row.get("score", {})
    pillars = score_doc.get("livability_pillars", {})
    sf = pillars.get("social_fabric")
    if not sf or sf.get("status") != "success":
        return RowEngagementResult("skip_no_sf", None, None, detail="no social_fabric or not success")

    summary = sf.get("summary", {}) or {}
    breakdown = sf.get("breakdown", {}) or {}
    old_eng = breakdown.get("engagement")
    if old_eng is None:
        return RowEngagementResult("skip_missing_subscores", None, None, detail="missing engagement")

    stability = breakdown.get("stability")
    civic = breakdown.get("civic_gathering")
    if stability is None or civic is None:
        return RowEngagementResult("skip_missing_subscores", None, None, detail="missing stability or civic")

    orgs_per_1k = summary.get("orgs_per_1k")
    turnout_rate = summary.get("voter_turnout_rate")
    turnout_source = summary.get("turnout_source")
    area_type = (sf.get("area_classification") or {}).get("area_type")
    zip_code = (score_doc.get("location_info") or {}).get("zip")

    z_turn = _turnout_z_offline(
        float(turnout_rate) if turnout_rate is not None else None,
        str(turnout_source) if turnout_source is not None else None,
        str(area_type) if area_type is not None else None,
    )

    vol = get_volunteering_score(zip_code, _tract_stub_for_volunteering(row))
    z_vol = vol[0] if vol else None
    vol_resolution = vol[1] if vol else None

    z_ref = (
        irs_bmf.engagement_100_from_orgs_area_type(float(orgs_per_1k), area_type, use_legacy=False)
        if orgs_per_1k is not None
        else None
    )
    z_leg = (
        irs_bmf.engagement_100_from_orgs_area_type(float(orgs_per_1k), area_type, use_legacy=True)
        if orgs_per_1k is not None
        else None
    )
    bmf_slot = z_ref if z_ref is not None else z_leg

    engagement, mix = _blend_engagement(bmf_slot, z_vol, z_turn)
    if engagement is None:
        return RowEngagementResult(
            "skip_no_engagement_inputs", float(old_eng), None, mix=mix, detail="no blend inputs"
        )

    engagement = max(0.0, min(100.0, float(engagement)))
    old_f = float(old_eng)

    if bmf_slot is None and orgs_per_1k is not None:
        return RowEngagementResult(
            "skip_bmf_verify_fail",
            old_f,
            engagement,
            mix=mix,
            vol_resolution=vol_resolution,
            detail="orgs present but no area-type bmf stats",
        )

    tsrc = (turnout_source or "").strip().lower()
    if tsrc == "state_turnout" and abs(engagement - old_f) > tol:
        return RowEngagementResult(
            "would_change_state_turnout",
            old_f,
            engagement,
            mix=mix,
            vol_resolution=vol_resolution,
            detail="state turnout excluded from blend; engagement should drop",
        )

    if abs(engagement - old_f) <= tol:
        return RowEngagementResult(
            "patch_ok",
            old_f,
            engagement,
            mix=mix,
            vol_resolution=vol_resolution,
            detail="verify ok",
        )

    hint = row.get("catalog", {}).get("search_query") or row.get("catalog", {}).get("name")
    return RowEngagementResult(
        "skip_verify_mismatch",
        old_f,
        engagement,
        mix=mix,
        vol_resolution=vol_resolution,
        detail=f"mix={mix} delta={engagement - old_f:.3f} row={hint!r}",
    )


def apply_engagement_patch(row: dict, res: RowEngagementResult, tol: float) -> str:
    """
    Apply updates to ``row``. Returns ``metadata`` if only summary fields changed, else ``full``.
    """
    from data_sources import irs_bmf
    from data_sources.community_participation import get_volunteering_score

    if res.new_engagement is None:
        return "none"

    score_doc = row["score"]
    pillars = score_doc["livability_pillars"]
    sf = pillars["social_fabric"]
    summary = sf.setdefault("summary", {})
    breakdown = sf.setdefault("breakdown", {})

    area_type = (sf.get("area_classification") or {}).get("area_type")
    zip_code = (score_doc.get("location_info") or {}).get("zip")
    vol = get_volunteering_score(zip_code, _tract_stub_for_volunteering(row))
    vol_resolution = vol[1] if vol else res.vol_resolution

    orgs_per_1k = summary.get("orgs_per_1k")
    z_ref = (
        irs_bmf.engagement_100_from_orgs_area_type(float(orgs_per_1k), area_type, use_legacy=False)
        if orgs_per_1k is not None
        else None
    )
    z_leg = (
        irs_bmf.engagement_100_from_orgs_area_type(float(orgs_per_1k), area_type, use_legacy=True)
        if orgs_per_1k is not None
        else None
    )
    bmf_slot = z_ref if z_ref is not None else z_leg
    z_turn = _turnout_z_offline(
        float(summary["voter_turnout_rate"]) if summary.get("voter_turnout_rate") is not None else None,
        str(summary.get("turnout_source") or ""),
        str(area_type) if area_type is not None else None,
    )
    _, mix = _blend_engagement(bmf_slot, vol[0] if vol else None, z_turn)
    if mix == "none":
        mix = res.mix

    tsrc = (summary.get("turnout_source") or "").strip().lower()
    summary["turnout_in_engagement_blend"] = tsrc in ("precinct", "tract_turnout") and z_turn is not None
    summary["participation_mix"] = mix
    if vol_resolution:
        summary["volunteering_resolution"] = vol_resolution

    old_eng = float(breakdown["engagement"])
    if abs(float(res.new_engagement) - old_eng) <= tol:
        return "metadata"

    breakdown["engagement"] = round(float(res.new_engagement), 10)

    stability = float(breakdown["stability"])
    civic = float(breakdown["civic_gathering"])
    raw = 1.2 * stability + 1.2 * civic + 1.2 * float(res.new_engagement)
    sf["score"] = round(max(0.0, min(100.0, raw / 3.6)), 1)
    score_doc["total_score"] = _recompute_total(pillars)
    return "full"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=None, help="Required when --apply")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write output (default: dry-run only)",
    )
    parser.add_argument(
        "--patch-state-turnout",
        action="store_true",
        help="With --apply, also patch rows where state turnout changes engagement",
    )
    parser.add_argument(
        "--verify-tol",
        type=float,
        default=TOL_DEFAULT,
        help="Max abs delta vs stored engagement for verify-only patch (default 0.2)",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        default=None,
        help="Write dry-run counters + school hints to this JSON file",
    )
    parser.add_argument(
        "--max-mismatch-examples",
        type=int,
        default=30,
        help="Cap mismatch examples listed in stdout / report",
    )
    args = parser.parse_args()
    tol: float = float(args.verify_tol)

    if args.apply and not args.output:
        print("ERROR: --apply requires --output", file=sys.stderr)
        return 2

    rows: List[dict] = [json.loads(l) for l in args.input.read_text().splitlines() if l.strip()]
    st = DryRunStats(total_rows=len(rows))
    api_school_hints: List[str] = []

    for row in rows:
        sf = row.get("score", {}).get("livability_pillars", {}).get("social_fabric") or {}
        st.sf_success += int(sf.get("status") == "success")

    patched_meta = patched_full = 0
    for row in rows:
        cat = row.get("catalog") or {}
        name = cat.get("name", "")
        edu = (row.get("score", {}) or {}).get("livability_pillars", {}).get("quality_education") or {}
        if edu.get("status") == "fallback" and (edu.get("score") == 0 or edu.get("score") == 0.0):
            q = cat.get("search_query") or name
            api_school_hints.append(f"education fallback score=0: {q!r}")

        res = audit_row_engagement(row, tol)

        if res.status == "skip_no_sf":
            st.skip_no_sf += 1
        elif res.status == "skip_missing_subscores":
            st.skip_missing_subscores += 1
        elif res.status == "skip_no_engagement_inputs":
            st.skip_no_engagement_inputs += 1
        elif res.status == "skip_bmf_verify_fail":
            st.skip_bmf_verify_fail += 1
        elif res.status == "would_change_state_turnout":
            st.would_change_state_turnout += 1
            if args.apply and args.patch_state_turnout:
                kind = apply_engagement_patch(row, res, tol)
                if kind == "metadata":
                    patched_meta += 1
                elif kind == "full":
                    patched_full += 1
        elif res.status == "skip_verify_mismatch":
            st.skip_verify_mismatch += 1
            if len(st.examples_mismatch) < args.max_mismatch_examples:
                st.examples_mismatch.append(res.detail)
        elif res.status == "patch_ok":
            st.patch_ok += 1
            if args.apply:
                kind = apply_engagement_patch(row, res, tol)
                if kind == "metadata":
                    patched_meta += 1
                elif kind == "full":
                    patched_full += 1
        else:
            st.skip_verify_mismatch += 1

    print("=== Social Fabric engagement offline dry-run ===")
    out_stats = {
        **st.__dict__,
        "rows_metadata_only": patched_meta if args.apply else 0,
        "rows_full_engagement_rescore": patched_full if args.apply else 0,
    }
    print(json.dumps(out_stats, indent=2))
    if st.examples_mismatch:
        print("\nFirst mismatch examples:")
        for x in st.examples_mismatch[:15]:
            print(" ", x)

    if args.apply and args.output:
        args.output.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        print(f"\nWrote {args.output}")
    else:
        print("\nDry-run only (no write). Pass --apply --output PATH to write.")

    if args.report_json:
        payload = {
            "stats": out_stats,
            "school_api_rescore_hints": sorted(set(api_school_hints)),
            "note": "School hints: confirm quality_education before SchoolDigger API.",
        }
        args.report_json.write_text(json.dumps(payload, indent=2))
        print(f"Report written to {args.report_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

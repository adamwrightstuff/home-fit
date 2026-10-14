#!/usr/bin/env python3
"""
Generate a one-time, non-personalized description per catalog place with Claude and store it in
score.place_description (plus score.place_description_meta with an input hash).

The description is written only from fields already stored on the row, so no live scoring is needed.
Each description carries a hash of its inputs; re-running skips rows whose hash still matches, and
--check lists rows whose stored data has changed since the text was written.

The existing rule-based score.place_summary is left untouched.

Pilot first (writes to a separate file, calls the API for 5 places):
  PYTHONPATH=. python3 scripts/catalog/generate_place_descriptions.py \\
    --input data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl \\
    --output /tmp/nyc_descriptions_pilot.jsonl --names "Borough Park,Williamsburg,Bronxville" --limit 5

No API calls (prints the assembled inputs and prompt):
  ... --dry-run

Stale check (no API calls):
  ... --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPT_VERSION = "v1"
TOP_CODED_HOME_VALUE = 2_000_000
KM_PER_MILE = 1.609344

PILLAR_LABELS = {
    "active_outdoors": "outdoor recreation access",
    "natural_beauty": "natural scenery",
    "neighborhood_amenities": "walkable daily amenities",
    "air_travel_access": "airport access",
    "public_transit_access": "public transit",
    "healthcare_access": "healthcare access",
    "quality_education": "schools",
    "housing_value": "housing affordability and space",
    "climate_risk": "climate and flood resilience (higher is safer)",
    "social_fabric": "community cohesion",
    "diversity": "demographic diversity",
    "community_safety": "safety (higher is safer)",
    "economic_opportunity": "reachable job market",
}


def _num(v: Any) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def build_inputs(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    cat = row.get("catalog") or {}
    score = row.get("score") or {}
    lp = score.get("livability_pillars") or {}
    if not cat.get("name") or not lp:
        return None

    pillars: Dict[str, Dict[str, Any]] = {}
    for key, label in PILLAR_LABELS.items():
        p = lp.get(key)
        if not isinstance(p, dict) or p.get("status") in ("failed", "no_data"):
            continue
        s = _num(p.get("score"))
        if s is None:
            continue
        conf = _num(p.get("confidence"))
        entry: Dict[str, Any] = {"label": label, "score": round(s)}
        if conf is not None and conf < 50:
            entry["limited_data"] = True
        pillars[key] = entry

    hv = (lp.get("housing_value") or {}).get("summary") or {}
    housing: Dict[str, Any] = {}
    mhv = _num(hv.get("median_home_value"))
    if mhv is not None:
        housing["median_home_value"] = (
            f"above ${TOP_CODED_HOME_VALUE:,} (Census top code)" if mhv >= TOP_CODED_HOME_VALUE else f"${int(round(mhv, -3)):,}"
        )
    for k in ("renter_pct", "median_gross_rent"):
        v = _num(hv.get(k))
        if v is not None:
            housing[k] = round(v, 2) if k == "renter_pct" else int(v)
    low = _num((score.get("housing_stock") or {}).get("pct_low_density"))
    if low is not None:
        housing["share_of_units_in_1_to_4_unit_buildings"] = round(low, 2)

    facts: Dict[str, Any] = {}
    cbd = _num(row.get("cbd_transit_minutes"))
    if cbd is not None:
        facts["transit_minutes_to_metro_center"] = round(cbd)
    ata = (lp.get("air_travel_access") or {}).get("summary") or {}
    km = _num(ata.get("nearest_airport_km"))
    if km is not None:
        facts["nearest_major_airport_miles"] = round(km / KM_PER_MILE)
    if score.get("local_scene_bucket"):
        facts["independent_local_scene"] = score["local_scene_bucket"]
    area_type = ((score.get("data_quality_summary") or {}).get("area_classification") or {}).get("area_type")
    if area_type:
        facts["area_type"] = area_type

    return {
        "place": cat["name"],
        "state": cat.get("state_full") or cat.get("state_abbr"),
        "pillar_scores_0_to_100": pillars,
        "housing": housing,
        "other_facts": facts,
    }


def input_hash(inputs: Dict[str, Any], model: str) -> str:
    blob = json.dumps({"v": PROMPT_VERSION, "model": model, "inputs": inputs}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def build_prompt(inputs: Dict[str, Any]) -> str:
    return f"""You write short neighborhood descriptions for HomeFit, a livability scoring product.

Describe this place using ONLY the data below. Rules:
- 3 to 4 sentences, plain and neutral. Do not address the reader or tailor it to any person's priorities.
- Lead with what is genuinely strongest about the place, then be honest about the main trade-offs.
- Use only the facts and scores provided. Do not name restaurants, parks, landmarks, streets, schools or employers, and do not assert anything the data does not show.
- Scores are 0 to 100 within HomeFit's own scale. Say "strong", "solid", "modest" or "weak" rather than quoting raw scores. Pillars flagged limited_data should be hedged or left out.
- Do not compare this place to other places or mention rankings.
- Quote dollar amounts and distances exactly as given (distances are in miles). Never use em dashes.

DATA:
{json.dumps(inputs, indent=2, ensure_ascii=False)}

Return only the description text."""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, default=None, help="Output JSONL path")
    ap.add_argument("--in-place", action="store_true", help="Write back to --input")
    ap.add_argument("--names", type=str, default=None, help="Comma-separated catalog names to process")
    ap.add_argument("--limit", type=int, default=0, help="Process at most this many rows")
    ap.add_argument("--model", default=None)
    ap.add_argument("--delay", type=float, default=0.3)
    ap.add_argument("--force", action="store_true", help="Regenerate even if the stored hash matches")
    ap.add_argument("--dry-run", action="store_true", help="Print inputs and prompt; no API calls, no writes")
    ap.add_argument("--check", action="store_true", help="Report missing/stale descriptions; no API calls")
    args = ap.parse_args()

    model = (args.model or os.getenv("HOMEFIT_ANTHROPIC_MODEL", "") or "").strip() or "claude-haiku-4-5-20251001"
    wanted = {n.strip() for n in args.names.split(",")} if args.names else None

    with open(args.input, encoding="utf-8") as f:
        raw_lines = [ln.rstrip("\n") for ln in f if ln.strip()]

    todo: List[int] = []
    stale = missing = 0
    for i, ln in enumerate(raw_lines):
        row = json.loads(ln)
        name = (row.get("catalog") or {}).get("name")
        if wanted and name not in wanted:
            continue
        inputs = build_inputs(row)
        if inputs is None:
            continue
        meta = (row.get("score") or {}).get("place_description_meta") or {}
        has = bool((row.get("score") or {}).get("place_description"))
        current = input_hash(inputs, model)
        if not has:
            missing += 1
        elif meta.get("input_hash") != current:
            stale += 1
        elif not args.force:
            continue
        todo.append(i)

    print(f"{len(raw_lines)} rows | missing: {missing} | stale: {stale} | to generate: {len(todo)}")
    if args.limit:
        todo = todo[: args.limit]
    if args.check:
        return 0

    if args.dry_run:
        for i in todo[:2]:
            row = json.loads(raw_lines[i])
            print("=" * 70)
            print(build_prompt(build_inputs(row)))
        return 0

    out_path = args.input if args.in_place else args.output
    if out_path is None:
        print("Provide --output or --in-place", file=sys.stderr)
        return 1

    try:
        import anthropic
    except ImportError:
        print("anthropic package not installed", file=sys.stderr)
        return 1
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        print("ANTHROPIC_API_KEY is not set", file=sys.stderr)
        return 1
    client = anthropic.Anthropic(api_key=key)

    out_lines = list(raw_lines)
    done = 0
    for n, i in enumerate(todo, 1):
        row = json.loads(raw_lines[i])
        inputs = build_inputs(row)
        name = row["catalog"]["name"]
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=400,
                messages=[{"role": "user", "content": build_prompt(inputs)}],
            )
            text = resp.content[0].text.strip().replace("—", ",")
        except Exception as e:  # keep going; one failure should not lose the run
            print(f"[{n}/{len(todo)}] {name}: FAILED {e}")
            continue
        row["score"]["place_description"] = text
        row["score"]["place_description_meta"] = {
            "input_hash": input_hash(inputs, model),
            "model": model,
            "prompt_version": PROMPT_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        out_lines[i] = json.dumps(row, ensure_ascii=False)
        done += 1
        print(f"[{n}/{len(todo)}] {name}: {text[:110]}...")
        time.sleep(args.delay)

    with open(out_path, "w", encoding="utf-8") as f:
        for ln in out_lines:
            f.write(ln + "\n")
    print(f"Wrote {out_path} ({done} generated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

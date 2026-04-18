#!/usr/bin/env python3
"""
Recompute longevity_index, status_signal, happiness_index from stored catalog JSONL
without re-running pillars (uses current data/status_signal_baselines.json, etc.).

Input lines match batch_score_place_catalog / merged JSONL: { catalog, success, score?, ... }.

Status Signal luxury runs the dedicated OSM luxury Overpass and merges per-bucket counts with
amenities ``business_list`` when rows include lat/lon (max per bucket).

  cd /path/to/home-fit
  PYTHONPATH=. python3 scripts/catalog/recompute_catalog_composites.py
  PYTHONPATH=. python3 scripts/catalog/recompute_catalog_composites.py --in-place \\
    --input data/nyc_metro_place_catalog_scores_merged.jsonl
  PYTHONPATH=. python3 scripts/catalog/recompute_catalog_composites.py \\
    --only-search-query "Ardsley, NY" \\
    --only-search-query "Floral Park, NY" \\
    --only-search-query "Merrick, NY" \\
    --output data/catalog_three_recomputed.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_INPUT = REPO_ROOT / "data" / "nyc_metro_place_catalog_scores_merged.jsonl"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl"

_COMPOSITE_KEYS = (
    "longevity_index",
    "longevity_index_contributions",
    "status_signal",
    "status_signal_breakdown",
    "happiness_index",
    "happiness_index_breakdown",
)


def _merge_composites_into_score(score: Dict[str, Any], composites: Dict[str, Any]) -> None:
    for k in _COMPOSITE_KEYS:
        if k in composites and composites[k] is not None:
            score[k] = composites[k]
    iv = composites.get("indices_version")
    if iv is not None:
        md = score.get("metadata")
        if not isinstance(md, dict):
            md = {}
            score["metadata"] = md
        md["indices_version"] = iv


def main() -> int:
    from pillars.composite_indices import recompute_composites_from_payload

    ap = argparse.ArgumentParser(
        description="Recompute composite indices from catalog JSONL score payloads (no pillar re-run)."
    )
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Source JSONL")
    ap.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSONL (default: ...merged.composites_recomputed.jsonl). Incompatible with --in-place.",
    )
    ap.add_argument(
        "--in-place",
        action="store_true",
        help="Write back to --input after a timestamped .bak copy (same path as input)",
    )
    ap.add_argument(
        "--max-rows",
        type=int,
        default=0,
        help="Recompute at most this many successful score rows (after --only-search-query filter); 0 = all",
    )
    ap.add_argument(
        "--only-search-query",
        action="append",
        default=None,
        metavar="QUERY",
        help="Only recompute rows whose catalog search_query matches exactly (repeat flag). E.g. --only-search-query \"Ardsley, NY\"",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Recompute in memory but do not write output file",
    )
    ap.add_argument(
        "--no-backup",
        action="store_true",
        help="With --in-place, write the output without creating a timestamped .bak copy.",
    )
    args = ap.parse_args()

    if args.in_place and args.output is not None:
        print("Use either --in-place or --output, not both.", file=sys.stderr)
        return 1
    if args.no_backup and not args.in_place:
        print("--no-backup only applies with --in-place.", file=sys.stderr)
        return 1

    out_path: Path
    if args.in_place:
        out_path = args.input
    elif args.output is not None:
        out_path = args.output
    else:
        out_path = DEFAULT_OUTPUT

    if not args.input.is_file():
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 1

    only_set: Optional[Set[str]] = None
    if args.only_search_query:
        only_set = {q.strip() for q in args.only_search_query if q and q.strip()}

    budget = args.max_rows if args.max_rows > 0 else None
    processed = 0
    skipped = 0
    errors = 0
    lines_out: list[str] = []
    matched_queries: Set[str] = set()

    with args.input.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError as e:
                print(f"Line {line_no}: JSON skip: {e}", file=sys.stderr)
                errors += 1
                if not args.dry_run:
                    lines_out.append(raw)
                continue

            if not record.get("success"):
                skipped += 1
                if not args.dry_run:
                    lines_out.append(json.dumps(record, ensure_ascii=False))
                continue

            score = record.get("score")
            if not isinstance(score, dict):
                skipped += 1
                if not args.dry_run:
                    lines_out.append(json.dumps(record, ensure_ascii=False))
                continue

            catalog = record.get("catalog") if isinstance(record.get("catalog"), dict) else {}
            sq = (catalog.get("search_query") or "").strip()

            if only_set is not None and sq not in only_set:
                if not args.dry_run:
                    lines_out.append(json.dumps(record, ensure_ascii=False))
                continue

            if only_set is not None and sq in only_set:
                matched_queries.add(sq)

            if budget is not None and processed >= budget:
                if not args.dry_run:
                    lines_out.append(json.dumps(record, ensure_ascii=False))
                continue

            try:
                composites = recompute_composites_from_payload(score)
                _merge_composites_into_score(score, composites)
                record["score"] = score
                processed += 1
            except Exception as e:
                print(f"Line {line_no}: recompute error: {e}", file=sys.stderr)
                errors += 1
                if not args.dry_run:
                    lines_out.append(json.dumps(record, ensure_ascii=False))
                continue

            if not args.dry_run:
                lines_out.append(json.dumps(record, ensure_ascii=False))

    if only_set is not None:
        missing = only_set - matched_queries
        if missing:
            print(f"Warning: no catalog row for search_query: {sorted(missing)}", file=sys.stderr)

    if args.dry_run:
        print(
            f"dry-run: recomputed {processed} rows in memory "
            f"(skipped non-success/no-score: {skipped}, parse errors: {errors})"
        )
        return 0

    if args.in_place and not args.no_backup:
        bak = args.input.parent / f"{args.input.name}.bak.{time.strftime('%Y%m%d-%H%M%S')}"
        bak.write_text(args.input.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Backup: {bak}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as out:
        for line in lines_out:
            out.write(line + "\n")

    print(
        f"Wrote {out_path} — recomputed {processed} scores, "
        f"skipped {skipped} non-success/missing score, errors {errors}"
    )
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

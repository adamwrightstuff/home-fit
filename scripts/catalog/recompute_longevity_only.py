#!/usr/bin/env python3
"""
Recompute ONLY the longevity index (contributions, breakdown, version stamp) from stored pillar scores.

Offline: no API, Census or Overpass calls. Touches nothing else in a row (no total score, happiness or
status signal). Preserves each file's existing JSON formatting (compact or default).

  PYTHONPATH=. python3 scripts/catalog/recompute_longevity_only.py data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl ...
  Add --dry-run to report changes without writing.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pillars.composite_indices import INDEX_VERSION_LONGEVITY, compute_longevity_index  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    for path in args.files:
        raw_lines = path.read_text(encoding="utf-8").split("\n")
        compact = False
        for ln in raw_lines:
            if ln.strip():
                compact = json.dumps(json.loads(ln), separators=(",", ":")) == ln
                break
        dump = (lambda o: json.dumps(o, separators=(",", ":"))) if compact else json.dumps
        out: List[str] = []
        n = 0
        deltas: List[float] = []
        for ln in raw_lines:
            if not ln.strip():
                out.append(ln)
                continue
            row = json.loads(ln)
            sc = row.get("score") if row.get("success") else None
            if isinstance(sc, dict) and isinstance(sc.get("livability_pillars"), dict):
                p = sc["livability_pillars"]
                new, contrib = compute_longevity_index(p, token_allocation={k: 1.0 for k in p})
                old = sc.get("longevity_index")
                n += 1
                if isinstance(old, (int, float)):
                    deltas.append(new - old)
                sc["longevity_index"] = new
                sc["longevity_index_contributions"] = contrib
                sc["longevity_index_breakdown"] = dict(contrib)
                iv = (sc.setdefault("metadata", {})).setdefault("indices_version", {})
                iv["longevity"] = INDEX_VERSION_LONGEVITY
            out.append(dump(row))
        mean = sum(deltas) / len(deltas) if deltas else 0.0
        print(f"{path.name}: {n} rows recomputed, mean change {mean:+.2f}, "
              f"min {min(deltas, default=0):+.1f}, max {max(deltas, default=0):+.1f}")
        if not args.dry_run:
            path.write_text("\n".join(out), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

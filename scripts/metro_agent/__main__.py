from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import diagnose as dg
from . import preflight as pf


def main() -> int:
    ap = argparse.ArgumentParser(prog="metro_agent")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("preflight", help="check every dependency before scoring a metro")
    p1.add_argument("--metro", required=True, help="slug, e.g. austin")
    p1.add_argument("--csv", type=Path, help="place list (default data/<metro>_metro_place_catalog.csv)")
    p1.add_argument("--out", type=Path, help="scores file to inspect for leftovers")
    p1.add_argument("--api-base", default=os.environ.get("HOMEFIT_API_BASE"))
    p1.add_argument("--no-network", action="store_true")

    p2 = sub.add_parser("diagnose", help="classify every failed or empty pillar by cause")
    p2.add_argument("--input", type=Path, required=True)
    p2.add_argument("--json", action="store_true", help="write <input>.diagnosis.json")

    a = ap.parse_args()
    if a.cmd == "preflight":
        csv_path = a.csv or pf.REPO / "data" / f"{a.metro}_metro_place_catalog.csv"
        out = a.out or pf.REPO / "data" / f"{a.metro}_metro_place_catalog_scores_merged.composites_recomputed.jsonl"
        checks = pf.run(a.metro, csv_path, a.api_base, out, network=not a.no_network)
        print(pf.format_report(checks))
        return 1 if any(c.status == pf.FAIL for c in checks) else 0
    rows = dg.load_rows(a.input)
    result = dg.diagnose(rows)
    print(dg.format_report(result, a.input.name))
    if a.json:
        dest = a.input.with_suffix(".diagnosis.json")
        dest.write_text(json.dumps(result, indent=2))
        print(f"\nwrote {dest}")
    return 1 if result["material_places"] else 0


if __name__ == "__main__":
    sys.exit(main())

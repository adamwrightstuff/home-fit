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

    p3 = sub.add_parser("resolve", help="retry what can be retried, hand off what cannot")
    p3.add_argument("--input", type=Path, required=True)
    p3.add_argument("--api-base", default=os.environ.get("HOMEFIT_API_BASE", "http://127.0.0.1:8000"))
    p3.add_argument("--rounds", type=int, default=3)
    p3.add_argument("--delay", type=float, default=2.0)
    p3.add_argument("--include-minor", action="store_true", help="also retry minor findings")
    p3.add_argument("--dry-run", action="store_true")
    p3.add_argument("--skip-composites", action="store_true")

    p5 = sub.add_parser("probe", help="ask the upstream services directly about places resolve could not fix")
    p5.add_argument("--input", type=Path, required=True)

    p4 = sub.add_parser("run", help="whole launch in one command: preflight, score, resolve, gate")
    p4.add_argument("--metro", required=True)
    p4.add_argument("--api-base", default=os.environ.get("HOMEFIT_API_BASE", "http://127.0.0.1:8000"))
    p4.add_argument("--csv", type=Path)
    p4.add_argument("--out", type=Path)
    p4.add_argument("--rounds", type=int, default=3)
    p4.add_argument("--push", action="store_true", help="commit and push the catalog file if the gate passes")
    p4.add_argument("--skip-score", action="store_true", help="only resolve and gate an existing file")
    p4.add_argument("--no-server", action="store_true", help="do not start a local API automatically")

    a = ap.parse_args()
    if a.cmd == "probe":
        from . import probe as pr
        pf._load_env()
        pr.probe(dg.load_rows(a.input))
        return 0
    if a.cmd == "run":
        from . import run as runner
        pf._load_env()
        return runner.run_pipeline(a.metro, api_base=a.api_base.rstrip("/"), csv_path=a.csv, out_path=a.out,
                                   rounds=a.rounds, push=a.push, skip_score=a.skip_score,
                                   manage_server=not a.no_server)
    if a.cmd == "resolve":
        from . import resolve as rs
        summary = rs.resolve(a.input, a.api_base.rstrip("/"), max_rounds=a.rounds, delay=a.delay,
                             include_minor=a.include_minor, dry_run=a.dry_run,
                             recompute=None if a.skip_composites else rs._default_recompute)
        print(rs.format_summary(summary))
        if not a.dry_run:
            a.input.with_suffix(".resolution.json").write_text(json.dumps(summary, indent=2))
        return 1 if summary["material_places_left"] else 0
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

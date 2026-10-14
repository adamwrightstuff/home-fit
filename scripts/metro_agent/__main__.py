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

    p6 = sub.add_parser("validate", help="check results against independent sources (Census, peers)")
    p6.add_argument("--input", type=Path, required=True)
    p6.add_argument("--apply", action="store_true", help="record confirmed-genuine gaps so the gate accepts them")

    p7 = sub.add_parser("fbi", help="why does community safety have no data here, and which agency could serve it")
    p7.add_argument("--input", type=Path, required=True)
    p7.add_argument("--places", help="comma-separated place names to limit to")
    p7.add_argument("--suggest", action="store_true", help="write <input>.fbi_suggestions.json (nothing is applied)")

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

    p8 = sub.add_parser("health", help="audit every launched metro like the launch playbook; --fix retries what can be retried")
    p8.add_argument("--metro", action="append", help="limit to a metro (repeatable); default all")
    p8.add_argument("--offline", action="store_true", help="skip the Census cross-checks")
    p8.add_argument("--fix", action="store_true", help="run the resolver on metros with retryable problems, then re-audit")
    p8.add_argument("--api-base", default=os.environ.get("HOMEFIT_API_BASE", "http://127.0.0.1:8000"))
    p8.add_argument("--json", type=Path, help="also write the full report here")

    p9 = sub.add_parser("accept", help="consciously accept a remaining gap so the gate stops blocking on it")
    p9.add_argument("--input", type=Path, required=True)
    p9.add_argument("--place", required=True)
    p9.add_argument("--pillar", required=True)
    p9.add_argument("--reason", required=True, help="why this gap is genuine or acceptable (recorded in the accepted file)")

    p10 = sub.add_parser("withhold", help="blank pillars whose lookups failed (shown as unknown) so the metro can publish; rescore fills them in")
    p10.add_argument("--input", type=Path, required=True)
    p10.add_argument("--dry-run", action="store_true")

    a = ap.parse_args()
    if a.cmd == "withhold":
        from . import withhold as wh
        n = wh.withhold(a.input, dry_run=a.dry_run)
        print(f"\n{n} pillar values {'would be ' if a.dry_run else ''}withheld")
        return 0
    if a.cmd == "accept":
        from . import validate as vd
        n = vd.write_accepted(a.input, [vd.Verdict(a.place, a.pillar, vd.CONSISTENT, f"accepted by hand: {a.reason}")])
        print(f"recorded; {n} accepted gaps in {vd.accepted_path(a.input).name}")
        return 0
    if a.cmd == "health":
        from . import health as hl
        from . import run as runner
        pf._load_env()
        reports = hl.audit_all(a.metro, offline=a.offline)
        print(hl.format_report(reports))
        if a.fix:
            base = a.api_base.rstrip("/")
            proc = runner.start_server(base, print) if runner.is_local(base) else None
            try:
                fixed = hl.fix(reports, base)
            finally:
                if proc is not None:
                    proc.terminate()
            if fixed:
                print("\n\nRE-AUDIT AFTER FIXES\n")
                reports = hl.audit_all(a.metro, offline=a.offline)
                print(hl.format_report(reports))
        if a.json:
            a.json.write_text(json.dumps(reports, indent=2))
        return 1 if any(r["verdict"] == hl.UNHEALTHY for r in reports) else 0
    if a.cmd == "validate":
        from . import validate as vd
        pf._load_env()
        verdicts = vd.validate(dg.load_rows(a.input))
        print(vd.format_report(verdicts))
        if a.apply:
            print(f"\n{vd.write_accepted(a.input, verdicts)} accepted gaps recorded in {vd.accepted_path(a.input).name}")
        return 1 if any(v.kind == vd.CONTRADICTED for v in verdicts) else 0
    if a.cmd == "fbi":
        from . import fbi_probe as fp
        pf._load_env()
        fp.run(dg.load_rows(a.input), only=[x.strip() for x in a.places.split(",")] if a.places else None,
               suggest_path=a.input.with_suffix(".fbi_suggestions.json") if a.suggest else None)
        return 0
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
    result = dg.diagnose(rows, accepted=dg.load_accepted(a.input))
    print(dg.format_report(result, a.input.name))
    if a.json:
        dest = a.input.with_suffix(".diagnosis.json")
        dest.write_text(json.dumps(result, indent=2))
        print(f"\nwrote {dest}")
    return 1 if result["material_places"] else 0


if __name__ == "__main__":
    sys.exit(main())

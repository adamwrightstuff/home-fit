#!/usr/bin/env python3
"""
Parity check: frontend computeHappinessIndex (frontend/lib/pillars.ts, run in Node) against the stored
happiness_index in every catalog row. Offline. Needs node and a typescript install (frontend/node_modules).

  PYTHONPATH=. python3 scripts/catalog/happiness_frontend_parity.py [--ts-dir frontend] [files...]

Defaults to all data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl. Differences of 0.1 are
reported as rounding ties (Python and JavaScript break an exact x.x5 differently); exit 1 on anything larger.
"""
from __future__ import annotations
import argparse, glob, json, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
JS = r"""
const fs=require('fs');const ts=require(process.argv[2]+'/node_modules/typescript');
const src=fs.readFileSync(process.argv[3],'utf8');
const i=src.indexOf('export function computeHappinessIndex');const j=src.indexOf('/** API `only=` list');
const js=ts.transpileModule(src.slice(i,j),{compilerOptions:{target:'ES2020',module:'ESNext'}}).outputText.replace('export function','function');
const f=new Function(js+';return computeHappinessIndex;')();
const rows=JSON.parse(fs.readFileSync(process.argv[4],'utf8'));
fs.writeFileSync(process.argv[5],JSON.stringify(rows.map(p=>f(p))));
"""

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*")
    ap.add_argument("--ts-dir", default=str(REPO / "frontend"))
    a = ap.parse_args()
    files = a.files or sorted(glob.glob(str(REPO / "data" / "*_metro_place_catalog_scores_merged.composites_recomputed.jsonl")))
    names, pillars, stored = [], [], []
    for fn in files:
        for ln in open(fn, encoding="utf-8"):
            if not ln.strip():
                continue
            r = json.loads(ln)
            if r.get("success") and isinstance(r.get("score"), dict):
                names.append(r["catalog"]["name"]); pillars.append(r["score"].get("livability_pillars") or {})
                stored.append(r["score"].get("happiness_index"))
    with tempfile.TemporaryDirectory() as d:
        pin, pout, pjs = Path(d, "in.json"), Path(d, "out.json"), Path(d, "run.js")
        pin.write_text(json.dumps(pillars)); pjs.write_text(JS)
        subprocess.run(["node", str(pjs), a.ts_dir, str(REPO / "frontend/lib/pillars.ts"), str(pin), str(pout)], check=True)
        fe = json.loads(pout.read_text())
    bad = ties = 0
    for n, f, s in zip(names, fe, stored):
        if (f is None) != (s is None):
            bad += 1; print("null mismatch", n); continue
        if f is None:
            continue
        d = abs(f - s)
        if d > 0.101:
            bad += 1; print("MISMATCH", n, f, s)
        elif d > 0.051:
            ties += 1; print("rounding tie", n, f, s)
    print(f"{len(names)} rows: {bad} mismatches, {ties} rounding-tie differences of 0.1")
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())

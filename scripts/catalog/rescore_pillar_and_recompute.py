#!/usr/bin/env python3
"""
Rescore a pillar then immediately recompute composites — sequentially, no interleave.

Without this wrapper, running composites concurrently with a rescore causes a race:
composites loads an in-flight catalog snapshot and writes it back, stomping new scores.

Usage:
    cd /path/to/home-fit

    # Built beauty — both catalogs
    PYTHONPATH=. python3 scripts/catalog/rescore_pillar_and_recompute.py built_beauty

    # Built beauty — NYC only
    PYTHONPATH=. python3 scripts/catalog/rescore_pillar_and_recompute.py built_beauty --catalog nyc

    # Built beauty — LA only
    PYTHONPATH=. python3 scripts/catalog/rescore_pillar_and_recompute.py built_beauty --catalog la
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

NYC = REPO / "data" / "nyc_metro_place_catalog_scores_merged.jsonl"
LA  = REPO / "data" / "la_metro_place_catalog_scores_merged.jsonl"

PILLAR_SCRIPTS = {
    "built_beauty": REPO / "scripts" / "catalog" / "rescore_built_beauty_full.py",
}


def run(cmd: list[str]) -> None:
    print(f"\n>>> {' '.join(str(c) for c in cmd)}\n")
    result = subprocess.run(cmd, cwd=REPO)
    if result.returncode != 0:
        print(f"\nERROR: command exited {result.returncode}. Aborting before composites.")
        sys.exit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pillar", choices=list(PILLAR_SCRIPTS))
    parser.add_argument("--catalog", choices=["nyc", "la", "both"], default="both")
    args = parser.parse_args()

    script = PILLAR_SCRIPTS[args.pillar]
    catalogs = {
        "nyc": [NYC],
        "la":  [LA],
        "both": [NYC, LA],
    }[args.catalog]

    python = sys.executable

    # Step 1: rescore pillar
    t0 = time.time()
    run([python, "-c",
         f"import sys; sys.path.insert(0, '{REPO}'); "
         f"from scripts.catalog.{script.stem} import process_catalog; "
         f"from pathlib import Path; "
         + "; ".join(f"process_catalog(Path('{c}'))" for c in catalogs if c.exists())])

    elapsed = time.time() - t0
    print(f"\nRescore finished in {elapsed/60:.1f} min")

    # Step 2: recompute composites for each catalog
    composites = REPO / "scripts" / "catalog" / "recompute_catalog_composites.py"
    for catalog in catalogs:
        if not catalog.exists():
            print(f"Skipping composites for missing catalog: {catalog.name}")
            continue
        run([python, str(composites), "--input", str(catalog), "--in-place", "--no-backup"])


if __name__ == "__main__":
    main()

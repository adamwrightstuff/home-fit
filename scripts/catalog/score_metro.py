#!/usr/bin/env python3
"""
Single-command metro scorer. Runs all phases in order so a new metro comes
out complete — no separate backfill or patch scripts needed afterward.

Usage:
    HOMEFIT_API_BASE=https://home-fit-production.up.railway.app \\
    HOMEFIT_PROXY_SECRET=<secret> \\
    HOMEFIT_TRANSIT_STABLE_COMMUTE=true \\
    ANTHROPIC_API_KEY=<key> \\
    PYTHONPATH=. python3 scripts/catalog/score_metro.py \\
        --csv  data/sf_metro_place_catalog.csv \\
        --out  data/sf_metro_place_catalog_scores_merged.composites_recomputed.jsonl \\
        --metro sf

Phases (all run unless --skip-* flags used):
  0. baselines — build status_signal CBSA baselines for the new metro (Census API)
  1. batch     — API score every place in --csv (resumable)
  2. retry     — re-run any failed pillars
  3. housing   — Census ACS B25024 housing stock (housing-type filter)
  4. zips      — Nominatim ZIP code backfill
  5. lean      — political lean data
  6. scene     — local_scene_bucket from stored business_list
  7. labels    — best-fit preference labels on NB + built_environment
  8. schools   — charter/public flag on school arrays
  9. archs     — Claude-based archetype summaries (costs ~$5-15, requires ANTHROPIC_API_KEY)
 10. compose   — recompute composites (longevity, status_signal, happiness_index)
 11. safety    — rebuild community_safety_baselines.json from all metro catalog files

Skip individual phases with --skip-baselines, --skip-batch, --skip-safety, etc.
Skip archs by default if ANTHROPIC_API_KEY is unset; override with --archs.

The --out file is used as the working file throughout. After phase 1, every
subsequent phase reads and writes it in-place. At the end it contains the
complete, deployment-ready catalog.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except Exception:
    pass


# ── helpers ──────────────────────────────────────────────────────────────────

def _banner(phase: int, name: str) -> None:
    print(f"\n{'='*60}", flush=True)
    print(f"  Phase {phase}: {name}", flush=True)
    print(f"{'='*60}", flush=True)


def _coverage(path: Path) -> None:
    """Print a quick coverage table for key fields."""
    checks = {
        "housing_stock.pct_low_density": 0,
        "built_environment.score": 0,
        "political_lean.lean_2024": 0,
        "local_scene_bucket": 0,
        "zip_code": 0,
        "archetype": 0,
    }
    total = 0
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                p = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not p.get("success", True):
                continue
            total += 1
            s = p.get("score") or {}
            cat = p.get("catalog") or {}
            pillars = s.get("livability_pillars") or {}

            hs = s.get("housing_stock") or {}
            if isinstance(hs.get("pct_low_density"), (int, float)):
                checks["housing_stock.pct_low_density"] += 1
            be = pillars.get("built_environment") or {}
            if be.get("score") is not None:
                checks["built_environment.score"] += 1
            pl = pillars.get("political_lean") or {}
            if (pl.get("breakdown") or {}).get("lean_2024") is not None:
                checks["political_lean.lean_2024"] += 1
            if s.get("local_scene_bucket") is not None:
                checks["local_scene_bucket"] += 1
            if cat.get("zip_code") or s.get("zip_code"):
                checks["zip_code"] += 1
            ss = s.get("status_signal_breakdown") or {}
            if ss.get("archetype"):
                checks["archetype"] += 1

    print(f"\nCoverage ({total} places):")
    for k, v in checks.items():
        pct = v / total * 100 if total else 0
        flag = "✓" if pct >= 95 else ("~" if pct >= 50 else "✗")
        print(f"  {flag} {k}: {v}/{total} ({pct:.0f}%)")


# ── phase implementations ─────────────────────────────────────────────────────

def phase_baselines(metro: str) -> None:
    """Add/rebuild status_signal CBSA baselines for this metro before scoring."""
    import subprocess
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts/baselines/build_metro_baselines_from_cbsa.py"),
        "--only", f"{metro}_metro",
    ]
    result = subprocess.run(cmd, env={**os.environ, "PYTHONPATH": str(REPO_ROOT)})
    if result.returncode != 0:
        print(f"  WARNING: baseline build exited {result.returncode} — scoring will use division-level fallback")


def phase_safety_baselines(out_path: Path) -> None:
    """Rebuild community_safety_baselines.json from all catalog JSONL files including the new metro."""
    import subprocess
    all_catalogs = list(REPO_ROOT.glob("data/*_metro_place_catalog_scores_merged.composites_recomputed.jsonl"))
    if not all_catalogs:
        # fall back to any merged JSONL
        all_catalogs = list(REPO_ROOT.glob("data/*_metro_place_catalog_scores_merged.jsonl"))
    if str(out_path) not in [str(p) for p in all_catalogs]:
        all_catalogs.append(out_path)
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts/baselines/build_community_safety_baselines.py"),
        "--inputs", *[str(p) for p in all_catalogs],
    ]
    result = subprocess.run(cmd, env={**os.environ, "PYTHONPATH": str(REPO_ROOT)})
    if result.returncode != 0:
        print(f"  WARNING: safety baselines build exited {result.returncode}")


def phase_batch(csv_path: Path, out_path: Path, args) -> None:
    """Call the API for every place in the CSV. Resumable."""
    import requests
    import csv as csv_mod

    base_url = os.environ.get("HOMEFIT_API_BASE", "http://127.0.0.1:8000").rstrip("/")
    secret = os.environ.get("HOMEFIT_PROXY_SECRET", "").strip()
    headers = {"X-HomeFit-Proxy-Secret": secret} if secret else {}
    session = requests.Session()
    session.headers.update(headers)

    def catalog_key(row):
        return f"{row.get('name','')}|{row.get('county_borough','')}|{row.get('state_abbr','')}"

    done_keys: set = set()
    if out_path.exists():
        with out_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("success"):
                    done_keys.add(catalog_key(obj.get("catalog") or {}))

    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv_mod.DictReader(f))

    pending = [r for r in rows if catalog_key(r) not in done_keys]
    print(f"  {len(rows)} places total | {len(done_keys)} already scored | {len(pending)} to run")

    processed = 0
    with out_path.open("a", encoding="utf-8") as out:
        for i, row in enumerate(pending):
            key = catalog_key(row)
            location = (row.get("search_query") or "").strip()
            if not location:
                out.write(json.dumps({"catalog": row, "success": False, "error": "empty search_query"}, ensure_ascii=False) + "\n")
                out.flush()
                print(f"  [{i+1}/{len(pending)}] {key} SKIP (empty search_query)")
                continue

            print(f"  [{i+1}/{len(pending)}] {key} …", end="", flush=True)
            try:
                lat_s, lon_s = row.get("lat", ""), row.get("lon", "")
                if lat_s and lon_s:
                    r = session.post(
                        f"{base_url}/score/jobs",
                        params={"location": location, "enable_schools": "false",
                                "lat": lat_s, "lon": lon_s, "test_mode": "true"},
                        timeout=120,
                    )
                    r.raise_for_status()
                    job_id = r.json().get("job_id")
                    if not job_id:
                        raise RuntimeError(f"No job_id: {r.json()}")
                    status_url = f"{base_url}/score/jobs/{job_id}"
                    deadline = time.time() + args.job_timeout
                    result = None
                    while time.time() < deadline:
                        time.sleep(args.poll_interval)
                        sr = session.get(status_url, timeout=120)
                        sr.raise_for_status()
                        st = sr.json()
                        status = (st.get("status") or "").lower()
                        if status == "done":
                            result = st.get("result")
                            break
                        if status == "error":
                            raise RuntimeError(f"Job failed: {st.get('detail') or st.get('error')}")
                    if result is None:
                        raise TimeoutError(f"Job {job_id} timed out after {args.job_timeout}s")
                else:
                    r = session.get(f"{base_url}/score",
                                    params={"location": location, "enable_schools": "false"},
                                    timeout=args.timeout)
                    r.raise_for_status()
                    result = r.json()

                out.write(json.dumps({"catalog": row, "success": True, "score": result}, ensure_ascii=False) + "\n")
                out.flush()
                processed += 1
                print(f" ok (score={result.get('total_score')!r})", flush=True)
            except Exception as e:
                out.write(json.dumps({"catalog": row, "success": False, "error": str(e)}, ensure_ascii=False) + "\n")
                out.flush()
                print(f" FAIL: {e}", flush=True)

            if i < len(pending) - 1 and args.delay > 0:
                time.sleep(args.delay)

    print(f"  Done. {processed} new places scored.")


def phase_retry(out_path: Path, args) -> None:
    """Re-run failed pillars via the API."""
    import subprocess
    cmd = [
        sys.executable, str(REPO_ROOT / "scripts/catalog/rerun_failed_catalog_pillars.py"),
        str(out_path),
        "--base-url", os.environ.get("HOMEFIT_API_BASE", "http://127.0.0.1:8000"),
        "--in-place",
    ]
    result = subprocess.run(cmd, env={**os.environ, "PYTHONPATH": str(REPO_ROOT)})
    if result.returncode != 0:
        print(f"  WARNING: retry phase exited {result.returncode}")


def phase_housing(out_path: Path) -> None:
    from scripts.catalog.backfill_housing_stock import backfill
    backfill(str(out_path), str(out_path), dry_run=False, skip_existing=True)


def phase_zips(out_path: Path) -> None:
    from scripts.catalog.backfill_zip_codes import backfill_zips
    backfill_zips(str(out_path))


def phase_lean(out_path: Path) -> None:
    from scripts.catalog.rescore_political_lean import process_catalog
    process_catalog(out_path, in_place=True, no_backup=True, dry_run=False)


def phase_scene(out_path: Path) -> None:
    from scripts.catalog.compute_local_scene import process
    process(out_path)


def phase_labels(out_path: Path) -> None:
    from scripts.catalog.patch_best_fit_labels import patch
    patch(out_path, in_place=True, no_backup=True)


def phase_schools(out_path: Path, metro: str) -> None:
    from scripts.catalog.patch_school_charter_flag import patch_catalog, load_nces
    nces_path = str(REPO_ROOT / "data" / "nces_schools.csv")
    if not Path(nces_path).exists():
        print(f"  SKIP — NCES file not found at {nces_path}")
        return
    nces = load_nces(nces_path)
    is_la = metro.lower() == "la"
    updated, total, skipped = patch_catalog(str(out_path), nces, is_la=is_la)
    print(f"  {updated} updated, {skipped} skipped of {total} total")


def phase_archs(out_path: Path, metro: str) -> None:
    try:
        import importlib
        mod = importlib.import_module("scripts.catalog.generate_archetype_summaries")
        mod.process_catalog(str(out_path), metro=metro, dry_run=False, force=False)
    except ModuleNotFoundError as e:
        print(f"  SKIP — missing dependency: {e}")
        print("  Install with: pip install anthropic")


def phase_compose(out_path: Path) -> None:
    import subprocess
    cmd = [
        sys.executable, str(REPO_ROOT / "scripts/catalog/recompute_catalog_composites.py"),
        "--input", str(out_path),
        "--output", str(out_path),
    ]
    result = subprocess.run(cmd, env={**os.environ, "PYTHONPATH": str(REPO_ROOT)})
    if result.returncode != 0:
        raise RuntimeError(f"Composite recompute failed (exit {result.returncode})")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(
        description="Score a new metro: all phases in one command.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--csv", type=Path, required=True, help="Place catalog CSV")
    p.add_argument("--out", type=Path, required=True, help="Output JSONL (working file + final result)")
    p.add_argument("--metro", required=True, help="Metro slug: nyc | la | sf | <new>")
    p.add_argument("--delay", type=float, default=2.0, help="Seconds between API calls (default 2)")
    p.add_argument("--timeout", type=int, default=900, help="GET /score timeout in seconds")
    p.add_argument("--job-timeout", type=int, default=900, help="Job polling timeout in seconds")
    p.add_argument("--poll-interval", type=float, default=2.0, help="Job poll interval in seconds")
    p.add_argument("--archs", action="store_true",
                   help="Run archetype summaries phase (Claude API, ~$5-15; auto-enabled if ANTHROPIC_API_KEY set)")
    p.add_argument("--skip-baselines", action="store_true", help="Skip phase 0 (status_signal CBSA baselines)")
    p.add_argument("--skip-batch",     action="store_true", help="Skip phase 1 (API scoring)")
    p.add_argument("--skip-retry",     action="store_true", help="Skip phase 2 (retry failures)")
    p.add_argument("--skip-housing",   action="store_true", help="Skip phase 3 (housing stock)")
    p.add_argument("--skip-zips",      action="store_true", help="Skip phase 4 (ZIP codes)")
    p.add_argument("--skip-lean",      action="store_true", help="Skip phase 5 (political lean)")
    p.add_argument("--skip-scene",     action="store_true", help="Skip phase 6 (local scene)")
    p.add_argument("--skip-labels",    action="store_true", help="Skip phase 7 (best-fit labels)")
    p.add_argument("--skip-schools",   action="store_true", help="Skip phase 8 (charter school flag)")
    p.add_argument("--skip-archs",     action="store_true", help="Skip phase 9 (archetype summaries)")
    p.add_argument("--skip-compose",   action="store_true", help="Skip phase 10 (composite recompute)")
    p.add_argument("--skip-safety",    action="store_true", help="Skip phase 11 (community safety baselines)")
    args = p.parse_args()

    if not args.csv.is_file():
        print(f"ERROR: catalog CSV not found: {args.csv}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    def _anthropic_available() -> bool:
        try:
            import importlib
            importlib.import_module("anthropic")
            return True
        except ModuleNotFoundError:
            return False

    run_archs = args.archs or (bool(os.environ.get("ANTHROPIC_API_KEY")) and _anthropic_available() and not args.skip_archs)

    print(f"Metro:  {args.metro}")
    print(f"CSV:    {args.csv}")
    print(f"Output: {args.out}")
    print(f"API:    {os.environ.get('HOMEFIT_API_BASE', 'http://127.0.0.1:8000')}")

    known_metros = {"nyc", "la", "sf"}
    if not args.skip_baselines:
        if args.metro in known_metros:
            _banner(0, f"Status signal CBSA baselines ({args.metro}_metro)")
            phase_baselines(args.metro)
        else:
            print(f"\n[Phase 0] New metro '{args.metro}' — add its CBSA to build_metro_baselines_from_cbsa.py first, then re-run with --skip-baselines after.")
            print("  See docs/METRO_EXPANSION_PLAYBOOK.md for CBSA county lists.")
    else:
        print("\n[skip] Phase 0: status_signal baselines")

    if not args.skip_batch:
        _banner(1, "Batch scoring (API)")
        phase_batch(args.csv, args.out, args)
    else:
        print("\n[skip] Phase 1: batch scoring")

    if not args.skip_retry:
        _banner(2, "Retry failed pillars")
        try:
            phase_retry(args.out, args)
        except Exception as e:
            print(f"  WARNING: retry phase failed: {e}")
    else:
        print("\n[skip] Phase 2: retry")

    if not args.skip_housing:
        _banner(3, "Housing stock (Census ACS B25024)")
        phase_housing(args.out)
    else:
        print("\n[skip] Phase 3: housing stock")

    if not args.skip_zips:
        _banner(4, "ZIP codes (Nominatim)")
        phase_zips(args.out)
    else:
        print("\n[skip] Phase 4: ZIP codes")

    if not args.skip_lean:
        _banner(5, "Political lean")
        phase_lean(args.out)
    else:
        print("\n[skip] Phase 5: political lean")

    if not args.skip_scene:
        _banner(6, "Local scene bucket")
        phase_scene(args.out)
    else:
        print("\n[skip] Phase 6: local scene")

    if not args.skip_labels:
        _banner(7, "Best-fit preference labels")
        phase_labels(args.out)
    else:
        print("\n[skip] Phase 7: best-fit labels")

    if not args.skip_schools:
        _banner(8, "Charter school flag")
        phase_schools(args.out, args.metro)
    else:
        print("\n[skip] Phase 8: charter school flag")

    if run_archs and not args.skip_archs:
        _banner(9, "Archetype summaries (Claude API)")
        phase_archs(args.out, args.metro)
    else:
        print("\n[skip] Phase 9: archetype summaries (pass --archs or set ANTHROPIC_API_KEY to enable)")

    if not args.skip_compose:
        _banner(10, "Recompute composites")
        phase_compose(args.out)
    else:
        print("\n[skip] Phase 10: composite recompute")

    if not args.skip_safety:
        _banner(11, "Community safety baselines (all metros)")
        phase_safety_baselines(args.out)
    else:
        print("\n[skip] Phase 11: community safety baselines")

    print(f"\n{'='*60}")
    print(f"  Complete: {args.out}")
    print(f"{'='*60}")
    _coverage(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

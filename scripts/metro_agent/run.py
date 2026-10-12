"""One command for a whole metro launch:

    PYTHONPATH=. python -m scripts.metro_agent run --metro chicago

Stages (stops at the first blocking problem, resumable by simply running it again):
  0. start the local API if the target is localhost and nothing is listening
  1. preflight        blocking failures stop the run before any scoring
  2. score            scripts/catalog/score_metro.py, then once more if any place failed outright
  3. resolve          retry upstream failures, hand off what retrying cannot fix
  4. validate         check against independent sources; confirmed-genuine gaps are accepted
  5. gate             PUBLISH: OK or BLOCKED
  6. optional push    only the metro's catalog file, only when the gate passes (--push)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import diagnose as dg
from . import preflight as pf
from . import resolve as rs
from . import validate as vd

REPO = pf.REPO


def is_local(api_base: str) -> bool:
    return "127.0.0.1" in api_base or "localhost" in api_base


def api_healthy(api_base: str) -> bool:
    import requests
    try:
        r = requests.get(f"{api_base}/health", timeout=10,
                         headers={"X-HomeFit-Proxy-Secret": os.environ.get("HOMEFIT_PROXY_SECRET", "")})
        return r.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def start_server(api_base: str, log: Callable[[str], None], wait_s: int = 180) -> Optional[subprocess.Popen]:
    """Start uvicorn if the local API is not already answering. Returns the process we started."""
    if api_healthy(api_base):
        log("API already running.")
        return None
    port = api_base.rsplit(":", 1)[-1].split("/")[0]
    log(f"starting local API on port {port}…")
    env = {**os.environ, "PYTHONPATH": str(REPO), "HOMEFIT_TRANSIT_STABLE_COMMUTE": "true"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", port],
                            cwd=str(REPO), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + wait_s
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("the local API exited during startup (run uvicorn by hand to see why)")
        if api_healthy(api_base):
            log("API is up.")
            return proc
        time.sleep(3)
    proc.terminate()
    raise RuntimeError(f"the local API did not answer within {wait_s}s")


def _failed_places(path: Path) -> int:
    if not path.is_file():
        return -1
    return sum(1 for r in dg.load_rows(path) if not r.get("success"))


def drop_stale_pins(csv_path: Path, out_path: Path, log: Callable[[str], None] = print, tol: float = 0.0005) -> int:
    """Remove scored rows whose pin in the place list has changed, so the resumable scorer redoes them."""
    import csv as csv_mod
    if not out_path.is_file() or not csv_path.is_file():
        return 0
    with csv_path.open(newline="", encoding="utf-8") as f:
        pins = {(r["name"], r["county_borough"], r["state_abbr"]): (float(r["lat"]), float(r["lon"]))
                for r in csv_mod.DictReader(f)}
    rows, keep, dropped = dg.load_rows(out_path), [], []
    for r in rows:
        c = r.get("catalog") or {}
        k = (c.get("name"), c.get("county_borough"), c.get("state_abbr"))
        want = pins.get(k)
        try:
            have = (float(c["lat"]), float(c["lon"]))
        except (KeyError, TypeError, ValueError):
            have = None
        if want and have and (abs(want[0] - have[0]) > tol or abs(want[1] - have[1]) > tol):
            dropped.append(c.get("name"))
        else:
            keep.append(r)
    if dropped:
        out_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep), encoding="utf-8")
        log(f"pin changed since scoring; will re-score: {', '.join(dropped)}")
    return len(dropped)


def run_score(metro: str, csv_path: Path, out_path: Path, api_base: str) -> int:
    cmd = [sys.executable, str(REPO / "scripts" / "catalog" / "score_metro.py"),
           "--csv", str(csv_path), "--out", str(out_path), "--metro", metro,
           "--skip-baselines", "--skip-overpass-retry"]
    env = {**os.environ, "PYTHONPATH": str(REPO), "HOMEFIT_API_BASE": api_base}
    return subprocess.run(cmd, cwd=str(REPO), env=env).returncode


def git_publish(metro: str, out_path: Path) -> None:
    try:
        rel = str(out_path.relative_to(REPO))
    except ValueError:
        rel = str(out_path)
    subprocess.run(["git", "add", rel], cwd=str(REPO), check=True)
    subprocess.run(["git", "commit", "-m", f"{metro.title()} metro scores (metro_agent run, gate passed)"],
                   cwd=str(REPO), check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=str(REPO), check=True)


def run_pipeline(
    metro: str,
    *,
    api_base: str,
    csv_path: Optional[Path] = None,
    out_path: Optional[Path] = None,
    rounds: int = 3,
    push: bool = False,
    skip_score: bool = False,
    manage_server: bool = True,
    log: Callable[[str], None] = print,
    server_fn: Callable = start_server,
    preflight_fn: Callable = pf.run,
    score_fn: Callable = run_score,
    resolve_fn: Callable = rs.resolve,
    publish_fn: Callable = git_publish,
    failed_fn: Callable = _failed_places,
    validate_fn: Callable = vd.validate,
) -> int:
    csv_path = csv_path or REPO / "data" / f"{metro}_metro_place_catalog.csv"
    out_path = out_path or REPO / "data" / f"{metro}_metro_place_catalog_scores_merged.composites_recomputed.jsonl"
    proc = None
    try:
        def banner(t):
            log(f"\n{'=' * 70}\n  {t}\n{'=' * 70}")

        if manage_server and is_local(api_base):
            banner("0. API")
            proc = server_fn(api_base, log)

        banner("1. PREFLIGHT")
        checks = preflight_fn(metro, csv_path, api_base, None)
        log(pf.format_report(checks))
        if any(c.status == pf.FAIL for c in checks):
            log("\nSTOPPED at preflight. Fix the FAIL lines above and run the same command again.")
            return 2

        if not skip_score:
            banner("2. SCORE (resumable)")
            drop_stale_pins(csv_path, out_path, log)
            for attempt in (1, 2):
                rc = score_fn(metro, csv_path, out_path, api_base)
                bad = failed_fn(out_path)
                if rc != 0:
                    log(f"scoring exited {rc}")
                if bad <= 0 and rc == 0:
                    break
                if attempt == 1:
                    log(f"{bad} places failed outright; running the scorer once more to pick them up")
            if failed_fn(out_path) > 0:
                log("\nSTOPPED: some places still fail to score at all. Check the API logs, then run again.")
                return 3

        banner("3. RESOLVE")
        summary = resolve_fn(out_path, api_base, max_rounds=rounds)
        log(rs.format_summary(summary))
        out_path.with_suffix(".resolution.json").write_text(json.dumps(summary, indent=2))

        banner("4. VALIDATE against independent sources (Census business counts, commuting, peers)")
        try:
            verdicts = validate_fn(dg.load_rows(out_path))
            log(vd.format_report(verdicts))
            n = vd.write_accepted(out_path, verdicts)
            log(f"\n{n} gaps recorded as genuine in {vd.accepted_path(out_path).name}")
        except Exception as e:  # noqa: BLE001 - validation must not take the run down
            log(f"validation skipped: {type(e).__name__}: {str(e)[:100]}")

        banner("5. GATE")
        result = dg.diagnose(dg.load_rows(out_path), accepted=dg.load_accepted(out_path))
        log(dg.format_report(result, out_path.name))
        if result["material_places"]:
            log(f"\nPUBLISH: BLOCKED. {len(result['material_places'])} places have a material gap. "
                "See NEEDS A DATA SOURCE / HUMAN CHECK above; send me that summary to decide.")
            return 1

        log("\nPUBLISH: OK, no material gaps.")
        if push:
            banner("6. PUBLISH")
            publish_fn(metro, out_path)
            log("committed and pushed.")
        else:
            try:
                rel = out_path.relative_to(REPO)
            except ValueError:
                rel = out_path
            log(f"To publish: git add {rel} && git commit -m '{metro.title()} metro scores' && git push origin main"
                "   (or rerun with --push)")
        return 0
    finally:
        if proc is not None:
            proc.terminate()

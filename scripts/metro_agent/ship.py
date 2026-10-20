"""
Ship a finished metro: gate, flip it live in the registry, regenerate the frontend blocks, stage ONLY an allowlist of
files, commit and push.

  PYTHONPATH=. python -m scripts.metro_agent ship --metro phoenix --dry-run     # show what would be staged
  PYTHONPATH=. python -m scripts.metro_agent ship --metro phoenix               # commit and push

Rules it enforces (METRO_RUNBOOK.md): only a HEALTHY or ATTENTION metro ships; the commit holds the metro's own files
plus shared data other metros read (never another metro's scores); anything else in the working tree (analysis files,
other work in progress) is left alone.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable, List, Optional

from . import registry

REPO = registry.REPO

# Shared data files and folders that carry additions for many metros (crime agencies, pins, baselines, school data,
# election data, climate rows). They are data other metros read, never another metro's scores, so they ship with any metro.
SHARED = [
    "data/crime_agency_map.json",
    "data/pin_exceptions.json",
    "data/education_check_exceptions.json",
    "data/status_signal_baselines.json",
    "data/catalog_climate_profiles.jsonl",
    "data/school_snapshot",
    "data/school_geo",
    "data/election",
]


def _git(*args: str, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=str(REPO), capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()[:300]}")
    return r.stdout


def files_for(metro: str) -> List[str]:
    own = [f"data/{metro}_metro_place_catalog.csv",
           f"data/{metro}_metro_place_catalog_scores_merged.composites_recomputed.jsonl"]
    return own + ["data/metro_registry.json"] + [rel for rel, _ in registry.TARGETS] + SHARED


def ship(metro: str, *, dry_run: bool = False, push: bool = True, message: Optional[str] = None,
         gate: Optional[Callable[[str], str]] = None, log: Callable[[str], None] = print) -> int:
    metros = registry.load()
    if metro not in metros:
        log(f"{metro} is not in the registry")
        return 2
    scores = REPO / "data" / f"{metro}_metro_place_catalog_scores_merged.composites_recomputed.jsonl"
    if not scores.is_file():
        log(f"no scores file for {metro}: {scores}")
        return 2

    if gate is None:
        from . import health

        def gate(m: str) -> str:
            return health.audit_all([m], offline=True)[0]["verdict"]
    verdict = gate(metro)
    log(f"health verdict for {metro}: {verdict}")
    if verdict not in ("HEALTHY", "ATTENTION"):
        log("NOT SHIPPING: only a HEALTHY or ATTENTION metro ships. Run `metro_agent health --metro %s` for the problems." % metro)
        return 1

    if _git("diff", "--cached", "--name-only").strip():
        log("NOT SHIPPING: something is already staged. Commit or unstage it first, so this commit holds only this metro.")
        return 1

    was_live = metros[metro].get("status") == "live"
    metros[metro]["status"] = "live"
    changed = registry.generate(metros, write=not dry_run)
    if not dry_run:
        registry.save(metros)
    paths = [p for p in files_for(metro) if (REPO / p).exists()]
    if dry_run:
        log("dry run: would set status live" + (" (already live)" if was_live else "") + "; frontend files regenerated: " + (", ".join(changed) or "none"))
        for p in paths:
            out = _git("status", "--short", "--", p).strip()
            if out:
                log("  would stage: " + out.replace("\n", "\n               "))
        return 0

    _git("add", "--", *paths)
    staged = [l for l in _git("diff", "--cached", "--name-only").splitlines() if l]
    foreign = [p for p in staged if "_metro_place_catalog" in p and not p.startswith(f"data/{metro}_metro_place_catalog")]
    if foreign:
        _git("reset", "-q")
        log(f"ABORTED: another metro's files were about to be committed: {foreign}")
        return 1
    if not staged:
        log("nothing to commit")
        return 0
    msg = message or (f"{registry.load()[metro]['long_label']}: scores for {_place_count(metro)} places, "
                      f"registry status live, frontend generated from the registry")
    msg += "\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
    _git("commit", "-q", "-m", msg)
    log(f"committed {len(staged)} files: " + _git("log", "-1", "--format=%h %s").strip()[:100])
    if push:
        _git("fetch", "-q", "origin")
        out = subprocess.run(["git", "push", "origin", "main"], cwd=str(REPO), capture_output=True, text=True)
        if out.returncode != 0:
            log("PUSH FAILED: " + out.stderr.strip()[-300:])
            return 1
        log("pushed to origin/main: " + _git("log", "-1", "--format=%h").strip())
    return 0


def _place_count(metro: str) -> int:
    p = REPO / "data" / f"{metro}_metro_place_catalog.csv"
    try:
        return max(0, sum(1 for _ in open(p)) - 1)
    except OSError:
        return 0

"""Strict lookups for batch (catalog) scoring.

Live /score keeps returning a best-effort number with a low-confidence flag when an upstream lookup fails, so users never
see a broken page. A published catalog should not: a score built on a failed lookup looks like data. With
HOMEFIT_STRICT_LOOKUPS=true (set by the metro agent for batch scoring) such pillars come back as unknown (score None, weight
redistributed to the place's other pillars by the existing data-gap handling) and stay flagged so they are retried.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional


def strict_enabled() -> bool:
    return os.getenv("HOMEFIT_STRICT_LOOKUPS", "").strip().lower() in ("1", "true", "yes", "on")


def failed_lookup_reason(pillar: str, entry: Dict[str, Any]) -> Optional[str]:
    """Why this pillar's score rests on a failed lookup, or None if it does not."""
    if not isinstance(entry, dict) or entry.get("score") is None:
        return None
    dq = entry.get("data_quality") or {}
    warnings = [str(w) for w in (dq.get("data_warnings") or [])]
    if dq.get("data_warning"):
        warnings.append(str(dq["data_warning"]))
    if pillar == "healthcare_access" and "api_error" in warnings:
        return "healthcare lookup failed"
    if pillar == "active_outdoors":
        op = (entry.get("summary") or {}).get("overpass") or {}
        failed = [q for q in ("local", "regional") if op.get(q) == "overpass_error"]
        if failed:
            return f"Overpass failed on: {', '.join(failed)}"
    return None


def apply_strict_lookup_failures(livability_pillars: Dict[str, Any]) -> None:
    """Blank pillars whose score rests on a failed lookup (no-op unless strict mode is on)."""
    if not strict_enabled():
        return
    for name, entry in livability_pillars.items():
        why = failed_lookup_reason(name, entry)
        if not why:
            continue
        entry["score"] = None
        entry["contribution"] = 0.0
        dq = dict(entry.get("data_quality") or {})
        dq["lookup_failed"] = True
        dq["lookup_failed_reason"] = why
        dq["degraded"] = True
        entry["data_quality"] = dq

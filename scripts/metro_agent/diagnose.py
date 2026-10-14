"""Failure-cause reporting for a scored metro catalog (read-only, no API calls).

Every pillar result is classified into a cause so a run can be triaged without reading
raw JSON.  The pipeline reports many failed lookups as ``status=success`` with a score of 0,
so causes are inferred from the evidence each pillar stores (Overpass outcomes, data-quality
warnings, fallback reasons, data source tags).

Causes
  UPSTREAM_ERROR      a lookup against an external service failed; retrying the pillar can fix it
  SUSPECTED_UPSTREAM  looks like a failed lookup but could be genuine absence; retry, then verify
  NO_DATA_SOURCE      no usable source exists for this place; retrying will not help
  DISABLED            switched off by configuration (e.g. school scoring)
  GENUINE_LOW         measured and low by design (e.g. no businesses within walking range); informational
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

UPSTREAM_ERROR = "UPSTREAM_ERROR"
SUSPECTED_UPSTREAM = "SUSPECTED_UPSTREAM"
NO_DATA_SOURCE = "NO_DATA_SOURCE"
DISABLED = "DISABLED"
GENUINE_LOW = "GENUINE_LOW"

RETRY = "RETRY_PILLAR"
VERIFY = "RETRY_THEN_VERIFY"
SOURCE = "NEEDS_DATA_SOURCE"
NONE = "NONE"

# Share of places hit by the same cause on the same pillar above which the cause is systemic:
# fix the dependency (see `preflight`) before retrying anything.
SYSTEMIC_SHARE = 0.4


@dataclass
class Finding:
    place: str
    pillar: str
    cause: str
    material: bool
    remedy: str
    evidence: str
    severity: int = 1  # how many things failed inside this pillar (used to tell better from worse)


def _pillars(row: Dict[str, Any]) -> Dict[str, Any]:
    return ((row.get("score") or {}).get("livability_pillars")) or {}


def _dq(p: Dict[str, Any]) -> Dict[str, Any]:
    return p.get("data_quality") or {}


def _warnings(p: Dict[str, Any]) -> List[str]:
    dq = _dq(p)
    w = list(dq.get("data_warnings") or [])
    if dq.get("data_warning"):
        w.append(str(dq["data_warning"]))
    return [str(x) for x in w]


def classify_place(row: Dict[str, Any]) -> List[Finding]:
    name = (row.get("catalog") or {}).get("name", "?")
    out: List[Finding] = []

    def add(pillar, cause, material, remedy, evidence, severity=1):
        out.append(Finding(name, pillar, cause, material, remedy, evidence, severity))

    if not row.get("success"):
        add("(place)", UPSTREAM_ERROR, True, RETRY, f"scoring failed: {str(row.get('error'))[:120]}")
        return out

    lp = _pillars(row)

    # Pillars withheld because their lookup failed: unknown on purpose, still on the rescore list.
    withheld = {k for k, v in lp.items() if "withheld_pending_rescore" in _warnings(v)}
    for k in sorted(withheld):
        add(k, UPSTREAM_ERROR, False, RETRY, "withheld pending rescore (shown as unknown until the lookup succeeds)")
    lp = {k: v for k, v in lp.items() if k not in withheld}

    # Active outdoors: records each Overpass query outcome.
    ao = lp.get("active_outdoors")
    if ao is not None:
        op = (ao.get("summary") or {}).get("overpass") or {}
        failed = [q for q in ("local", "trail", "regional") if op.get(q) == "overpass_error"]
        if failed:
            material = any(q in ("local", "regional") for q in failed)
            add("active_outdoors", UPSTREAM_ERROR, material, RETRY,
                f"Overpass failed on: {', '.join(failed)}; score {ao.get('score')}", severity=len(failed))

    # Healthcare: flags api_error when a lookup failed, but still computes a score.
    hc = lp.get("healthcare_access")
    if hc is not None and "api_error" in _warnings(hc):
        add("healthcare_access", UPSTREAM_ERROR, True, RETRY,
            f"lookup failed (completeness {_dq(hc).get('completeness')}); score {hc.get('score')} rests on partial data")
    elif hc is not None and _dq(hc).get("completeness") == 0 and not any(
            (hc.get("summary") or {}).get(k) for k in ("urgent_care_count", "pharmacy_count", "clinic_count", "hospital_count")):
        # Older runs cleared the error flag when a retry came back empty: no clinics, pharmacies or hospitals at all
        # with zero completeness is a failed lookup until Census data says the area really has none (validate).
        add("healthcare_access", SUSPECTED_UPSTREAM, True, VERIFY,
            f"no clinics, pharmacies or hospitals found (completeness 0.0); score {hc.get('score')} rests on the nearest hospital only")

    # Neighborhood amenities: empty result with no diagnostics means the query never produced data.
    na = lp.get("neighborhood_amenities")
    if na is not None and "no_businesses_within_radius" in _warnings(na):
        add("neighborhood_amenities", GENUINE_LOW, False, NONE,
            f"no businesses within walking range; scored {na.get('score')} by design (confidence capped)")
    elif na is not None:
        bd = na.get("breakdown") or {}
        if na.get("score") is None and na.get("status") in ("no_data", "failed", "error"):
            reason = na.get("failure_reason")  # stored by the API once the pillar reports it
            if reason and str(reason).startswith("osm_unavailable"):
                add("neighborhood_amenities", UPSTREAM_ERROR, True, RETRY, f"Overpass business query failed ({reason})")
            elif reason and str(reason).startswith("osm_data_gap"):
                add("neighborhood_amenities", SUSPECTED_UPSTREAM, True, VERIFY,
                    f"Overpass answered but returned no businesses, Places fallback added none ({reason})")
            elif reason == "no_businesses_found":
                add("neighborhood_amenities", NO_DATA_SOURCE, True, SOURCE, "no businesses found in a non-urban area")
            else:
                empty = not bd.get("business_list") and not bd.get("diagnostics")
                add("neighborhood_amenities", SUSPECTED_UPSTREAM if empty else NO_DATA_SOURCE, True,
                    VERIFY if empty else SOURCE,
                    f"no score; status={na.get('status')}, empty result={empty} (old file: no failure_reason stored)")
        elif isinstance(na.get("confidence"), (int, float)) and na["confidence"] < 30:
            add("neighborhood_amenities", SUSPECTED_UPSTREAM, False, RETRY,
                f"very low confidence ({na['confidence']}); score {na.get('score')}")

    # Natural beauty: zero score with no data behind it.
    nb = lp.get("natural_beauty")
    if nb is not None and (nb.get("score") in (0, 0.0, None)) and (nb.get("confidence") in (0, None) or
                                                               _dq(nb).get("quality_tier") == "very_poor"):
        add("natural_beauty", SUSPECTED_UPSTREAM, True, RETRY, f"score {nb.get('score')} with confidence {nb.get('confidence')}")

    # Transit: fallback to commute-time only because Transitland returned nothing.
    pt = lp.get("public_transit_access")
    if pt is not None:
        summ = pt.get("summary") or {}
        if summ.get("fallback_applied") and "Transitland" in str(summ.get("fallback_reason", "")):
            add("public_transit_access", SUSPECTED_UPSTREAM, True, VERIFY,
                "Transitland returned no routes; commute-time-only fallback (may be genuinely no service)")

    # Community safety: a state-level aggregate is deliberately never scored.
    cs = lp.get("community_safety")
    if cs is not None:
        bd = cs.get("breakdown") or {}
        if cs.get("score") is None:
            add("community_safety", NO_DATA_SOURCE, True, SOURCE,
                f"no usable crime data; source={bd.get('source')}, matched agency={bd.get('agency_name')}")

    # Political lean: raw lean value or the flagged 2020 estimate.
    pl = lp.get("political_lean")
    if pl is not None:
        bd = pl.get("breakdown") or {}
        if bd.get("lean_2024") is None:
            add("political_lean", NO_DATA_SOURCE, True, SOURCE, "no precinct data within range")
        elif bd.get("lean_2024_estimated"):
            add("political_lean", NO_DATA_SOURCE, False, NONE, "2024 results not joined; showing 2020 lean")

    # Education: zero because school scoring is switched off.
    qe = lp.get("quality_education")
    if qe is not None and qe.get("status") == "fallback" and "disabled" in str(_dq(qe).get("reason", "")).lower():
        add("quality_education", DISABLED, False, NONE, "school scoring disabled for this run")

    # Anything else that failed outright.
    seen = {f.pillar for f in out}
    for pillar, p in lp.items():
        if pillar in seen or not isinstance(p, dict):
            continue
        if p.get("status") in ("failed", "error") or (p.get("error") and p.get("score") is None):
            add(pillar, UPSTREAM_ERROR, True, RETRY, f"status={p.get('status')} error={str(p.get('error'))[:100]}")
    return out


def load_rows(path: Path) -> List[Dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def load_accepted(scores_path: Path) -> Dict[tuple, str]:
    """Gaps confirmed genuine by `validate` (sidecar <scores>.accepted.json): {(place, pillar): reason}."""
    p = Path(scores_path).with_suffix(".accepted.json")
    if not p.is_file():
        return {}
    try:
        return {(a["place"], a["pillar"]): a.get("reason", "") for a in json.loads(p.read_text())}
    except (ValueError, KeyError, TypeError):
        return {}


def place_labels(rows: List[Dict[str, Any]]) -> List[str]:
    """One label per row: the place name, or 'Name (ST)' when two rows share a name (Ridgewood, NJ vs Ridgewood, Queens)."""
    names = [(r.get("catalog") or {}).get("name", "?") for r in rows]
    counts: Dict[str, int] = {}
    for n in names:
        counts[n] = counts.get(n, 0) + 1
    return [n if counts[n] == 1 else f"{n} ({(r.get('catalog') or {}).get('state_abbr', '?')})"
            for n, r in zip(names, rows)]


def diagnose(rows: Iterable[Dict[str, Any]], accepted: Optional[Dict[tuple, str]] = None) -> Dict[str, Any]:
    rows = list(rows)
    accepted = accepted or {}
    findings: List[Finding] = []
    for r, label in zip(rows, place_labels(rows)):
        for f in classify_place(r):
            f.place = label
            reason = accepted.get((f.place, f.pillar))
            if reason and f.material and f.remedy in (VERIFY, SOURCE):
                f.material, f.remedy = False, NONE
                f.evidence = f"{f.evidence} [accepted: {reason}]"
            findings.append(f)

    n = max(len(rows), 1)
    by_pc: Dict[tuple, List[Finding]] = defaultdict(list)
    for f in findings:
        by_pc[(f.pillar, f.cause)].append(f)
    systemic = [
        {"pillar": p, "cause": c, "places": len(v), "share": round(len(v) / n, 2)}
        for (p, c), v in by_pc.items()
        if c in (UPSTREAM_ERROR, SUSPECTED_UPSTREAM) and len(v) / n >= SYSTEMIC_SHARE
    ]
    material = [f for f in findings if f.material]
    return {
        "places": len(rows),
        "findings": [asdict(f) for f in findings],
        "material_places": sorted({f.place for f in material}),
        "counts": {f"{p}|{c}": len(v) for (p, c), v in sorted(by_pc.items())},
        "systemic": systemic,
        "clean": len(rows) - len({f.place for f in material}),
    }


REMEDY_TEXT = {
    RETRY: "re-run just that pillar for the listed places",
    VERIFY: "re-run once; if still empty, check by hand whether the place genuinely has none",
    SOURCE: "retrying will not help; a data source or a decision is needed",
    NONE: "nothing to do",
}


def format_report(result: Dict[str, Any], title: str = "") -> str:
    lines = [f"METRO DIAGNOSIS {title}".rstrip(), "=" * 70,
             f"{result['places']} places | {result['clean']} with no material gaps | "
             f"{len(result['material_places'])} with at least one"]
    if result["systemic"]:
        lines += ["", "SYSTEMIC (fix the dependency first, then retry; run `preflight`):"]
        for s in result["systemic"]:
            lines.append(f"  {s['pillar']} {s['cause']}: {s['places']} places ({int(s['share'] * 100)}%)")
    groups: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
    for f in result["findings"]:
        if f["material"]:
            groups[(f["remedy"], f["pillar"], f["cause"])].append(f)
    for remedy in (RETRY, VERIFY, SOURCE):
        block = [(k, v) for k, v in groups.items() if k[0] == remedy]
        if not block:
            continue
        lines += ["", f"{remedy}  —  {REMEDY_TEXT[remedy]}"]
        for (_, pillar, cause), fs in sorted(block, key=lambda kv: -len(kv[1])):
            names = ", ".join(f["place"] for f in fs[:8]) + (f" +{len(fs) - 8} more" if len(fs) > 8 else "")
            lines.append(f"  {pillar} [{cause}] {len(fs)}: {names}")
            lines.append(f"      e.g. {fs[0]['place']}: {fs[0]['evidence']}")
    minor = Counter(f"{f['pillar']} [{f['cause']}]" for f in result["findings"] if not f["material"])
    if minor:
        lines += ["", "Minor / informational:"]
        lines += [f"  {k}: {v}" for k, v in minor.most_common()]
    return "\n".join(lines)

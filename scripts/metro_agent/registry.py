"""
Single source of truth for catalog metros: data/metro_registry.json.

Every script and the frontend read metros from here instead of from hand-edited lists. A metro has a status:
  building  scored or being scored, not shown on the site
  live      shown on the site (the only status the generated frontend blocks include)

  PYTHONPATH=. python -m scripts.metro_agent registry generate     # rewrite the generated frontend blocks
  PYTHONPATH=. python -m scripts.metro_agent registry list

Design rules (DESIGN_PRINCIPLES.md): nothing here branches on a city name. A metro is data; the code is the same for all.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO / "data" / "metro_registry.json"
FRONTEND = REPO / "frontend"
BEGIN = "BEGIN GENERATED"
END = "END GENERATED"

STATUSES = ("building", "live")


def load(path: Path = REGISTRY_PATH) -> Dict[str, Dict[str, Any]]:
    """{slug: entry}, in file order."""
    return json.loads(path.read_text())["metros"]


def save(metros: Dict[str, Dict[str, Any]], path: Path = REGISTRY_PATH) -> None:
    doc = {
        "_doc": ("Catalog metros. status 'live' shows the metro on the site; 'building' keeps it off. "
                 "cbsa = {CBSA code: {state FIPS: [county FIPS]}} (Census delineation). inference = fallback rule that "
                 "tags an untagged place with this metro (state, plus counties where a state holds several metros). "
                 "Edit with `metro_agent registry`, then `registry generate`."),
        "metros": metros,
    }
    path.write_text(json.dumps(doc, indent=2) + "\n")


def slugs(statuses: Optional[Tuple[str, ...]] = None, metros: Optional[Dict[str, Dict[str, Any]]] = None) -> List[str]:
    metros = load() if metros is None else metros
    return [s for s, m in metros.items() if statuses is None or m.get("status") in statuses]


def key_of(slug: str) -> str:
    return f"{slug}_metro"


def cbsa_entries(metros: Optional[Dict[str, Dict[str, Any]]] = None) -> Tuple[Dict[str, Dict[str, List[str]]], Dict[str, str]]:
    """(CBSA_COUNTIES additions, CBSA_TO_KEY additions) for the baseline builder."""
    metros = load() if metros is None else metros
    counties: Dict[str, Dict[str, List[str]]] = {}
    keys: Dict[str, str] = {}
    for slug, m in metros.items():
        for code, by_state in (m.get("cbsa") or {}).items():
            counties[code] = by_state
            keys[code] = key_of(slug)
    return counties, keys


def bounds_from_places(csv_path: Path, margin: float = 0.08) -> List[List[float]]:
    import csv

    rows = list(csv.DictReader(open(csv_path)))
    lat = [float(r["lat"]) for r in rows]
    lon = [float(r["lon"]) for r in rows]
    return [[round(min(lon) - margin, 2), round(min(lat) - margin, 2)],
            [round(max(lon) + margin, 2), round(max(lat) + margin, 2)]]


def counties_from_places(csv_path: Path) -> Dict[str, List[str]]:
    """{state: sorted county names} from a place list, used for the county rule of states that hold several metros."""
    import csv

    out: Dict[str, set] = {}
    for r in csv.DictReader(open(csv_path)):
        out.setdefault(r["state_abbr"], set()).add(r["county_borough"])
    return {k: sorted(v) for k, v in out.items()}


# ----------------------------------------------------------------------------------------------
# Frontend generation: rewrite the text between BEGIN/END GENERATED markers. Nothing else in the file is touched.
# ----------------------------------------------------------------------------------------------
def _replace_block(text: str, tag: str, body: str, comment: str) -> str:
    pat = re.compile(rf"([ \t]*){re.escape(comment)} {BEGIN} {re.escape(tag)}[^\n]*\n(?:.*?\n)?[ \t]*{re.escape(comment)} {END} {re.escape(tag)}",
                     re.S)
    m = pat.search(text)
    if not m:
        raise ValueError(f"marker '{BEGIN} {tag}' not found")
    indent = m.group(1)
    new = (f"{indent}{comment} {BEGIN} {tag} (scripts/metro_agent/registry.py; do not edit by hand)\n"
           f"{body.rstrip(chr(10))}\n{indent}{comment} {END} {tag}")
    return text[:m.start()] + new + text[m.end():]


def _ts_str(s: str) -> str:
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def render(metros: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    live = {s: m for s, m in metros.items() if m.get("status") == "live"}
    order = list(live)
    out: Dict[str, str] = {}
    out["list"] = "export const CATALOG_METROS = [" + ", ".join(_ts_str(s) for s in order) + "] as const"
    meta = []
    for s, m in live.items():
        b = m["bounds"]
        meta.append(f"  {s}: {{ label: {_ts_str(m['label'])}, longLabel: {_ts_str(m['long_label'])}, color: {_ts_str(m['color'])}, "
                    f"bounds: [[{b[0][0]}, {b[0][1]}], [{b[1][0]}, {b[1][1]}]] }},")
    out["meta"] = "\n".join(meta)
    out["files"] = "\n".join(f"  'data/{s}_metro_place_catalog_scores_merged.composites_recomputed.jsonl'," for s in order)
    out["server"] = "\n".join(f"  {s}: '{s}_metro_place_catalog_scores_merged.composites_recomputed.jsonl'," for s in order)
    # county / state fallback rules; county rules first so a state that holds several metros resolves by county
    rules = []
    for s, m in live.items():
        inf = m.get("inference") or {}
        if not inf.get("state"):
            continue
        rules.append((0 if inf.get("counties") else 1, s, inf))
    rules.sort(key=lambda r: r[0])
    lines = ["function inferFromRegistry(state: string, county: string): CatalogMetro | null {"]
    for _, s, inf in rules:
        if inf.get("counties"):
            cs = ", ".join(_ts_str(c) for c in inf["counties"])
            lines.append(f"  if (state === {_ts_str(inf['state'])} && [{cs}].includes(county)) return {_ts_str(s)}")
        else:
            lines.append(f"  if (state === {_ts_str(inf['state'])}) return {_ts_str(s)}")
    lines += ["  return null", "}"]
    out["infer"] = "\n".join(lines)
    return out


TARGETS = [
    ("frontend/lib/catalogMetros.ts", [("list", "list", "//"), ("meta", "meta", "//")]),
    ("frontend/next.config.js", [("files", "files", "//")]),
    ("frontend/lib/catalogServer.ts", [("server", "server", "//")]),
    ("frontend/lib/catalogMapTypes.ts", [("infer", "infer", "//")]),
]


def generate(metros: Optional[Dict[str, Dict[str, Any]]] = None, write: bool = True) -> List[str]:
    """Rewrite the generated blocks. Returns the repo-relative files that changed."""
    metros = load() if metros is None else metros
    parts = render(metros)
    changed: List[str] = []
    for rel, blocks in TARGETS:
        p = REPO / rel
        text = p.read_text()
        new = text
        for key, tag, comment in blocks:
            new = _replace_block(new, tag, parts[key], comment)
        if new != text:
            changed.append(rel)
            if write:
                p.write_text(new)
    return changed

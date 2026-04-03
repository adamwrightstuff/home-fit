"""
Neighborhood recommendations: load pre-scored catalog JSONL, prerank, Claude explanations.

Pillar keys match frontend/lib/pillars.ts PillarKey.
"""
from __future__ import annotations

import json
import os
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

# Mirrors frontend/lib/pillars.ts PillarKey (order matches validation set)
PILLAR_KEYS: tuple[str, ...] = (
    "natural_beauty",
    "built_beauty",
    "neighborhood_amenities",
    "active_outdoors",
    "healthcare_access",
    "public_transit_access",
    "air_travel_access",
    "economic_security",
    "quality_education",
    "housing_value",
    "climate_risk",
    "social_fabric",
    "diversity",
)

VALID_PRIORITY_LEVELS = frozenset({"None", "Low", "Medium", "High"})

PRIORITY_TO_NUMERIC = {"None": 0, "Low": 33, "Medium": 66, "High": 100}

REPO_ROOT = Path(__file__).resolve().parent


def _default_catalog_path() -> Path:
    raw = os.getenv("HOMEFIT_AGENT_CATALOG_JSONL", "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else (REPO_ROOT / p)
    return REPO_ROOT / "data" / "nyc_metro_place_catalog_scores_merged.jsonl"


def _pillar_numeric_score(pillar_obj: Any) -> float:
    if not isinstance(pillar_obj, dict):
        return 0.0
    if pillar_obj.get("status") == "failed":
        return 0.0
    if pillar_obj.get("error"):
        return 0.0
    s = pillar_obj.get("score")
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        return float(s)
    return 0.0


def _normalize_catalog_row(line_obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not line_obj.get("success", True):
        return None
    cat = line_obj.get("catalog") or {}
    score = line_obj.get("score") or {}
    search_query = (cat.get("search_query") or "").strip()
    if not search_query:
        name = (cat.get("name") or "").strip()
        state = (cat.get("state_abbr") or "").strip()
        if name and state:
            search_query = f"{name}, {state}"
    if not search_query:
        return None
    liv = score.get("livability_pillars") or {}
    pillar_scores: Dict[str, float] = {}
    for k in PILLAR_KEYS:
        pillar_scores[k] = _pillar_numeric_score(liv.get(k))
    br = score.get("status_signal_breakdown") or {}
    archetype = br.get("archetype")
    if not isinstance(archetype, str):
        archetype = "Typical"
    status_label = br.get("status_label")
    if not isinstance(status_label, str):
        status_label = ""
    return {
        "neighborhood": search_query,
        "search_query": search_query,
        "archetype": archetype,
        "status_label": status_label,
        "pillar_scores": pillar_scores,
        "raw_livability_pillars": liv,
    }


@lru_cache(maxsize=1)
def load_catalog_records() -> tuple[Dict[str, Any], ...]:
    path = _default_catalog_path()
    if not path.is_file():
        raise FileNotFoundError(f"Agent catalog not found: {path}")
    out: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            row = _normalize_catalog_row(obj)
            if row:
                out.append(row)
    return tuple(out)


def priorities_to_numeric(priorities: Dict[str, str]) -> Dict[str, int]:
    return {k: PRIORITY_TO_NUMERIC.get(priorities[k], 0) for k in PILLAR_KEYS}


def prerank_neighborhoods(
    catalog: tuple[Dict[str, Any], ...], priorities: Dict[str, str], top_n: int = 10
) -> List[Dict[str, Any]]:
    numeric = priorities_to_numeric(priorities)
    total_weight = sum(numeric.values()) or 1
    scored: List[Dict[str, Any]] = []
    for n in catalog:
        ps = n["pillar_scores"]
        weighted = sum(numeric.get(pillar, 0) * ps.get(pillar, 0.0) for pillar in PILLAR_KEYS) / total_weight
        payload = {
            "neighborhood": n["neighborhood"],
            "archetype": n["archetype"],
            "percentile_band": n["status_label"],
            "pillar_scores": ps,
            "weighted_match": round(weighted, 2),
        }
        scored.append(payload)
    scored.sort(key=lambda x: x["weighted_match"], reverse=True)
    return scored[:top_n]


def build_results_url(neighborhood_name: str, priorities: Dict[str, str]) -> str:
    """Mirror frontend buildResultsUrl: location + priorities JSON string."""
    params = urlencode(
        {
            "location": neighborhood_name,
            "priorities": json.dumps(priorities),
        }
    )
    return f"/results?{params}"


def _strip_json_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            inner = parts[1]
            if inner.lstrip().startswith("json"):
                inner = re.sub(r"^\s*json\s*", "", inner, count=1, flags=re.IGNORECASE)
            return inner.strip()
    return text


def build_prompt(priorities: Dict[str, str], context: Dict[str, Any], candidates: List[Dict[str, Any]]) -> str:
    return f"""You are a neighborhood matching assistant for HomeFit, a platform that scores neighborhoods across livability pillars.

A user completed a preference quiz. Their pillar priorities (keys are canonical; values are None/Low/Medium/High) are:
{json.dumps(priorities, indent=2)}

Additional context about this user:
{json.dumps(context, indent=2)}

Below are the top candidate neighborhoods pre-ranked by weighted pillar match. Each includes pillar_scores (0–100), archetype, and percentile_band (status signature label from data):
{json.dumps(candidates, indent=2)}

Return ONLY a JSON array of exactly 5 neighborhoods (choose from the candidates; order by best fit). For each object include:
- neighborhood: string (exact "neighborhood" value from the candidate)
- archetype: string (exact value from the candidate)
- percentile_band: string (exact "percentile_band" from the candidate)
- match_score: integer 0–100 representing your assessment of fit given this user's priorities
- top_drivers: array of 2–3 pillar keys from this list only: {list(PILLAR_KEYS)}
- explanation: string, 2–3 sentences in plain language specific to this user's priorities; reference context when relevant

Return only the JSON array. No preamble, no markdown fences, no text outside the JSON."""


def get_recommendations(
    priorities: Dict[str, str],
    context: Dict[str, Any],
    *,
    model: Optional[str] = None,
) -> List[Dict[str, Any]]:
    try:
        import anthropic
    except ImportError as e:
        raise HTTPException(status_code=500, detail="anthropic package not installed") from e

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY is not configured")

    model_id = (model or os.getenv("HOMEFIT_ANTHROPIC_MODEL", "") or "").strip() or "claude-haiku-4-5-20251001"

    catalog = load_catalog_records()
    candidates = prerank_neighborhoods(catalog, priorities, top_n=10)
    if not candidates:
        return []

    prompt = build_prompt(priorities, context, candidates)
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model_id,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text
    raw = _strip_json_fence(raw)

    try:
        results = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail="Model returned malformed JSON") from e

    if not isinstance(results, list):
        raise HTTPException(status_code=500, detail="Model JSON must be an array")

    for r in results:
        if not isinstance(r, dict):
            continue
        name = r.get("neighborhood")
        if isinstance(name, str) and name:
            r["results_url"] = build_results_url(name, priorities)

    return results  # type: ignore[return-value]


class RecommendRequest(BaseModel):
    priorities: Dict[str, str]
    context: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("priorities")
    @classmethod
    def validate_priorities(cls, v: Dict[str, str]) -> Dict[str, str]:
        for key in PILLAR_KEYS:
            if key not in v:
                raise ValueError(f"Missing pillar key: {key}")
            if v[key] not in VALID_PRIORITY_LEVELS:
                raise ValueError(f"Invalid priority level for {key}: {v[key]}")
        extra = set(v.keys()) - set(PILLAR_KEYS)
        if extra:
            raise ValueError(f"Unknown pillar keys: {sorted(extra)}")
        return v


router = APIRouter(tags=["agent"])


@router.post("/agent/recommend")
def recommend_neighborhoods(req: RecommendRequest) -> Dict[str, Any]:
    start = time.perf_counter()
    model = (os.getenv("HOMEFIT_ANTHROPIC_MODEL", "") or "").strip() or "claude-haiku-4-5-20251001"
    try:
        results = get_recommendations(req.priorities, req.context)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    catalog = load_catalog_records()
    processing_ms = round((time.perf_counter() - start) * 1000)
    return {
        "recommendations": results,
        "meta": {
            "model": model,
            "neighborhoods_evaluated": len(catalog),
            "processing_ms": processing_ms,
        },
    }

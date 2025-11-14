"""
Shared helpers and constants for beauty-related pillars.
"""

from typing import Dict, Optional, Tuple

# Normalization parameters carried over from legacy neighborhood beauty pillar.
AREA_NORMALIZATION: Dict[str, Dict[str, float]] = {
    "historic_urban": {"shift": 12.0, "scale": 0.96, "max": 95.0},
    "suburban": {"shift": 7.5, "scale": 1.0, "max": 94.0},
    "urban_residential": {"shift": -6.0, "scale": 0.92, "max": 88.0},
    "urban_core": {"shift": 1.5, "scale": 1.0, "max": 94.0},
    "exurban": {"shift": 12.5, "scale": 1.02, "max": 95.0},
    "rural": {"shift": 13.0, "scale": 1.04, "max": 95.0},
    "urban_core_lowrise": {"shift": 4.0, "scale": 0.98, "max": 90.0},
}

# Enhancer caps used by both beauty sub-pillars.
BUILT_ENHANCER_CAP = 8.0
NATURAL_ENHANCER_CAP = 18.0
BEAUTY_BONUS_CAP = BUILT_ENHANCER_CAP + NATURAL_ENHANCER_CAP


def normalize_beauty_score(score: float, area_type: Optional[str]) -> Tuple[float, Optional[Dict[str, float]]]:
    """
    Apply area-type-specific normalization to a raw 0-100 beauty score.
    """
    if not area_type:
        return max(0.0, min(100.0, score)), None

    params = AREA_NORMALIZATION.get(area_type.lower())
    if not params:
        return max(0.0, min(100.0, score)), None

    scaled = score * params.get("scale", 1.0)
    shifted = scaled + params.get("shift", 0.0)
    capped = min(params.get("max", 100.0), shifted)
    return max(0.0, capped), params


def parse_beauty_weights(weights_str: Optional[str]) -> Dict[str, float]:
    """
    Parse a custom weight string (e.g., "trees:0.5,architecture:0.5") into a normalized dict.
    """
    default = {"trees": 0.5, "architecture": 0.5}
    if weights_str is None:
        return default

    try:
        weights: Dict[str, float] = {}
        total = 0.0

        for pair in weights_str.split(","):
            component, weight = pair.split(":")
            component = component.strip()
            if component not in {"trees", "architecture"}:
                continue
            value = float(weight.strip())
            weights[component] = value
            total += value

        if total <= 0.0:
            return default

        return {component: value / total for component, value in weights.items()}
    except Exception:
        return default


def default_beauty_weights(area_type: Optional[str]) -> str:
    """
    Return the default tree vs architecture weight string for a given area type.
    """
    if not area_type:
        return "trees:0.5,architecture:0.5"

    area_type = area_type.lower()
    if area_type in {"urban_core", "urban_residential", "urban_core_lowrise"}:
        return "trees:0.4,architecture:0.6"
    if area_type in {"historic_urban", "suburban"}:
        return "trees:0.35,architecture:0.65"
    if area_type == "exurban":
        return "trees:0.4,architecture:0.6"
    if area_type == "rural":
        return "trees:0.5,architecture:0.5"
    return "trees:0.5,architecture:0.5"


"""A no-data pillar's weight is redistributed in the total whether it is stored with contribution 0.0 or None."""
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def recompute():
    # Load composite_indices without the heavy package __init__ imports, as the catalog scripts do.
    for name, d in (("pillars", ROOT / "pillars"), ("data_sources", ROOT / "data_sources")):
        if name not in sys.modules:
            pkg = types.ModuleType(name)
            pkg.__path__ = [str(d)]
            pkg.__package__ = name
            sys.modules[name] = pkg
    from pillars.composite_indices import recompute_composites_from_payload
    return recompute_composites_from_payload


def _payload(gap_contribution):
    pillars = {
        "a": {"score": 80.0, "weight": 25.0, "contribution": 20.0},
        "b": {"score": 60.0, "weight": 25.0, "contribution": 15.0},
        "c": {"score": None, "weight": 25.0, "contribution": gap_contribution, "status": "no_data"},
        "d": {"score": 40.0, "weight": 25.0, "contribution": 10.0},
    }
    return {"livability_pillars": pillars, "location_info": {}, "coordinates": {}}


@pytest.mark.parametrize("stored", [0.0, None])
def test_gap_weight_is_redistributed(recompute, stored):
    out = recompute(_payload(stored))
    assert out["total_score"] == pytest.approx(60.0)  # (20 + 15 + 10) / (1 - 0.25)
    assert out["data_gaps"]["pillars"] == ["c"]


def test_no_gap_leaves_the_total_alone(recompute):
    p = _payload(None)
    p["livability_pillars"]["c"].update({"score": 50.0, "contribution": 12.5})
    assert recompute(p)["total_score"] == pytest.approx(57.5)

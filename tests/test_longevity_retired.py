"""The longevity index was retired 2026-11-08 (docs/LONGEVITY_INDEX_SPEC.md). Guard against it coming back by accident."""
from pillars import composite_indices
from pillars.composite_indices import INDICES_VERSION_METADATA, recompute_composites_from_payload


def test_no_longevity_in_composite_module():
    assert not hasattr(composite_indices, "compute_longevity_index")
    assert not hasattr(composite_indices, "LONGEVITY_INDEX_WEIGHTS")
    assert "longevity" not in INDICES_VERSION_METADATA


def test_recompute_does_not_emit_longevity_fields():
    out = recompute_composites_from_payload({"livability_pillars": {}, "location_info": {}, "coordinates": {}})
    assert not any("longevity" in k for k in out)

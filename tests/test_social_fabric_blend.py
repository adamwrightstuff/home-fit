"""Social fabric blend is fail-loud: missing components are left out and weights scale proportionally."""
import pytest

from pillars.social_fabric_blend import SF_BASE_WEIGHTS, blend_social_fabric


def test_all_present_uses_base_weights():
    score, w, missing = blend_social_fabric(participation=50.0, cohesion=60.0, rootedness=70.0, civic=80.0)
    assert missing == [] and w == SF_BASE_WEIGHTS
    assert score == round(0.60 * 50 + 0.20 * 60 + 0.10 * 70 + 0.10 * 80, 1)


def test_missing_cohesion_scales_the_rest_proportionally():
    score, w, missing = blend_social_fabric(participation=50.0, cohesion=None, rootedness=70.0, civic=80.0)
    assert missing == ["cohesion"] and abs(sum(w.values()) - 1.0) < 1e-12
    assert abs(w["participation"] - 0.75) < 1e-12 and abs(w["rootedness"] - 0.125) < 1e-12
    assert score == round(0.75 * 50 + 0.125 * 70 + 0.125 * 80, 1)


def test_missing_stability_is_not_scored_as_zero():
    with_zero = 0.60 * 50 + 0.20 * 60 + 0.10 * 0 + 0.10 * 80
    score, _, missing = blend_social_fabric(participation=50.0, cohesion=60.0, rootedness=None, civic=80.0)
    assert missing == ["rootedness"] and score > round(with_zero, 1)


def test_no_score_without_participation_or_with_one_component():
    with pytest.raises(RuntimeError):
        blend_social_fabric(participation=None, cohesion=60.0, rootedness=70.0, civic=80.0)
    with pytest.raises(RuntimeError):
        blend_social_fabric(participation=50.0, cohesion=None, rootedness=None, civic=None)


def test_participation_blend_has_no_invented_fallback():
    from data_sources.community_participation import blend_participation
    assert blend_participation(40.0, 60.0) == (50.0, "full")
    assert blend_participation(None, 60.0) == (60.0, "vol_only")
    assert blend_participation(40.0, None) == (40.0, "bmf_only")
    assert blend_participation(None, None) == (None, "none")  # the retired code returned 50.0 here


def test_irs_state_coverage_follows_the_loaded_files(monkeypatch):
    from data_sources import irs_bmf
    refined = {f"17{i:09d}": 1 for i in range(5)}                        # IL: only 5 tracts, not covered
    refined.update({f"06{i:09d}": 1 for i in range(40)})                 # CA: 40 tracts, covered
    monkeypatch.setattr(irs_bmf, "org_count_by_tract", refined)
    monkeypatch.setattr(irs_bmf, "org_count_by_tract_legacy", {})
    assert irs_bmf.state_has_coverage("06") and not irs_bmf.state_has_coverage("17") and not irs_bmf.state_has_coverage(None)
    # a covered state gets a rate; an uncovered one gets no data instead of a rate of zero
    tract = {"geoid": "17" + "000000001", "state_fips": "17"}
    assert irs_bmf.get_civic_orgs_per_1k(41.0, -87.0, tract=tract, population=4000) is None

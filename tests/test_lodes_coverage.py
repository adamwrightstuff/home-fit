"""LODES commuter lookup: outside the built states the answer is unavailable (None), not zero."""
import pytest

from data_sources import lodes_h8_commuter_context as lc

h3 = pytest.importorskip("h3")
AUSTIN = (30.2672, -97.7431)


@pytest.fixture
def grid(monkeypatch):
    center = h3.latlng_to_cell(*AUSTIN, 8)
    index = {str(c): {"workplace_jobs": 5000.0, "rac_c000": 2000.0} for c in h3.grid_disk(center, 12)}  # a covered patch
    monkeypatch.setattr(lc, "_ensure_table", lambda: None)
    monkeypatch.setattr(lc, "_H8_INDEX", index)
    monkeypatch.setattr(lc, "built_states", lambda: {"TX", "NY"})
    return index


def test_point_in_a_covered_area_gets_numbers(grid):
    jobs, workers = lc.jobs_in_disk(*AUSTIN, 800, state="TX")
    assert jobs > 0 and workers > 0


def test_empty_disk_inside_the_grid_is_a_real_zero(grid):
    assert lc.jobs_in_disk(AUSTIN[0] + 0.12, AUSTIN[1], 300) == (0.0, 0.0)  # about 13 km out, still ringed by indexed cells


def test_point_far_from_any_cell_is_unavailable(grid):
    assert lc.jobs_in_disk(41.88, -87.63, 800) is None  # Chicago: nothing indexed around it


def test_state_missing_from_the_built_list_is_unavailable_even_with_cells_in_the_disk(grid):
    assert lc.jobs_in_disk(*AUSTIN, 800, state="PA") is None  # across-the-border cells must not stand in for a missing state
    assert lc.jobs_in_disk(*AUSTIN, 800, state="tx") is not None


def test_missing_sidecar_falls_back_to_the_density_check(grid, monkeypatch):
    monkeypatch.setattr(lc, "built_states", lambda: None)
    assert lc.jobs_in_disk(*AUSTIN, 800, state="PA") is not None

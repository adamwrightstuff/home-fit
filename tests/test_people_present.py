"""Offline tests for the people-present denominator (residents + workers for work hours)."""

from __future__ import annotations

from unittest import mock

import pytest

from data_sources import people_present as pp


def test_people_present_adds_workers_for_work_week_share():
    assert pp.people_present(40_000, 47_000, 21_500) == pytest.approx(40_000 + (45 / 168) * 25_500)


def test_people_present_never_below_residents():
    # bedroom community: more residents leave for work than workers arrive
    assert pp.people_present(60_000, 33_000, 30_000 + 10_000) == 60_000


def _geo(layer, lat, lon):
    return {28: {"GEOID": "0617568", "NAME": "Culver City city"}, 82: {"GEOID": "06037", "NAME": "Los Angeles County"}}.get(layer, {})


def _counts(level, state, county=""):
    return {"place": {"0617568": (40_357, 46_946, 21_523)}, "county": {"06037": (9_936_690, 4_300_000, 4_600_000)}}[level]


def test_municipal_multiplier_uses_the_town():
    with mock.patch.object(pp, "_geography_at", side_effect=_geo), \
         mock.patch.object(pp, "_acs_worker_counts", side_effect=_counts):
        mult, meta = pp.people_present_multiplier(34.02, -118.39, "municipal")
    assert mult == pytest.approx(1 + (45 / 168) * (46_946 - 21_523) / 40_357)
    assert meta["geography"] == "Culver City city"


def test_county_agency_uses_the_county():
    with mock.patch.object(pp, "_geography_at", side_effect=_geo), \
         mock.patch.object(pp, "_acs_worker_counts", side_effect=_counts):
        mult, meta = pp.people_present_multiplier(33.98, -118.44, "county")
    assert mult == 1.0 and meta["geography"] == "Los Angeles County"


def test_missing_geography_leaves_residents_only():
    with mock.patch.object(pp, "_geography_at", return_value={}):
        mult, meta = pp.people_present_multiplier(40.0, -100.0, "municipal")
    assert mult == 1.0 and meta["skip_reason"] == "geography_or_counts_unavailable"

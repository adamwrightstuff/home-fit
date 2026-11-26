"""Local scene v2: culture and hangout mix facts and the ladder level (docs/LOCAL_SCENE_LADDER_DPV2.md)."""

import unittest

from pillars import local_scene_v2 as ls


def v(t, d=100.0, brand=None):
    return {"type": t, "distance_m": d, "brand": brand}


class TestFacts(unittest.TestCase):
    def test_counts_and_shares(self):
        venues = [v("gallery"), v("bookstore"), v("records"), v("cafe", 300), v("bar", 500), v("restaurant"), v("theater")]
        f = ls.place_facts(venues, 1200)
        self.assertEqual((f["venues_total"], f["culture_venues"], f["hangouts_5min"]), (7, 3, 1))
        self.assertEqual(f["culture_share"], round(100 * 3 / 7, 1))
        self.assertEqual(f["hangout_share"], round(100 * 6 / 7, 1))  # restaurant is the only non-hangout

    def test_branded_culture_venues_and_theaters_are_not_culture(self):
        f = ls.place_facts([v("bookstore", brand="Barnes & Noble"), v("theater"), v("gallery")], 1200)
        self.assertEqual(f["culture_venues"], 1)

    def test_radius_and_unknown_types_are_ignored(self):
        f = ls.place_facts([v("gallery", 1300), v("grocery"), v("cafe", 1100)], 1200)
        self.assertEqual(f["venues_total"], 1)

    def test_no_venues_gives_no_shares_not_zero(self):
        f = ls.place_facts([], 1200)
        self.assertIsNone(f["culture_share"])
        self.assertIsNone(f["hangout_share"])
        self.assertTrue(f["few_venues"])

    def test_few_venues_flag_uses_the_minimum(self):
        self.assertTrue(ls.place_facts([v("cafe")] * 14, 1200)["few_venues"])
        self.assertFalse(ls.place_facts([v("cafe")] * 15, 1200)["few_venues"])


class TestReading(unittest.TestCase):
    def facts(self, shares):
        out = []
        for cshare, hshare, venues in shares:
            out.append({"culture_share": cshare, "hangout_share": hshare, "few_venues": venues < ls.MIN_VENUES})
        return out

    def test_combined_ranks_within_the_group_and_missing_shares_give_none(self):
        data = [(i * 1.0, i * 1.0, 100) for i in range(1, 21)]
        f = self.facts(data)
        ls.apply_reading(f)
        self.assertEqual(f[19]["combined"], max(x["combined"] for x in f))
        self.assertEqual(f[0]["combined"], min(x["combined"] for x in f))

    def test_places_without_data_have_no_combined(self):
        f = [{"culture_share": None, "hangout_share": None, "few_venues": True}, {"culture_share": 5.0, "hangout_share": 40.0, "few_venues": False}]
        ls.apply_reading(f)
        self.assertIsNone(f[0]["combined"])


class TestDensityBands(unittest.TestCase):
    def test_bands_split_by_density_and_none_stays_none(self):
        b = ls.density_bands([1.0, 2.0, 3.0, 4.0, 5.0, None], n_bands=5)
        self.assertEqual(b[:5], [0, 1, 2, 3, 4])
        self.assertIsNone(b[5])

    def test_places_are_ranked_only_against_their_density_band(self):
        # ten places, two per density band; the stronger place in every pair gets the same reading whatever the absolute shares
        f = []
        for k in range(10):
            strong = k % 2 == 1
            base = (k // 2) * 10.0  # absolute shares rise with density, so a global ranking would differ
            f.append({"culture_share": base + (5.0 if strong else 1.0), "hangout_share": base + (50.0 if strong else 10.0), "few_venues": False})
        ls.apply_reading(f, [float(k + 1) for k in range(10)])
        for k in range(0, 10, 2):
            self.assertEqual(f[k]["combined"], 25.0)
            self.assertEqual(f[k + 1]["combined"], 75.0)
            self.assertEqual(f[k]["density_band"], f[k + 1]["density_band"])


class TestBuckets(unittest.TestCase):
    def test_place_with_no_density_gets_no_reading_instead_of_a_tiny_peer_group(self):
        f = [{"culture_share": 5.0, "hangout_share": 40.0, "few_venues": False} for _ in range(4)]
        f.append({"culture_share": 9.0, "hangout_share": 60.0, "few_venues": False})
        ls.apply_reading(f, [1.0, 2.0, 3.0, 4.0, None])
        self.assertIsNone(f[4]["combined"])


class TestActivity(unittest.TestCase):
    def test_count_is_independent_venues_inside_the_radius(self):
        vs = [v("cafe", 100), v("bar", 1201), v("restaurant", 500, "Chipotle"), v("gallery", 1200)]
        self.assertEqual(ls.independent_venue_count(vs), 2)



class TestLevels(unittest.TestCase):
    def facts(self, total, n, combined):
        return {"venues_total": total, "independent_venues_1200m": n, "combined": combined}

    def test_no_data_is_none_never_quiet(self):
        self.assertIsNone(ls.scene_level(self.facts(0, 0, None)))
        self.assertIsNone(ls.scene_level(self.facts(None, None, None)))
        self.assertIsNone(ls.scene_level(self.facts(40, None, 80.0)))  # no venue read at the pin

    def test_floor_is_the_measured_area_venue_count(self):
        self.assertEqual(ls.scene_level(self.facts(14, 90, 99.0)), "quiet")  # thin base never outranks, whatever the mix
        self.assertEqual(ls.scene_level(self.facts(15, 3, 99.0)), "lively")  # a town whose main street is off the pin keeps its level

    def test_mix_cut_splits_low_key_from_lively(self):
        self.assertEqual(ls.scene_level(self.facts(40, 20, 54.9)), "low_key")
        self.assertEqual(ls.scene_level(self.facts(40, 20, 55.0)), "lively")

    def test_large_place_with_an_average_mix_is_lively_not_flat(self):
        self.assertEqual(ls.scene_level(self.facts(200, 71, 49.9)), "low_key")
        self.assertEqual(ls.scene_level(self.facts(200, 71, 50.0)), "lively")
        self.assertEqual(ls.scene_level(self.facts(200, 71, 54.9)), "lively")
        self.assertEqual(ls.scene_level(self.facts(200, 71, 55.0)), "buzzing")
        self.assertEqual(ls.scene_level(self.facts(40, 70, 52.0)), "low_key")  # a small place needs the strong mix

    def test_a_dense_place_near_the_mix_cut_moves_one_level_at_a_time(self):
        order = {"quiet": 0, "low_key": 1, "lively": 2, "buzzing": 3}
        levels = [ls.scene_level(self.facts(300, 150, m)) for m in range(30, 80)]
        self.assertTrue(all(abs(order[a] - order[b]) <= 1 for a, b in zip(levels, levels[1:])))

    def test_top_volume_makes_buzzing(self):
        self.assertEqual(ls.scene_level(self.facts(200, 70, 80.0)), "lively")
        self.assertEqual(ls.scene_level(self.facts(200, 71, 80.0)), "buzzing")
        self.assertEqual(ls.scene_level(self.facts(700, 600, 38.0)), "low_key")  # busy but restaurant-heavy

    def test_no_density_figure_is_low_key_not_a_guess(self):
        self.assertEqual(ls.scene_level(self.facts(60, 40, None)), "low_key")


class TestBoundary(unittest.TestCase):
    def test_boundary_facts_count_every_venue_given_and_have_no_pin_fields(self):
        venues = [v("gallery"), v("cafe"), v("bar"), v("restaurant"), v("bookstore", brand="Barnes & Noble")]
        f = ls.boundary_facts(venues, 4.2)
        self.assertEqual((f["venues_total"], f["culture_venues"], f["cafes_bars_in_town"]), (5, 1, 2))
        self.assertEqual(f["geography"], "town_boundary")
        self.assertIsNone(f["hangouts_5min"])
        self.assertIsNone(f["radius_m"])
        self.assertEqual(f["area_km2"], 4.2)

    def test_towns_and_neighborhoods_are_ranked_only_against_their_own_kind(self):
        f = []
        for k in range(4):
            f.append({"culture_share": float(k), "hangout_share": float(k), "few_venues": False, "geography": "town_boundary"})
        for k in range(4):
            f.append({"culture_share": 50.0 + k, "hangout_share": 50.0 + k, "few_venues": False, "geography": "pin_circle"})
        ls.apply_reading(f)  # no densities: one band, so only the geography splits the groups
        self.assertEqual([x["combined"] for x in f[:4]], [x["combined"] for x in f[4:]])
        self.assertEqual([x["combined"] for x in f[:4]], [12.5, 37.5, 62.5, 87.5])


class TestOvertureHybrid(unittest.TestCase):
    """Overture volume with an OSM mix (owner decision 2026-11-13, docs/LOCAL_SCENE_LADDER_DPV2.md section 7)."""

    def test_blend_weight_ramps_from_the_floor_to_the_buzzing_cut(self):
        self.assertEqual(ls.blend_weight(0), 0.0)
        self.assertEqual(ls.blend_weight(ls.OVERTURE_MIN_VENUES), 0.0)
        self.assertEqual(ls.blend_weight(ls.OVERTURE_TOP_VOLUME_FROM), 1.0)
        self.assertEqual(ls.blend_weight(10_000), 1.0)
        mid = (ls.OVERTURE_MIN_VENUES + ls.OVERTURE_TOP_VOLUME_FROM) / 2
        self.assertAlmostEqual(ls.blend_weight(mid), 0.5)
        self.assertEqual(ls.blend_weight(None), 0.0)

    def test_hybrid_mix_blends_and_missing_stays_missing(self):
        self.assertEqual(ls.hybrid_mix(40.0, 80.0, 0.0), 40.0)
        self.assertEqual(ls.hybrid_mix(40.0, 80.0, 1.0), 80.0)
        self.assertEqual(ls.hybrid_mix(40.0, 80.0, 0.25), 50.0)
        self.assertIsNone(ls.hybrid_mix(None, 80.0, 0.5))
        self.assertIsNone(ls.hybrid_mix(40.0, None, 0.5))

    def test_overture_floor_is_the_overture_venue_count(self):
        thin = {"venues_total": ls.OVERTURE_MIN_VENUES - 1, "independent_venues_1200m": 5}
        self.assertEqual(ls.hybrid_level(thin, 90.0), "quiet")  # too few venues: Limited data, whatever the mix
        enough = {"venues_total": ls.OVERTURE_MIN_VENUES, "independent_venues_1200m": 5}
        self.assertEqual(ls.hybrid_level(enough, 90.0), "lively")
        self.assertEqual(ls.hybrid_level(enough, 10.0), "low_key")

    def test_buzzing_needs_the_overture_volume_cut(self):
        below = {"venues_total": 200, "independent_venues_1200m": ls.OVERTURE_TOP_VOLUME_FROM - 1}
        at = {"venues_total": 200, "independent_venues_1200m": ls.OVERTURE_TOP_VOLUME_FROM}
        self.assertEqual(ls.hybrid_level(below, 80.0), "lively")
        self.assertEqual(ls.hybrid_level(at, 80.0), "buzzing")
        self.assertEqual(ls.hybrid_level(at, 52.0), "lively")  # large place, average mix
        self.assertIsNone(ls.hybrid_level({"venues_total": 0, "independent_venues_1200m": 0}, 80.0))

    def test_osm_level_function_is_unchanged(self):
        self.assertEqual(ls.scene_level({"venues_total": 14, "independent_venues_1200m": 14, "combined": 90.0}), "quiet")
        self.assertEqual(ls.scene_level({"venues_total": 80, "independent_venues_1200m": 71, "combined": 60.0}), "buzzing")

    def test_restaurant_free_reading_ignores_the_restaurant_count(self):
        # same hangout and culture venues, one place has 100 extra restaurants: the restaurant-free reading must not move
        base = {"venues_total": 20, "culture_venues": 2, "hangout_share": 50.0, "geography": "pin_circle"}
        padded = {"venues_total": 120, "culture_venues": 2, "hangout_share": round(100 * 10 / 120, 1), "geography": "pin_circle"}
        other = {"venues_total": 30, "culture_venues": 0, "hangout_share": 20.0, "geography": "pin_circle"}
        filler = {"venues_total": 0, "culture_venues": 0, "hangout_share": None, "geography": "pin_circle"}
        for first in (base, padded):
            # ten places so the two under test share the lowest density band
            f = [dict(first), dict(other)] + [dict(filler) for _ in range(8)]
            ls.apply_restaurant_free_reading(f, [2.0] * 10, [float(k) for k in range(1, 11)])
            self.assertGreater(f[0]["combined_new"], f[1]["combined_new"])
        self.assertEqual(ls.hangout_count(base), 10)
        self.assertEqual(ls.hangout_count(padded), 10)

    def test_restaurant_free_reading_needs_area_and_density(self):
        f = [{"venues_total": 10, "culture_venues": 1, "hangout_share": 50.0, "geography": "pin_circle"}]
        ls.apply_restaurant_free_reading(f, [None], [5.0])
        self.assertIsNone(f[0]["combined_new"])
        ls.apply_restaurant_free_reading(f, [2.0], [None])
        self.assertIsNone(f[0]["combined_new"])


class TestOvertureFacts(unittest.TestCase):
    def setUp(self):
        from scripts.catalog import add_local_scene_overture_facts as ov
        self.ov = ov

    def test_category_mapping(self):
        t = self.ov.venue_type
        self.assertEqual(t("coffee_shop", "coffee_shop"), "cafe")
        self.assertEqual(t("wine_bar", "bar"), "bar")
        self.assertEqual(t("italian_restaurant", "restaurant"), "restaurant")
        self.assertEqual(t("art_gallery", "art_gallery"), "gallery")
        self.assertEqual(t("record_store", "shopping"), "records")
        self.assertEqual(t("movie_theater", "movie_theater"), "theater")
        self.assertIsNone(t("bakery", "casual_eatery"))
        self.assertIsNone(t("fast_food_restaurant", "fast_food_restaurant"))

    def test_registry_only_and_low_confidence_rows_are_dropped(self):
        k = self.ov.keep_row
        self.assertTrue(k(0.9, ["meta", "Overture"]))
        self.assertTrue(k(None, ["Foursquare", "Overture-signals"]))
        self.assertFalse(k(0.4, ["meta", "Overture"]))
        self.assertFalse(k(0.9, ["BrightQuery", "Overture"]))
        self.assertTrue(k(0.9, ["BrightQuery", "meta", "Overture"]))  # registry plus a real source is kept


if __name__ == "__main__":
    unittest.main()

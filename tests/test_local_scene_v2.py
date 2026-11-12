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


if __name__ == "__main__":
    unittest.main()

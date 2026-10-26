from data_sources.places_fallback_client import _places_grocery_shop
from pillars import neighborhood_amenities as na


def _biz(kind, shop, d, source=None):
    return {"type": kind, "shop": shop, "distance_m": d, "source": source}


def test_convenience_store_does_not_earn_grocery_credit():
    only_conv = [_biz("grocery", "convenience", 100)]
    assert na._score_essentials_proximity(only_conv) == 0.0


def test_supermarket_earns_full_grocery_credit():
    assert na._score_essentials_proximity([_biz("grocery", "supermarket", 100)]) == round(0.45 * 25, 2)


def test_stored_places_record_without_subtype_still_counts():
    assert na._score_essentials_proximity([_biz("grocery", None, 100, "google_places")]) > 0


def test_convenience_store_still_counts_toward_density_and_variety():
    biz = [_biz("grocery", "convenience", 100)]
    assert na._score_walkable_density(biz) > 0
    assert na._score_walkable_variety(biz, [], [], []) > 0


def test_places_grocery_subtype():
    assert _places_grocery_shop(["convenience_store", "store"]) == "convenience"
    assert _places_grocery_shop(["supermarket", "grocery_store"]) == "supermarket"
    assert _places_grocery_shop(["grocery_store"]) == "supermarket"


def test_pin_sensitivity_reports_a_range():
    biz = [dict(_biz("cafe", None, 300), lat=30.0, lon=-97.0), dict(_biz("grocery", "supermarket", 900), lat=30.01, lon=-97.0)]
    ps = na._pin_sensitivity(biz, 30.0, -97.0, "suburban", False, 800)
    assert ps["shift_m"] == 200 and ps["range"] >= 0 and ps["min"] <= ps["max"]
    assert na._pin_sensitivity([], 30.0, -97.0, "suburban", False, 800)["range"] is None


def test_proximity_decays_linearly_from_400_to_1200_m():
    cafe = lambda d: [_biz("cafe", None, d)]
    full = na._score_essentials_proximity(cafe(400))
    assert full == round(0.30 * 25, 2)
    assert na._score_essentials_proximity(cafe(1200)) == 0.0
    assert na._score_essentials_proximity(cafe(1500)) == 0.0
    assert na._score_essentials_proximity(cafe(800)) == round(full / 2, 2)
    assert na._score_essentials_proximity(cafe(401)) < full

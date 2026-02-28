"""
Quick spot-check script for the Layout & Street Network pillar.

Run with:
    python -m analysis.layout_network_spotcheck
"""

from typing import List, Tuple

from pillars.layout_network import get_layout_network_score


def _print_result(name: str, lat: float, lon: float) -> None:
    score, details = get_layout_network_score(lat, lon)
    print(f"\n{name}")
    print("-" * len(name))
    print(f"Score: {score:.1f}")
    comps = (
        details.get("connectivity_score", 0.0),
        details.get("route_character_score", details.get("hierarchy_score", 0.0)),
        details.get("barrier_impact_penalty", details.get("barriers_penalty", 0.0)),
        details.get("comfort_safety_score", details.get("infra_bonus", 0.0)),
    )
    print(
        f"Components  connectivity={comps[0]:.1f}  route_character={comps[1]:.1f}  "
        f"barrier_impact_penalty={comps[2]:.1f}  comfort_safety={comps[3]:.1f}"
    )
    metrics = details.get("metrics", {})
    print(
        "Intersection density/km²="
        f"{metrics.get('intersection_density_per_sqkm', 0.0):.1f}, "
        "median_block_length_m="
        f"{metrics.get('median_block_length_m', 0.0):.1f}, "
        "culdesac_ratio="
        f"{metrics.get('culdesac_ratio', 0.0):.2f}"
    )


def main() -> None:
    # A small set of manually curated locations for sanity checks.
    test_points: List[Tuple[str, float, float]] = [
        ("Dense urban grid (Manhattan)", 40.7484, -73.9857),
        ("Traditional European fabric (Barcelona Eixample)", 41.3890, 2.1650),
        ("Typical US suburb (Plano, TX)", 33.0557, -96.7956),
        ("Rural village (Vermont)", 44.5588, -72.5778),
    ]

    for name, lat, lon in test_points:
        _print_result(name, lat, lon)


if __name__ == "__main__":
    main()


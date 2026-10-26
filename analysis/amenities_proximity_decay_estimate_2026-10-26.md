# Estimate: linear proximity decay (400 m full credit, 1,200 m zero)

Offline, from stored business lists. Not applied to the catalog. Code and tests are committed; the catalog recompute waits for approval.

Rule: essentials proximity credit is 1.0 within 400 m, 0.0 at 1,200 m or beyond, linear between (previous: steps at 150/300/500/800 m). Judgment anchored on Walk Score's 5-minute full-credit point; the curve and the 1,200 m end are not published. 1,200 m is the smallest query radius, so every place sees the same reach. Grocery rule (supermarkets only) unchanged.

Result on the 1,426 scored places (amenities score, new minus stored):
- mean +2.47, median absolute change 2.40, p95 5.70, max 7.5
- 139 places rise by more than 5 points; none falls by more than 0.1; 207 are unchanged
- total score: mean +0.19, range -0.01 to +0.58 (amenities weight about 7.7%)
- by area type: suburban +2.8, exurban +2.3, urban residential +2.0, rural +1.8
- by metro: Miami +3.1 to Seattle +1.8
- largest rises (about +7): Hialeah, Spring Branch, El Sereno, Fox Chase, Eastover, Gastonia

Sensitivity to the choice (mean change, proximity-only): linear 400 to 1,200 +2.5; exponential 400 to 2,400 +2.9; linear 400 to 2,400 +4.2.

Caveat: places whose nearest cafe, grocery or restaurant sits beyond the stored list radius are treated as having none, same as before.

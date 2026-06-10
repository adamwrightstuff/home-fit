# Tribeca, NY — Status Signal Test Results

**Run:** Status Signal pillars only (housing_value, social_fabric, economic_security, neighborhood_amenities).  
**Baselines:** `data/status_signal_baselines.json` (includes `nyc_metro` CBSA).

---

## Summary

| Metric | Value |
|--------|--------|
| **Total livability score** (requested pillars only) | **45.22** |
| **Status Signal** (0–100) | **73.0** |

---

## Status Signal formula

Weights (from `pillars/status_signal.py`): **Wealth 35%** + **Home cost 25%** + **Education 20%** + **Occupation 10%** + **Luxury presence 5%**.  
`wealth_character` is a label only (super_zip | unequal | typical), not weighted.

---

## Component breakdown (0–100 each)

| Component | Weight | Score | Contribution (approx.) |
|-----------|--------|-------|-------------------------|
| **Wealth** | 35% | **84.8** | ~31.2 |
| **Home cost** | 25% | **100.0** | ~26.3 |
| **Education** | 20% | 40.5 | ~8.5 |
| **Occupation** | 10% | 66.1 | ~7.0 |
| **Luxury presence** | 5% | 0.0 | 0.0 |
| **Wealth character** | (label) | **unequal** | — |

**Status Signal (weighted sum):** 73.0

---

## Interpretation

- **Wealth (84.8):** High household income and/or home values relative to the **nyc_metro** baseline (min–max from Tribeca, Scarsdale, Greenwich, NYC boroughs, etc.), so the metro’s upper range is now reflected.
- **Home cost (100.0):** Tribeca’s median home value is at or above the metro baseline max, so the home-cost component is capped at 100 (top of the scale).
- **Education (40.5):** Moderate vs. baseline (e.g. bachelor’s+/grad %); not a major driver.
- **Occupation (66.1):** Above average white‑collar / professional share.
- **Luxury presence (0.0):** No status-signal brands (e.g. Equinox, Soho House, Erewhon) matched in the neighborhood-amenities business list for this run.
- **Wealth character: unequal:** Mean household income is notably above median (wealth gap &gt; ~0.25), so the label is “unequal” rather than “super_zip” (widespread affluence) or “typical.”

The **nyc_metro** baseline is pulling Tribeca’s wealth and home-cost scores from the same metro pool as other NYC-area locations, so the 73.0 Status Signal reflects Tribeca’s position within that metro band.

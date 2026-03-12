# Place Results — Show Details Spec

When a user taps **Show details** on a pillar card on the Place Results screen, the expanded panel follows this spec. Same rules apply for all 12 pillars.

---

## Global Rules

- **Scores as %:** All component scores are shown as a **percentage** (e.g. 58%), not as "X/Y". Do not expose denominators (e.g. 35/60). Counts and distances stay as-is (e.g. "12 parks", "2.3 km").
- **Confidence & Data Quality on card only:** The pillar card already shows Confidence and Data Quality. Do **not** repeat them in the details panel. In details, show **one short degraded line** only when `data_quality.degraded` is true (e.g. "Limited data: some sources were unavailable.").
- **Qualitative labels when possible:** Use tier labels (e.g. "Stable" / "Moderate" / "High turnover", "Rich" / "Moderate" / "Sparse", "Very close" / "Short walk" / "Further", "Low" / "Medium" / "High") instead of raw numbers where that’s clearer.
- **No pillar-score repeat:** Do not include a row that only restates the pillar score. Every row is either (a) a **component** that feeds into the formula (shown as % or tier), or (b) a **driver** (count, distance, qualitative tier).

---

## 1. Natural Beauty

**Top line:** "Natural scenery based on topography/views, water, greenery, and land cover."

| # | Label | Source | Format |
|---|--------|--------|--------|
| 1 | Topography & views | Component score(s) | **%** (0–100 → %) |
| 2 | Water access | Water component | **%** |
| 3 | Tree canopy | Canopy component or % | "X% within 1 km" (keep as %) |
| 4 | Natural land cover | Forest/wetland/shrub/grass | **Qualitative:** "Rich" / "Moderate" / "Sparse" |
| 5 | Scenery preference | `natural_beauty_preference` | Text: "Weighted for: Mountains, Ocean, …" |

**Degraded only:** "Limited data: some natural data sources were unavailable."

---

## 2. Active Outdoors

**Top line:** "Access to parks, trails, and water for an active lifestyle."

| # | Label | Source | Format |
|---|--------|--------|--------|
| 1 | Local parks & playgrounds | `breakdown.local_parks_playgrounds` (max 40) | **%** |
| 2 | Trail access | `breakdown.trail_access` (max 30) | **%** |
| 3 | Water access | `breakdown.water_access` (max 20) | **%** |
| 4 | Camping access | `breakdown.camping_access` (max 10) | **%** |
| 5 | Summary | `summary` | Counts: "N parks, N trails, N water features, N camping" (if present) |

**Degraded only:** "Limited data: some outdoor data sources were unavailable."

---

## 3. Neighborhood Amenities (Daily Amenities)

**Top line:** "Walkable access to daily needs, social spots, and services."

| # | Label | Source | Format |
|---|--------|--------|--------|
| 1 | Home walkability | `breakdown.home_walkability.score` (max 60) | **%** |
| 2 | Daily needs nearby | `diagnostics.businesses_within_walkable` or `businesses_within_1km` | Count: "N businesses within ~10–15 min" |
| 3 | Mix of places | `diagnostics.tier1_count`–`tier4_count` | Counts or **qualitative:** "Good mix" / "Limited variety" |
| 4 | Distance to daily needs | `diagnostics.median_distance_m` | **Qualitative:** "Very close (≤3 min walk)" / "Short walk (3–6 min)" / "Moderate walk (6–10 min)" / "Further (10+ min)" |
| 5 | Town center & vibrancy | `breakdown.location_quality` (max 40) | **%** |
| 6 | Local vs chains | Chain logic | Text: "Score focuses on independent/local businesses." or "Score includes both chains and local places." |

**Degraded only:** "Limited data: OSM coverage is sparse here; this score may undercount amenities."

---

## 4. Built Beauty

**Top line:** "Street and building design, diversity, and human scale."

| # | Label | Source | Format |
|---|--------|--------|--------|
| 1 | Architecture diversity | Component | **%** or **qualitative:** "High" / "Moderate" / "Low" |
| 2 | Street character | Streetwall/setback/facade | **Qualitative:** "Strong" / "Moderate" / "Limited" |
| 3 | Building mix | Types / footprint variety | Count or **qualitative** tier |
| 4 | Character preference | `built_character_preference` / density | Text: "Weighted for: Historic / Contemporary / …" |

Do **not** add a row that is only "Design score" or "Built beauty score" (same as pillar score).

**Degraded only:** "Limited data: some built environment data were unavailable."

---

## 5. Healthcare Access

**Top line:** "Access to hospitals, urgent care, clinics, and pharmacies."

| # | Label | Source | Format |
|---|--------|--------|--------|
| 1 | Hospital access | `breakdown.hospital_access` (max 35) | **%** |
| 2 | Primary care | `breakdown.primary_care` (max 25) | **%** |
| 3 | Specialized care | `breakdown.specialized_care` (max 15) | **%** |
| 4 | Emergency services | `breakdown.emergency_services` (max 10) | **%** |
| 5 | Pharmacies | `breakdown.pharmacies` (max 15) | **%** |
| 6 | Counts | `summary` | "N hospitals, N clinics, N pharmacies" |

**Degraded only:** "Limited data: some healthcare data sources were unavailable."

---

## 6. Public Transit Access

**Top line:** "Access to rail and key transit within walking distance."

| # | Label | Source | Format |
|---|--------|--------|--------|
| 1 | Heavy rail | `breakdown.heavy_rail` | **%** (if score) or **qualitative** tier |
| 2 | Light rail | `breakdown.light_rail` | **%** or **qualitative** |
| 3 | Bus | `breakdown.bus` | **%** or **qualitative** |
| 4 | Nearest heavy rail | `summary.nearest_heavy_rail_distance_km` | "X km" or **qualitative:** "Under 10 min walk" / "10–20 min walk" / "Further" |
| 5 | Connectivity / commute | `summary.heavy_rail_connectivity_tier`, `mean_commute_minutes` | **Qualitative** tier + "Mean commute: X min" (if present) |

**Degraded only:** "Limited data: some transit data sources were unavailable."

---

## 7. Air Travel Access

**Top line:** "Access to major airports from this location."

| # | Label | Source | Format |
|---|--------|--------|--------|
| 1 | Nearest airport | `summary` (name + distance) | "Name, X km" |
| 2 | Airport count | `summary.airport_count` | "N airports within range" |
| 3 | Drive time band | If available | **Qualitative:** "Under 1 hr" / "1–2 hr" / "2+ hr" |

**Degraded only:** "Limited data: airport data unavailable."

---

## 8. Economic Security

**Top line:** "Local job market strength for your focus (or general economic health)."

| # | Label | Source | Format |
|---|--------|--------|--------|
| 1 | Job market fit | Score when `job_categories` set | **%** or **qualitative:** "Strong" / "Moderate" / "Limited" |
| 2 | Area | `summary.division`, `area_bucket` | Label (e.g. metro, bucket) |
| 3 | Job focus | Request params | Text: "Focused on: [categories]" or "General local economy" |

Do **not** add a row that is only the overall economic/pillar score.

**Degraded only:** "Limited data: some economic data were unavailable."

---

## 9. Quality Education

**Top line:** "Quality and availability of nearby schools (when enabled)."

| # | Label | Source | Format |
|---|--------|--------|--------|
| 1 | Average school rating | `breakdown` or summary | **%** (if 0–100) or qualitative "Above average" / "Average" / "Below average" |
| 2 | Schools rated | Counts by level | "N elementary, N middle, N high" |
| 3 | Excellent schools | Count of top-tier | "N excellent schools" |
| 4 | School scoring | — | If disabled: "School scoring is off for this run." |

**Degraded only:** "Limited data: school data unavailable or scoring disabled."

---

## 10. Housing Value

**Top line:** "How far your money goes on housing here."

| # | Label | Source | Format |
|---|--------|--------|--------|
| 1 | Local affordability | `breakdown.local_affordability` (max 50) | **%** |
| 2 | Space | `breakdown.space` (max 30) | **%** |
| 3 | Value efficiency | `breakdown.value_efficiency` (max 20) | **%** |
| 4 | Median home value | `summary.median_value` (if exposed) | "$X" |
| 5 | Price-to-income | From summary (if present) | "X× local income" |

**Degraded only:** "Limited data: some housing or income data were unavailable."

---

## 11. Climate & Flood Risk

**Top line:** "Exposure to flooding, heat, and air quality."

| # | Label | Source | Format |
|---|--------|--------|--------|
| 1 | Flood risk | Component | **Qualitative:** "Low" / "Medium" / "High" |
| 2 | Heat risk | Component | **Qualitative** tier or "X extreme-heat days" |
| 3 | Air quality | Component | **Qualitative** tier |
| 4 | Overall risk | Only if it’s a distinct composite; if it equals pillar score, **omit** | **Qualitative:** "Low" / "Medium" / "High" |

**Degraded only:** "Limited data: some climate/flood data were unavailable."

---

## 12. Social Fabric

**Top line:** "Community stability and civic places to connect."

| # | Label | Source | Format |
|---|--------|--------|--------|
| 1 | Residential stability | Summary/breakdown | **Qualitative:** "Stable" / "Moderate" / "High turnover" |
| 2 | Civic & third places | Count (libraries, community centers, town halls) | "N civic places nearby" |
| 3 | Community strength | If present | **Qualitative:** "Strong" / "Moderate" / "Fragile" |

Do **not** add a row for "Social fabric score" (that’s the pillar score on the card).

**Degraded only:** "Limited data: some community data were unavailable."

---

## Summary Checklist (All Pillars)

- [ ] Component scores → **%**; no X/Y or denominators.
- [ ] Counts and distances → unchanged (counts, km, "X min").
- [ ] Qualitative metrics → use **tiers/labels** (Stable/Moderate/High turnover, Rich/Moderate/Sparse, Low/Medium/High, Very close/Short walk/Further, etc.).
- [ ] Confidence & Data Quality → **only on the card**; in details, **one degraded line** when `data_quality.degraded` is true.
- [ ] **No row** that only repeats the pillar score (drop "Social fabric score", "Overall climate risk" if same as pillar, "Design score" if same as pillar, etc.).

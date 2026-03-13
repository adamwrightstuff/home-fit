# HomeFit QA & Performance Report

> **Location tested:** Carroll Gardens, Brooklyn  
> **App URL:** http://localhost:3000  
> **Started:** 2026-03-13T02:30:46.281Z  
> **Completed:** 2026-03-13T02:33:15.072Z  
> **Total duration:** 148.79s

---

## 📊 Summary

| | Count |
|---|---|
| Phases passed | **8 / 8** |
| Phases failed | **0** |
| Console errors | **1** |
| Network failures | **2** |
| Bugs flagged | **0** |
| Warnings | **8** |

---

## 🔄 Phase Results

### ✅ Phase: Initial Page Load

- **Status:** passed (1.12s)
- **Summary:** Loaded http://localhost:3000 in 0.96s

**Notes:**
- DOM interactive: 178ms
- Page fully loaded: 376ms

📸 Screenshot: `homefit-01-home.png`

---

### ✅ Phase: Search: "Carroll Gardens, Brooklyn"

- **Status:** passed (1.44s)
- **Summary:** Search submitted (autocomplete: true)

**Notes:**
- Found search input via: [data-testid="location-search-input"]
- Typed "Carroll Gardens, Brooklyn"
- Autocomplete appeared with: "Carroll Gardens, New York, 11231"
- Clicked first autocomplete suggestion

📸 Screenshot: `homefit-02-search.png`

---

### ✅ Phase: Results Page Load

- **Status:** passed (90.17s)
- **Summary:** Results/scoring UI confirmed

**Notes:**
- Results or scoring UI appeared in 90.01s
- Current URL: http://localhost:3000/
- Visible pillar-related cards found: 24

📸 Screenshot: `homefit-03-results.png`

---

### ✅ Phase: Adjust Pillar Weights

- **Status:** passed (30.18s)
- **Summary:** Attempted weight changes on 5 pillars

**Notes:**
- ⚠ No weight control found for "Natural Beauty" — skipping
- ⚠ No weight control found for "Schools" — skipping
- ⚠ No weight control found for "Active Outdoors" — skipping
- ⚠ No weight control found for "Daily Amenities" — skipping
- ⚠ No weight control found for "Climate" — skipping

📸 Screenshot: `homefit-04-weights.png`

---

### ✅ Phase: Run Score

- **Status:** passed (4.16s)
- **Summary:** Scores updated in 3.18s

**Notes:**
- Selected 4 pillar(s) via "Add" buttons
- Clicked Run Score button
- ⚠ No loading indicator detected — consider adding one for UX feedback
- Score run completed in 3.18s
- Captured score values: Run Score (1)

📸 Screenshot: `homefit-05-scored.png`

---

### ✅ Phase: Save Place

- **Status:** passed (20.46s)
- **Summary:** Save action completed (confirmed: false)

**Notes:**
- Clicked Save Place button
- ⚠ No save confirmation toast/alert detected — verify save feedback UX
- ⚠ Save button did not visually toggle — check saved state styling

📸 Screenshot: `homefit-06-saved.png`

---

### ✅ Phase: UX & Accessibility Spot-checks

- **Status:** passed (0.16s)
- **Summary:** Spot-checks complete

**Notes:**
- All images have alt text ✓
- All buttons have accessible labels ✓
- Document fonts status: loaded

📸 Screenshot: `homefit-07-a11y.png`

---

### ✅ Phase: API Timing Summary

- **Status:** passed (0.00s)
- **Summary:** API timing collected

**Notes:**
- 3 API call(s) captured



---

## 🌐 Page Load Performance

| Metric | Value |
|---|---|
| DOM Interactive | 178ms |
| DOMContentLoaded | 179ms |
| Load Event End | 376ms |
| Transfer Size | 3.5 KB |

| Key Timing | Value |
|---|---|
| Search → Autocomplete | 1.31s |
| Search → Results Page | 90.01s |
| Score Run Duration | 3.18s |

---

## ⚖️ Pillar Weight Changes

| Pillar | Target Value | Status | Via |
|---|---|---|---|
| Natural Beauty | — | no_control_found | — |
| Schools | — | no_control_found | — |
| Active Outdoors | — | no_control_found | — |
| Daily Amenities | — | no_control_found | — |
| Climate | — | no_control_found | — |

---

## 🔌 API Call Performance

| Endpoint | Method | Status | Duration |
|---|---|---|---|
| `/api/geocode?location=Carroll%20Gardens%2C%20New%20York%2C%2011231` | GET | 200 | 119ms  |
| `/api/score?location=Carroll+Gardens%2C+New+York%2C+11231&priorities=%7B%22active_outdoors%22%3A%22None%22%2C%22built_beauty%22%3A%22None%22%2C%22natural_beauty%22%3A%22None%22%2C%22neighborhood_amenities%22%3A%22Medium%22%2C%22air_travel_access%22%3A%22None%22%2C%22public_transit_access%22%3A%22None%22%2C%22healthcare_access%22%3A%22None%22%2C%22economic_security%22%3A%22Medium%22%2C%22quality_education%22%3A%22Medium%22%2C%22housing_value%22%3A%22None%22%2C%22climate_risk%22%3A%22Medium%22%2C%22social_fabric%22%3A%22None%22%7D&only=quality_education%2Cneighborhood_amenities%2Ceconomic_security%2Cclimate_risk&include_chains=false&enable_schools=false` | GET | 202 | 99ms  |
| `/api/score?job_id=950e1c297d604b77b47b8dbc9f7ddeec` | GET | 200 | 20ms  |

---

## 🐛 Bugs

_No bugs flagged._

---

## ⚠️ Warnings

- [Adjust Pillar Weights] No weight control found for "Natural Beauty" — skipping
- [Adjust Pillar Weights] No weight control found for "Schools" — skipping
- [Adjust Pillar Weights] No weight control found for "Active Outdoors" — skipping
- [Adjust Pillar Weights] No weight control found for "Daily Amenities" — skipping
- [Adjust Pillar Weights] No weight control found for "Climate" — skipping
- [Run Score] No loading indicator detected — consider adding one for UX feedback
- [Save Place] No save confirmation toast/alert detected — verify save feedback UX
- [Save Place] Save button did not visually toggle — check saved state styling

---

## 🖥️ Console Errors

- `2026-03-13T02:30:47.863Z` — Failed to load resource: the server responded with a status of 404 (Not Found)

---

## 📡 Network Failures

- `https://tile.openstreetmap.org/13/2412/3081.png` — net::ERR_ABORTED
- `https://tile.openstreetmap.org/13/2410/3080.png` — net::ERR_ABORTED

---

## 💡 Recommendations

1. Fix 1 console error(s) before launch
2. Investigate 2 network failure(s)
3. Add a visible save confirmation (toast/snackbar) after saving a place
4. Consider adding data-testid attributes to key elements for more reliable selector targeting
5. Run Lighthouse audit for Core Web Vitals (LCP, CLS, FID) against the Results page

---

## 🎬 Artifacts

Screenshots and a session video were saved to the directory where this script was run.

---

_Generated by homefit-agent.js · 3/12/2026, 10:33:15 PM_

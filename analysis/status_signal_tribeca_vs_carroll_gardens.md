# Status Signal: Why Carroll Gardens Can Score Higher Than Tribeca

## Status Signal formula

Status Signal is a **post-pillars composite** (0–100) built from four inputs, with **division-specific baselines** (NY → `middle_atlantic`) used to normalize wealth, education, and occupation:

| Component  | Weight | Source | Baselines (middle_atlantic for NY) |
|-----------|--------|--------|-------------------------------------|
| **Wealth**   | 25% | housing_value (mean/median HH income) | mean_hh_income [21,631 – 190,769], wealth_gap_ratio [0 – 0.455] |
| **Education**| 20% | social_fabric (education_attainment, self_employed_pct) | grad_pct [0–85], bach_pct [30–3206], self_employed_pct [0–77.05] |
| **Occupation** | 20% | economic_security (industry_shares) + tract white_collar + social_fabric self_employed | *Uses "all" (middle_atlantic.occupation is {}):* finance_arts [5–25], white_collar [25–65], self_employed [0–123.55] |
| **Brand**   | 35% | neighborhood_amenities business_list | No baselines: 4 categories (luxury gym, design perfumery, organic supermarket, boutique fitness); 0/0.5/1 per category → 0–100 |

- **Wealth** = 0.6 × (mean income normalized) + 0.4 × (wealth gap normalized).  
- **Education** = 0.5×grad + 0.3×bach + 0.2×self_employed (all normalized).  
- **Occupation** = 0.5×finance_arts + 0.3×white_collar + 0.2×self_employed (normalized).  
- **Brand** = presence of status brands (Equinox, Whole Foods, Trader Joe's, SoulCycle, etc.) in the amenities business list; 2+ matches per category = full 25%, 1 = 12.5%, 0 = 0%.

---

## Why Carroll Gardens can score higher than Tribeca

### 1. **Brand (35% weight) — most likely driver**

- Brand is the **largest weight** and is driven by the **business list** returned by the **neighborhood_amenities** pillar (radius/POI search).
- Tribeca’s list may include more high-end or non-retail uses (offices, galleries, finance) that are **not** in the status-brand set (luxury gym, perfumery, organic supermarket, boutique fitness). So Tribeca can have **fewer** name-matched status brands in the list.
- Carroll Gardens often has more **retail/amenity** density (Whole Foods, Trader Joe's, yoga/Pilates, etc.) that **do** match the config. So Carroll Gardens can get a **higher brand score** (e.g. 50–100) while Tribeca gets a lower one (e.g. 0–50), which alone can swing the overall Status Signal by many points.

### 2. **Wealth (25%) — ceiling and gap**

- Both neighborhoods have high incomes. **Middle Atlantic** wealth baselines cap at mean_hh_income **190,769** and wealth_gap_ratio **0.455**.
- If Tribeca’s **mean income is above 190,769**, the income component is **capped at 100**; the same component for Carroll Gardens (lower but still high) can also be near 100. So wealth may be **similar** or **slightly higher for Tribeca**; it’s unlikely to explain Carroll Gardens being higher overall.
- If Tribeca has **very high inequality** (mean >> median), wealth_gap can hit the cap; Carroll Gardens’ more moderate gap can still score high. Net: wealth is unlikely to favor Carroll Gardens unless there’s a data or tract-boundary quirk.

### 3. **Education (20%)**

- Both are highly educated. **Middle Atlantic** education uses grad_pct [0–85], bach_pct [30–3206], self_employed_pct [0–77.05].
- If Tribeca’s tract has **higher** grad_pct/bach_pct, it will score **higher** on education. So education is more likely to favor **Tribeca**, not Carroll Gardens—unless the **tract** used for Carroll Gardens has higher attainment or the Tribeca tract is drawn in a way that dilutes education (e.g. mixed commercial/residential).

### 4. **Occupation (20%)**

- **Occupation** uses **"all"** baselines in NY because `middle_atlantic.occupation` is `{}`. It combines finance+arts %, white_collar % (tract), and self_employed %.
- Tribeca is finance-heavy, so **finance_arts** can be at or above the “all” max (25%), i.e. **capped at 100**.
- Carroll Gardens can have high white_collar and self_employed; both can be near 100. So occupation could be **similar** or **slightly higher for Tribeca**. Again, not the main reason Carroll Gardens would lead.

---

## Summary

- **Most likely reason Carroll Gardens scores higher:** **Brand (35%)** — more status-brand matches (Whole Foods, Trader Joe's, boutique fitness, etc.) in the neighborhood_amenities business list for Carroll Gardens than for Tribeca, where the list may be more office/finance/gallery-heavy and less aligned with the configured retail/fitness brands.
- Wealth, education, and occupation use **middle_atlantic** (or “all” for occupation) and tend to **cap or favor Tribeca**; they are unlikely to explain a higher Carroll Gardens score unless tract boundaries or data differ in a specific way.

To **confirm** for your two points (Tribeca 40.7154, -74.0093 and Carroll Gardens 40.678420, -73.994802), run the comparison script with the API up:

```bash
PYTHONPATH=. python3 scripts/debug/compare_status_signal.py "Tribeca, NY 40.7154, -74.0093" "Carroll Gardens, Brooklyn NY 40.678420, -73.994802"
```

That prints the Status Signal and the four pillar scores (wealth, education, occupation, brand) side-by-side plus raw inputs (income, grad %, business count), so you can see exactly which pillar drives the difference.

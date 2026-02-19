# Economic Security Pillar — Data & Metrics Reference

## Does this pillar use Median Gross Rent? Why?

**No.** The pillar does not use median gross rent.

- The base pillar score has no earnings-to-rent or earnings_vs_cost component.
- **Job category overlays** are density-only (occupation/industry share and WFH share); they do not use rent or earnings-to-rent.
- **Historical:** The pillar and overlays previously used earnings-to-rent; those components have been removed.

---

## What is anchored balance scoring?

**Anchored balance** is a single number in **[-1, +1]** that summarizes how much of the local job base is “anchored” (stable) vs “cyclical” (sensitive to recessions).

- **Formula:** `(anchored_share - cyclical_share) / 100`
- **Anchored** = Education & health (DP03_0042PE) + Public administration (DP03_0045PE).
- **Cyclical** = Construction (DP03_0034PE) + Manufacturing (DP03_0035PE) + Leisure & hospitality (DP03_0043PE).

**Interpretation:** Higher score → more jobs in health, education, and government; fewer in construction, manufacturing, and hospitality. That is associated with more stable employment over the business cycle. The pillar normalizes this to 0–100 and uses it in the **resilience and diversification** sub-index (40% weight, with industry diversity HHI at 60%).

---

## How are growing vs declining industries used?

**They are not used.** The pillar currently uses:

- **Industry *levels* (shares):** DP03 industry percentages → **industry HHI** (diversity) and **anchored vs cyclical balance** (stability).
- **Business dynamism:** **Net establishment entry per 1k residents** from Census **BDS** (establishment entry minus exit), not employment or industry growth.

So we have **no** metric for “growing vs declining industries” (e.g. employment growth by sector). Adding one would require a new data source (e.g. BLS QCEW or ACS employment change over time).

---

## Possible additions

### 1. Job growth rate (not just establishment entry)

- **Current:** We use **net establishment entry per 1k** (BDS) — business churn, not job count growth.
- **Job growth:** Employment level change over time (e.g. 1-year or 5-year % change in jobs).
  - **ACS:** Possible by comparing employment (e.g. DP03) across two ACS vintages at the same geography; 1-year ACS only for larger areas.
  - **BLS QCEW:** Better fit — county and MSA employment and year-over-year % change. Would require adding a BLS API (or file) integration and aligning geography (CBSA/county).
- **Verdict:** **Can add**; most robust approach is BLS QCEW for employment growth; ACS comparison is a lighter alternative.

### 2. Wage distribution by percentile (not just median)

- **Current:** Only **median** worker earnings (DP03_0092E) → job-category overlays (and summary); no earnings-to-rent in the pillar score.
- **Distribution:** Would capture inequality and spread (e.g. P80/P20 ratio, or quintile shares).
  - **ACS:** Household income distribution — e.g. **B19081** (mean income by quintile), **B19082** (shares), **B19083** (Gini). For *earnings* (workers), tables like **B20002** (earnings distribution) exist; need to confirm availability at CBSA/county.
- **Verdict:** **Can add** once we choose a metric (e.g. earnings ratio or quintile share) and confirm ACS table/geography support. Then add to pillar and to `economic_baselines.json` build.

### 3. Underemployment rate

- **Current:** Only **unemployment rate** (DP03_0009PE) in the job market sub-index.
- **Underemployment:** Typically “U-6” style — unemployed + part-time for economic reasons + marginally attached. Better signal of labor slack.
  - **BLS CPS:** U-6 is from the Current Population Survey; published at national/state level, not CBSA/county.
  - **ACS:** Has employment status and hours; no direct “part-time for economic reasons” variable. Can approximate with part-time share or similar, but not true U-6.
- **Verdict:** **Possible but limited.** True U-6 at CBSA/county usually requires modeling or a different source. We could add an ACS-based proxy (e.g. part-time share) as a partial underemployment signal if we document the limitation.

---

## Summary

| Topic | Answer |
|-------|--------|
| Median gross rent | Fetched for job-category overlays only; not in base pillar score. |
| Anchored balance | (anchored − cyclical) / 100 from industry shares; higher = more stable job mix. |
| Growing vs declining industries | Not used; only level shares (HHI, anchored balance) and BDS metrics. |
| Business dynamism | Two metrics (50% each): **net establishment entry per 1k** (churn) and **total establishments per 1k** (scale/depth). Both from Census BDS; population from ACS B01001. |
| Job growth rate | Can add; best via BLS QCEW; ACS year-over-year comparison is an option. |
| Wage percentiles | Can add; ACS has income/earnings distribution tables (e.g. B19081, B20002). |
| Underemployment | Can add only as an ACS-based proxy; true U-6 at area level is not standard in ACS. |

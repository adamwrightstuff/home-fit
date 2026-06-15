# Pillar Deep-Dive: Economic Security

How `pillars/economic_security.py` scores a location today.

## What it measures — and what it deliberately does NOT
Economic security = **the job-market opportunity a place's residents can reach** — plus the
**quality** of that market. It is deliberately NOT:
- the metro a place is administratively filed under (commute-sheds cross CBSA lines), nor
- the current residents' outcomes (income/poverty). *Living in Harlem doesn't block your
  access to Manhattan's jobs.* Resident affluence is a **status_signal** concern, not this one.

The litmus test that settled the design: "does living in Harlem block your economic security?"
No — so the pillar must reward Harlem's excellent job access, not penalize its residents'
circumstances. (Full reasoning in the economic-security-design memory.)

## Two terms
```
economic_security = 0.55 · job_access  +  0.45 · market_quality
```
(falls back to `market_quality` alone where the LODES grid has no coverage)

### Term 1 — job_access (reachable market, the fix)
`data_sources/job_accessibility.py` — a gravity model over the LODES H8 workplace-job grid:
```
access(lat,lon) = Σ_hex  workplace_jobs(hex) · exp(−dist_km / 20)   over hexes < 75 km
score = logscale(access) → 0–100        (LOG_LO=2.5, LOG_HI=6.6)
```
- Near a big job center → high; isolated town → low; **anchored to the *reachable* market,
  not the administrative one.**
- Validated: Harlem 99, Midtown 100, Scarsdale 91, **Greenwich 88 (anchors to NYC, not its
  Bridgeport-Stamford CBSA)**, exurban Palmdale 72, isolated Montauk 46.
- This single term does all the *legitimate* differentiation: metro vs isolated, and
  within-metro proximity to jobs. It does NOT use resident outcomes.

### Term 2 — market_quality (existing components)
The pre-existing CBSA labor-market score: Density / Mobility / Ecosystem / Resilience built
from ACS + QCEW/OEWS (employment ratio, wages, establishment churn, industry diversity),
normalized within (Census Division × area-type bucket). Captures how *good* the reachable
market is (wages, growth, diversity), not its size.

## Why the blend, and why uniformity is correct
Before this, the pillar was market_quality alone at CBSA level → **47% of NYC places shared
71.5, 83% of LA shared 58.8**, and Greenwich scored 46 (Bridgeport's market, not NYC's).

Adding job_access:
- Fixes wrong-CBSA anchoring (Greenwich 46 → 69; same for Cos Cob, Old Greenwich, Norwalk).
- Restores differentiation (NYC 8 → 78 distinct values, LA 4 → 51).
- **Keeps metro neighbors similar on purpose.** Harlem ≈ Scarsdale ≈ Compton on economic
  security because they share the same reachable market — that's *correct*. The difference
  between Compton and Beverly Hills is resident outcomes, which belong in status_signal. A
  tight within-metro spread (esp. LA, a single sprawling market) is honest, not a bug.

## Coverage & data
- LODES parquet `data/lodes_h8_commuter.parquet` (force-committed; H3 res-8). Covers
  **NY / NJ / CT / CA**. Outside that, `job_access` is `None` and the pillar uses
  market_quality only (e.g. a Chicago address). Rebuild for new metros:
  `scripts/baselines/build_lodes_h8_commuter.py --states ...` then force-add.

## Live vs catalog
- Live: `get_economic_security_score` computes market_quality fresh, fetches job_access from
  the parquet, blends, and exposes `job_access_score` + `market_quality_score` in the summary.
- Catalog: blended offline by `scripts/apply_econ_job_access.py` (0.55·job_access + 0.45·
  *stored* market_quality). Because the stored market_quality is older than a live recompute,
  catalog and live can differ a few points (Greenwich catalog 69 vs live 72.7) — ordinary
  staleness, same blend formula. See LIVE_SCORER_VS_EXPLORER.

## Known residual
The market_quality half is still CBSA-anchored, so Greenwich's *quality* term is still
Bridgeport's. Minor now that job_access dominates the blend; revisit only if it surfaces.

## Where it feeds
`total_score` (one of 14 pillars) and the longevity index (linear factor). Cascade handled by
the apply script.

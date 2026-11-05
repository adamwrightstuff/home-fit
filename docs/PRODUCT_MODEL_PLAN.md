# Product model and build plan: separating status, who lives here, local scene, vibrancy and Aura

Written 2026-11-05. Plan only: no scoring change is made by this document. Every step below goes through a DPv2 spec sheet (reference frame, evidence tier, audit gap table, options with one recommendation) and needs the owner's approval before a scoring change. Nothing is pushed to main without an explicit yes.

## The rule for how things are grouped
- Score it only if every user wants more of it and a sourced curve exists (the pillars).
- Describe and filter it if "more" depends on taste (wealth, education, age, household type, diversity, political lean). Show plain facts; no invented weights.
- Tag it if it is a category (status tier, local scene, vibrancy, trajectory).

## The jobs
| Job | Treatment | Home | State today |
|---|---|---|---|
| Is it good to live in | Score | 12 pillars, user-weighted | Exists |
| What does it cost | Score, budget filter | Housing value pillar only; no housing in any label | Exists; label still uses housing burden |
| Who lives here (wealth, education, age, families) | Describe, filter | New "who lives here" panel plus life-stage filter | Stored data covers all but household type |
| Economic standing | Tag | Status signal: income and home value only | Built (Level 2 with accepted TODOs); frame and burden open |
| Character: independent places | Tag (High, Some, Low) | Local scene | Shipped; scored from business names with a hardcoded chain list; no spec sheet |
| Vibrancy: activity and energy | Tag | Amenities culture and social density, working-age share | Not built |
| Aura | Retire, or define as only the two tags above | Today 50% local scene, 35% eight pillars, 15% status | Shipped badge |
| Where it is heading | Tag | Trajectory | Keep as is |

Naming trap: schools quality is a pillar; residents' education is a fact in the panel. Use different names in the UI.

## Owner decisions needed (each blocks a step)
1. Status signal means economic standing (income plus home value, no housing burden). Recommended: yes.
2. Tier frame: national lines for the ends (Pew twice the national median, poverty line) with the metro ratio alongside, or a clear "relative to metro" name. Open since the v2 and v3 spec review.
3. Aura: retire it and show the two tags, or keep it as their combination. Retiring changes a shipped badge.
4. The "who lives here" panel is plain stats with no score. Recommended: yes.

## Build order and dependencies
Steps 1, 2 and 5 are independent and can run in parallel in separate worktrees. Step 3 needs 4, step 4 needs 2.

1. Who lives here panel. Stored data only: median and mean income, home value, renter share, graduate degree share, age shares (existing life-stage percentiles). Output: backend fields, frontend panel, spec sheet at Level 1 (descriptive, no parameters). Check each field's pooling and its vintage; spot-check a sample against the Census source (needs the owner's OK for the calls).
2. Status signal narrowing. Remove the housing burden test from the label (housing stays in the housing pillar). Pre-register a national-line candidate and test it offline: share of households at $150,000 or more from the stored income brackets (the check that was never run), mean income and rent proxies, launch pairs including Tribeca vs Murray Hill, Palo Alto vs East Palo Alto, Beverly Hills. Close the accepted TODOs from the 2026-11-04 sign-off where data allows. Mirror to the live scorer, the TypeScript copy and the catalog (docs/LIVE_SCORER_VS_EXPLORER.md).
3. Local scene rebuild. Spec sheet and audit first. Replace name guessing with chain and brand tags if the stored business lists carry them; if they do not, a new Overpass read is needed (ask before any call). Independent validation source still to choose; none identified yet.
4. Vibrancy tag. Spec sheet. Inputs: amenities culture and social density, working-age share. Evidence: Couture and Handbury cover young college graduates only, so the evidence tier is weak and stated as such. Depends on step 3 so the two tags do not double count.
5. Household type. A new Census table (families with children, single-person households, renters). Check the archive folder first; ask before any new Census call. Feeds the panel and the life-stage filter.
6. Aura. After 3 and 4 and decision 3: retire the badge or recompute it from the two tags only. Drops the 35% livability share (double counts the pillars) and the 15% status share (mixes wealth into vibe).

## For every step
Level 1 (spec sheet, gap table, owner sign-off), then Level 2 with criteria fixed first and the checks run by someone other than the builder. Product copy never says "validated" unless every check passes. Catalog changes are offline recomputes into new files, then swapped in; the Explorer serves the composites_recomputed files.

## Not in scope
Trajectory (kept as is), the pillars' own scoring, the housing value pillar, and any rebuild of the 12-pillar total.

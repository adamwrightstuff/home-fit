# UX Level 2 re-check (independent checker, 2026-11-08)

Checked: origin/main at 8c7d7bb8 (detached worktree), Next dev server on port 3101, Chrome via Playwright, fresh context per capture, 1280x800 and 375x812, signed out, empty storage, no backend (API health 502). Criteria used exactly as pre-registered in docs/UX_AUDIT.md (Level 2 pre-registration, D, D2). Screenshots: `docs/ux_audit_screens/l2_*.png` (54 files, suffix `__desktop` or `__m375`). Seeded or mocked captures are named `_SEEDED` or `_MOCKED_geocode` (localStorage work hub seed; geocode stubbed in the browser, no live API).

"code only" means read in source, not rendered (needs backend or login).

## Verdict

Level 2 is NOT met for the app. 29 pre-registered rows: 18 PASS, 8 FAIL, 3 NOT CHECKABLE. The previously fixed rows mostly hold, but commute still has editors beyond the profile, the search place screen still edits weights and premium code, and the twin finder controls are still greyed on mobile.

## D gap table and D2 rows

| ID | Result | Evidence |
|---|---|---|
| R1-1 | FAIL (partial) | Three of four fixed: Explorer pill outlined, mobile "Show list" is white and sits above the sheet (`l2_catalog_fresh__m375.png`). Still two solid fills on the first screen: coral "Take the quiz" (rgb 201,105,86) and the purple active "HomeFit" sort pill (rgb 127,119,221), on desktop and mobile (`l2_catalog_fresh__desktop.png`). The row named the HomeFit pill and the fix said outline sort tabs. Owner may rule the active segment is a state, not an action. |
| R1-2 | PASS (code only) | `PlaceView.tsx`: Add and Rerun no longer use `hf-btn-primary`; only "Run Score (N)" or "View results" do, and they are mutually exclusive (lines 1398-1420). |
| R2-1 | FAIL (partial) | Work hub, mode, days are profile only (rendered). But the filter sheet still edits "Commute over" (Under 15/30/45/60 min buttons, `l2_catalog_filters_with_hub_SEEDED__*.png`) and the Priorities panel still edits "Your commute" None/Low/Medium/High (`l2_catalog_priorities_with_hub_SEEDED__*.png`), each with a profile link. Row asked for read-through links; G1 is still an open owner decision. Quiz still writes the hub. |
| R2-2 | PASS (code only) | `app/quiz/page.tsx` writes `commute_mode` and `office_days` at top level, no `filters.commuteMode/officeDays`. Quiz iframe flow not walked. |
| R2-3 | PASS (code only) | `app/search/page.tsx` `mergeStoredOptions` spreads existing storage, all writes go through it. Not reproduced (needs backend). |
| R2-4 | FAIL (code only) | `PlaceView.tsx:1152` still has an "Importance:" editor with local `selectedPriorities`; `ScoreDisplay` shares the weights panel but PlaceView does not. |
| R2-5 | PASS | Metro only in the toolbar picker ("All metros"); no Metro group in the filter sheet (`l2_catalog_filters_open__*.png`). |
| R2-6 | NOT CHECKABLE (owner-accepted limit) | Per-card selectors accepted 2026-11-05, not graded. Catalog side checked: life stage and political lean in the filter sheet only, scenery and kinds in Priorities only, no duplicate. |
| R2-7 | FAIL (code only) | Premium code editor still in `PlaceView.tsx:1284-1315` and `app/saved/[id]/page.tsx:429-470`. |
| R2-8 | PASS | Chose Mountain + Family on /vacation (storage `trovamo_vacation_prefs`), /vacation/explorer opened with Mountain outlined and Family filled (`l2_vacation_explorer_after_vacation_choice__*.png`); /vacation keeps them on return. |
| R2-9 | NOT CHECKABLE | Quiz now merges into the same storage fields (code), but G9 is undecided, the iframe flow and signed-in profile sync were not run. |
| R3-1 | PASS | Set Natural Beauty, Active Outdoors, Social Fabric, Schools to None: scenery chips 4 to 0, AO kinds 3 to 0, school type/grade chips 4 to 0, Schools "Hide" chip gone; Community Safety (still Medium) kept its Hide chip. Reset priorities restored all 12 to Medium and the chips (`l2_catalog_priorities_none__*.png`). Both widths. |
| R3-2 | PASS | /profile fresh: no mode or days chips (`l2_profile_fresh__*.png`). With a hub (geocode mocked): chips appear (`l2_profile_hub_set_MOCKED_geocode__*.png`). Note: "Fastest" is shown pressed after a hub is set (default null mode); the row's fix text said no pre-selected chip, so the owner should confirm that is acceptable. |
| R3-3 | PASS | Filter sheet with no income: no Price chip, only "Add a work address" link and the filters. With-income state not rendered. |
| R3-4 | FAIL (mobile) | Desktop: controls hidden, text "Search a neighborhood to start" (`l2_catalog_twin_empty__desktop.png`). Mobile 375: Cross-metro, Same metro, Same class, Pillars (12) still shown and `disabled` with reduced opacity (`l2_catalog_twin_empty__m375.png`; `catalog-page-client.tsx` mobile block near line 1607 still renders them with `disabled={twinControlsLocked}`). |
| R3-5 | PASS | Longevity, Happiness, Archetype, A-Z: Priorities button absent (0 matches), both widths. |
| R3-6 | PASS | /vacation: Search enabled, label "Search", no helper text, Beach preselected; empty submit focuses the input. |
| R3-7 | PASS | /search and /vacation: Search button not disabled; empty click focuses the input (`activeElement` INPUT), both widths. |
| R3-8 | PASS (code only) | Run Score only renders when `netNewCount > 0`, otherwise "View results" or nothing; no disabled inert button (`PlaceView.tsx:1401`). |
| R5-1 | PASS | Twin finder empty: "Try one of these" Ridgewood, La Grange, Palo Alto, Havertown, Winchester, Westwood, both widths. |
| R5-2 | FAIL (partial) | Income quick picks $50k to $200k exist. Current home and people still start empty, no "use the place I selected" chip (`l2_profile_fresh__*.png`). Owner already logged it as partial. |
| R5-3 | PASS | /vacation opens with Beach selected. |
| R5-4 | PASS | /auth/callback: "Back to the catalog" link and "Then use Sign in to try again." (`l2_auth_callback__*.png`). |
| R6-1 | FAIL (code only) | PlaceView still edits importance, premium code, job categories and preferences after a search (same lines as R2-4, R2-7). Catalog side is clean: search box filters places only. |
| CA-1 | PASS (caveat) | One basis line under the toolbar for the active index ("HomeFit: average of the 12 pillars, equal weights. Adjust priorities to personalize."; Longevity and Happiness lines on sort) and expanded row header "PILLARS (SCORE, WEIGHT IN HOMEFIT BLEND)". The desktop detail panel shows three index numbers but no basis line of its own. |
| CA-2 | PASS | Neighborhood page map card has no pillar count (`showProgress={false}`); page says "12 pillars" (Ridgewood, Coconut Creek). See new item N3 for the live-score card. |
| CB-1 | FAIL | Pillar rows in the list now read "No data" with a hover-only `title` reason (touch gets none). Detail panel and bottom sheet index values return "No data" with no reason (`CatalogDetailPanel.tsx:38`, `CatalogBottomSheet.tsx:39`). Coconut Creek Community Safety shows "No data" and weight 0% (`l2_catalog_coconut_detail__desktop.png`). |
| CB-2 | PASS | Coconut Creek neighborhood page: "Not enough source data here" plus "No data" for Community Safety (`l2_neighborhood_coconut__*.png`). |
| CB-3 | NOT CHECKABLE (code only) | `saved/compare/page.tsx:774,888` now says "No data for this place" with an open link; states the gap, not the cause. Needs a signed-in render. |

## Rules 1 to 6 and candidates A, B on screens that render

- /catalog desktop and mobile (map, list, expanded row, Filters sheet, Priorities panel, twin empty): Rule 1 filled-control issue in R1-1 only (Filters sheet: one dark "Show N results", Clear all plain; Priorities: one purple "Done"). Rule 2 residual is commute (R2-1). Rule 3 residual is mobile twin (R3-4). Rule 4: first screen has no personal chip; commute and people show text plus profile link only. Rule 5: quiz link on first screen and in Priorities, twin suggestions. Rule 6: catalog search box filters by name only. Reset: Filters Clear all returns badge and count to 1476; Reset priorities returns all levels to Medium. Those pass criterion 3 for the catalog.
- /profile: Rules 1, 3, 4, 6 pass; Rule 5 partial (R5-2). Clear my profile returned storage to nulls and the page to the quiet default (`l2_profile_cleared__*.png`).
- /vacation, /vacation/explorer, /search empty, /auth/callback, header (one HomeFit/TravelFit switch, one Search link, Sign in; mobile menu the same), neighborhood pages: no Rule 1 to 6 FAIL found.

## New violations (not pre-registered)

N1. Twin finder greyed controls on mobile (same as R3-4, listed here because it contradicts the shipped log entry that says R3-4 was fixed).
N2. Naming: the desktop detail panel labels the first index "TROVAMO" (`CatalogDetailPanel.tsx:24`) while the toolbar, list and neighborhood page call it "HomeFit" (Candidate A, one number two names). `l2_catalog_map_click__desktop.png`.
N3. Code only: `InteractiveMap` shows "N/TOTAL pillars complete" with `TOTAL_PILLARS = Object.keys(PILLAR_META).length` (more than 12) on live results, since `showProgress` defaults to true; contradicts the "12 pillars" copy (Candidate A, the CA-2 mismatch can still appear on /search results).
N4. Low: "Reset priorities" shows when nothing has been changed; header "Search any place" link also shows on /search itself.

## Not run, and criterion notes

- Not rendered (backend or login): /search place and results, /results with data, /vacation results, /p/[id], /saved, /saved/[id], compare, in-catalog quiz modal and signed-in restore. Launch scenarios 1, 3, 4 could not be run; scenario 3 only up to setting a hub (geocode mocked); scenario 5 not run past opening Priorities; scenarios 2 and 6 steps are within target (filter, chip, show results, row; vacation to explorer via header TravelFit link).
- Criterion 5 (criteria existed before results): the pre-registration block was never committed, so no hash proves it was frozen. Not a criterion change, but the owner should commit it.
- Criterion 1 requires every claim in C to be re-run; the signed-in and code-only claims could not be, so no screen can reach Level 2 on this pass.
- Missing-data states used real places: Coconut Creek FL (community safety) on the catalog and neighborhood page.

# Trovamo UX audit (2026-11-05)

**Conclusion.** App level: **0 (Not certified)**. No screen reaches Level 1: every audited screen has at least one unfixed FAIL and no FAIL has an owner-accepted entry, and three screens have only partial coverage in this pass (see F).
**FAILs:** 29 rows in the gap table (Rule 1: 2, Rule 2: 9, Rule 3: 8, Rule 4: 0, Rule 5: 4, Rule 6: 1, Candidate A: 2, Candidate B: 3). Owner confirmed 2026-11-05 that Candidates A and B count as rules; rows CA-1 to CB-3 were added after that answer.
**Top fix:** make the search page stop overwriting the shared `homefit_search_options` storage (it drops the saved work hub, commute mode, office days and current home on any edit), then collapse commute to one home on the profile page.

Status: read-only audit. Nothing is committed or pushed. Branch `ux-audit`, cut from `origin/main` at 4cc3cc44. Only files written: this document and `docs/ux_audit_screens/`.

Standard: `docs/UX_PRINCIPLES_DRAFT.md` (six owner rules, two candidates). Levels modeled on `docs/DPV2_ADOPTION_DRAFT.md`.

---

## A. Screen and component inventory

### A1. Pages and layouts (confirmed against the filesystem, 2026-11-05)

The list matches the brief: 16 `page.tsx` plus the root `layout.tsx`. No nested layouts exist. `app/page.tsx` only redirects `/` to `/catalog`.

Command: `find app -name page.tsx -o -name layout.tsx` (result: `/`, `/search`, `/results`, `/quiz`, `/catalog`, `/catalog/la`, `/neighborhoods/[slug]`, `/p/[id]`, `/profile`, `/saved`, `/saved/[id]`, `/saved/compare`, `/vacation`, `/vacation/explorer`, `/auth/callback`, `/auth/update-password`, plus `app/layout.tsx`). Entry components that are not named `page.tsx` but are the real screen: `app/catalog/catalog-page-client.tsx` (2049 lines) and `app/results/results-client.tsx` (1022 lines).

### A2. Page to component map

Built by following imports recursively (script reads every `import ... from '@/...'` and relative import, resolves to `.tsx/.ts`, takes the closure). Pages that import another page's client file inherit its components.

| Page / layout file | Components reached (recursive imports, through `components/`) |
|---|---|
| `app/auth/callback/page.tsx` | (none) |
| `app/auth/update-password/page.tsx` | (none) |
| `app/catalog/la/page.tsx` | PillarInfoIcon.tsx, QuizModal.tsx, RelocationEquivalent.tsx, SearchOptions.tsx, WhyNotHigher.tsx, catalog/ArchetypeBadge.tsx, catalog/AuraBadge.tsx, catalog/CatalogBottomSheet.tsx, catalog/CatalogDetailPanel.tsx, catalog/CatalogListView.tsx, catalog/CatalogMapView.tsx, catalog/CatalogWeightPanel.tsx, catalog/CompareTray.tsx, catalog/FilterSheet.tsx, catalog/HeroBand.tsx, catalog/IndexInfoButton.tsx, catalog/InfoSheet.tsx, catalog/LocalSceneChip.tsx, catalog/MapLegend.tsx, catalog/MetroDot.tsx, catalog/MetroPicker.tsx, catalog/PillarTwinDrawer.tsx, catalog/RadarChart.tsx, catalog/TrajectoryChip.tsx, catalog/TwinCandidateDetailContent.tsx, catalog/TwinDiffRows.tsx, catalog/TwinFinderPanel.tsx, catalog/TwinResultCard.tsx, vacation/ClimateProfileCard.tsx |
| `app/catalog/page.tsx` | PillarInfoIcon.tsx, QuizModal.tsx, RelocationEquivalent.tsx, SearchOptions.tsx, WhyNotHigher.tsx, catalog/ArchetypeBadge.tsx, catalog/AuraBadge.tsx, catalog/CatalogBottomSheet.tsx, catalog/CatalogDetailPanel.tsx, catalog/CatalogListView.tsx, catalog/CatalogMapView.tsx, catalog/CatalogWeightPanel.tsx, catalog/CompareTray.tsx, catalog/FilterSheet.tsx, catalog/HeroBand.tsx, catalog/IndexInfoButton.tsx, catalog/InfoSheet.tsx, catalog/LocalSceneChip.tsx, catalog/MapLegend.tsx, catalog/MetroDot.tsx, catalog/MetroPicker.tsx, catalog/PillarTwinDrawer.tsx, catalog/RadarChart.tsx, catalog/TrajectoryChip.tsx, catalog/TwinCandidateDetailContent.tsx, catalog/TwinDiffRows.tsx, catalog/TwinFinderPanel.tsx, catalog/TwinResultCard.tsx, vacation/ClimateProfileCard.tsx |
| `app/layout.tsx` | ApiVersion.tsx, AuthBar.tsx, AuthModal.tsx, ClientLayout.tsx |
| `app/neighborhoods/[slug]/page.tsx` | InteractiveMap.tsx, NeighborhoodMap.tsx, NeighborhoodPersonal.tsx, SearchOptions.tsx, WhoLivesHere.tsx |
| `app/p/[id]/page.tsx` | ArchetypeTrajectoryInfo.tsx, HappinessInfo.tsx, HomeFitInfo.tsx, InteractiveMap.tsx, LongevityInfo.tsx, PillarCard.tsx, ScoreDisplay.tsx, SearchOptions.tsx, StatusArchetypeCompass.tsx, StatusSignalInfo.tsx, TotalScore.tsx, WhyNotHigher.tsx, catalog/InfoSheet.tsx, catalog/TrajectoryChip.tsx |
| `app/page.tsx` | (none) |
| `app/profile/page.tsx` | SearchOptions.tsx, catalog/PeopleYouKnowPicker.tsx, catalog/WorkHubPicker.tsx |
| `app/quiz/page.tsx` | QuizModal.tsx, SearchOptions.tsx |
| `app/results/page.tsx` | ArchetypeTrajectoryInfo.tsx, CompletedPillars.tsx, CurrentlyAnalyzing.tsx, FamilyServicesPanel.tsx, HappinessInfo.tsx, HomeFitInfo.tsx, InteractiveMap.tsx, LoadingQuotes.tsx, LongevityInfo.tsx, PillarCard.tsx, ProgressBar.tsx, ScoreDisplay.tsx, SearchOptions.tsx, SmartLoadingScreen.tsx, StatusArchetypeCompass.tsx, StatusSignalInfo.tsx, TotalScore.tsx, WhyNotHigher.tsx, catalog/InfoSheet.tsx, catalog/TrajectoryChip.tsx |
| `app/saved/[id]/page.tsx` | ArchetypeTrajectoryInfo.tsx, HappinessInfo.tsx, HomeFitInfo.tsx, InteractiveMap.tsx, LongevityInfo.tsx, PillarCard.tsx, ScoreDisplay.tsx, SearchOptions.tsx, StatusArchetypeCompass.tsx, StatusSignalInfo.tsx, TotalScore.tsx, WhyNotHigher.tsx, catalog/InfoSheet.tsx, catalog/TrajectoryChip.tsx |
| `app/saved/compare/page.tsx` | PillarInfoIcon.tsx, RelocationEquivalent.tsx, SearchOptions.tsx |
| `app/saved/page.tsx` | SearchOptions.tsx |
| `app/search/page.tsx` | AppHeader.tsx, ErrorMessage.tsx, ExportScoresModal.tsx, HappinessInfo.tsx, HomeFitInfo.tsx, InteractiveMap.tsx, LocationSearch.tsx, LongevityInfo.tsx, PillarCard.tsx, PillarInfoIcon.tsx, PlaceView.tsx, QuizModal.tsx, ScoreDisplay.tsx, SearchOptions.tsx, StatusArchetypeCompass.tsx, StatusSignalInfo.tsx, TotalScore.tsx, TrajectoryInfo.tsx, WhyNotHigher.tsx, catalog/InfoSheet.tsx, catalog/TrajectoryChip.tsx, vacation/ClimateProfileCard.tsx |
| `app/vacation/explorer/page.tsx` | SearchOptions.tsx, vacation/TravelerProfileSelector.tsx |
| `app/vacation/page.tsx` | AppHeader.tsx, ErrorMessage.tsx, HappinessInfo.tsx, HomeFitInfo.tsx, InteractiveMap.tsx, LoadingSpinner.tsx, LocationSearch.tsx, LongevityInfo.tsx, PillarCard.tsx, ScoreDisplay.tsx, SearchOptions.tsx, StatusArchetypeCompass.tsx, TotalScore.tsx, WhyNotHigher.tsx, catalog/InfoSheet.tsx, vacation/ClimateProfileCard.tsx, vacation/MapEmbed.tsx, vacation/TravelerProfileSelector.tsx, vacation/TripTypeSelector.tsx |

Notes on the map:
- `app/page.tsx` has no UI (server redirect).
- `/catalog/la` renders the same `CatalogPageClient` as `/catalog` with `initialMetroFilter` set (see `app/catalog/la/page.tsx`).
- `/auth/*` render their own inline markup, no shared components beyond the layout shell (`ApiVersion`, `AuthBar`, `AuthModal`, `ClientLayout`, all via `app/layout.tsx`).
- `SearchOptions.tsx` appears in most rows only because pages import `DEFAULT_PRIORITIES` and types from it. **The default-export UI component is never rendered anywhere** (proof below), so its large "Customize your score" panel is dead code.

### A3. Unreferenced or constants-only components (findings)

Proof, run from `frontend/`:

```
grep -rl PlaceValuesGame . --include='*.ts' --include='*.tsx' --exclude-dir=node_modules --exclude-dir=.next
  components/PlaceValuesGame.tsx, lib/agentRecommend.ts   (lib hit is a comment only, line 57)
grep -rl SignalStrengthDots ...      components/catalog/SignalStrengthDots.tsx   (itself only)
grep -rl VibeTwinResultCard ...      components/catalog/VibeTwinResultCard.tsx   (itself only)
grep -rn "SearchOptionsComponent\|<SearchOptions\b" app components --include='*.tsx'
  only the import at app/search/page.tsx:8 and the definition at components/SearchOptions.tsx:106,694
```

| Component | Status |
|---|---|
| `components/PlaceValuesGame.tsx` | Unreferenced (no import anywhere). Finding. |
| `components/catalog/SignalStrengthDots.tsx` | Unreferenced. Finding. |
| `components/catalog/VibeTwinResultCard.tsx` | Unreferenced. Finding. |
| `components/SearchOptions.tsx` (UI) | Constants and types are used; the panel component is never rendered. Finding (dead duplicate editor, see B and G). |

### A4. Screen states enumerated

"Browser" means I rendered it at 375px and desktop (1280x800) with a fresh browser context (empty storage, signed out). "Code-only" means it needs a keyed API, a backend run, or a signed-in account I do not have.

| Screen | States | How checked |
|---|---|---|
| `/catalog` (and `/catalog/la`) | fresh signed out (map), list view, place selected (desktop expanded row, mobile list), filter sheet, weights panel, twin finder empty, twin finder with a query, compare tray, quiz modal, signed in (preferences restore), loading, "no places clear all filters" fallback | Browser: first six. Code-only: twin with a query, compare tray, quiz modal, signed in, loading, fallback (`catalog-page-client.tsx:1816`). |
| `/search` | entry (fresh), geocoding, error, place screen (`PlaceView`: pillar selection), scoring overlay, results (`ScoreDisplay`), export modal, quiz game | Browser: entry only. Code-only: the rest (geocode and scoring need the backend and keyed APIs). |
| `/results` | missing params (error), loading (`SmartLoadingScreen`), results, partial pillars, signed out vs in save control | Browser: missing params only. Code-only: rest. |
| `/quiz` | quiz iframe (`public/quiz.html`, 1122 lines), apply | Browser: loads (iframe body not captured by text read). Code-only: question flow read by grep of question ids and `showIf`. |
| `/profile` | fresh signed out, signed in (account load, saving states), clear-all confirm | Browser: fresh. Code-only: signed in. |
| `/saved` | signed out, signed in empty, list, compare mode | Browser: signed out. Code-only: rest (needs account). |
| `/saved/[id]`, `/saved/compare` | signed out (shows the `/saved` sign-in gate), signed in view | Browser: signed out. Code-only: rest. |
| `/p/[id]` | share link valid, invalid or unavailable | Browser: invalid id with no backend (shows "Service unavailable", so the real not-found copy was not seen). |
| `/neighborhoods/[slug]` | full data, missing pillar | Browser: Ridgewood NJ (full) and Coconut Creek FL (community safety null). |
| `/vacation` | entry (fresh), loading, error, results | Browser: entry. Code-only: rest. |
| `/vacation/explorer` | fresh map, filter by trip type and traveler, place selected | Browser: fresh. Code-only: rest. |
| `/auth/callback`, `/auth/update-password` | error or no tokens, form | Browser: both (fresh). |
| Shell: `AuthModal`, `ExportScoresModal`, `InfoSheet`, `PillarTwinDrawer`, `CatalogBottomSheet` | modals and sheets | Code-only for the modals; bottom sheet seen at 375px on `/catalog`. |

Mobile layout differs from desktop on `/catalog` (toolbar, bottom sheet, filter sheet, weights sheet) and in the header (hamburger at 375px), so both widths were captured for each reachable state.

### A5. API routes (no UI)

`app/api/agent/recommend`, `catalog-map`, `climate-profile`, `family-services`, `geocode`, `health`, `me/preferences`, `me/profile`, `me/saved-scores`, `me/saved-scores/[id]`, `p/[id]`, `relocation/metro`, `relocation`, `score/recompute-composites`, `score`, `score/stream`, `vacation-catalog`. All `route.ts`. No UI.

### A6. Completeness check (re-run at the end)

Re-ran `find app -name page.tsx -o -name layout.tsx` (17 files) and `find components -type f` (67 files) and diffed against A1 to A3. **Diff: empty.** Every component is either mapped in A2 or listed in A3.

---

## B. Settings inventory (drives Rules 2 and 3)

Method: for each setting, every UI control that writes it. Search run over the whole tree: `grep -rn "<setter or storage key>" app components lib hooks contexts --include='*.ts' --include='*.tsx'`. Homes = live editing locations (dead code excluded, listed separately).

| # | Setting | Live edit locations (file:line) | Storage or API field | Homes | Rule 2 |
|---|---|---|---|---|---|
| 1 | Work hub | Profile `WorkHubPicker` `app/profile/page.tsx:441`; quiz `public/quiz.html:529` question `work_hub`, applied at `catalog-page-client.tsx:1237` | profile API `work_zone_id`; localStorage `homefit_search_options.filters.workZoneId` (`profile/page.tsx:60`) | 2 | FAIL |
| 2 | Commute mode | Profile chips `profile/page.tsx:452-454`; quiz `quiz.html:498` (only `transit` or null reaches the payload, `QuizModal.tsx:14`) | profile API `commute_mode`; localStorage `opts.commute_mode`; the `/quiz` route writes `filters.commuteMode` instead (`app/quiz/page.tsx:20`) which nothing reads | 2 | FAIL |
| 3 | Office days | Profile chips `profile/page.tsx:464-470`; quiz (`quiz.html:484` `work` question sets office or hybrid or remote) | profile API `office_days`; `opts.office_days`; `/quiz` route writes `filters.officeDays` (`quiz/page.tsx:21`), unread | 2 | FAIL |
| 4 | Commute cap ("Commute over") | Filter sheet `FilterSheet.tsx:259-264`; quiz `quiz.html:542` | `opts.filters.filterCommuteMax` | 2 | FAIL |
| 5 | Commute priority | Weights panel "Personal fit" `CatalogWeightPanel.tsx:255-272` | `opts.priorities.commute_time` | 1 | PASS alone, but the same concept as 1 to 4 (see G1) |
| 6 | Household income | Profile `profile/page.tsx:339-351` only (the duplicate in `SearchOptions.tsx:651-670` is dead code) | profile API `household_income`; `opts.household_income` | 1 | PASS |
| 7 | Current home and rent | Profile `profile/page.tsx:360-430` only | profile API `current_home`; `opts.current_home_match` | 1 | PASS |
| 8 | People you know | Profile `PeopleYouKnowPicker` `profile/page.tsx:483` only | profile API `people`; localStorage `socialConnections` key | 1 | PASS |
| 9 | Pillar priorities (12 weights) | Weights panel `CatalogWeightPanel.tsx:210`; search place screen `PlaceView.tsx:1172-1180` (Low/Med/High only, local `selectedPriorities`); results and saved view `ScoreDisplay.tsx:603-608` (per-card selector; read-only on `/p/[id]`, `p/[id]/page.tsx:278`); quiz | `opts.priorities` (catalog, quiz, search); `PlaceView` local state; saved score row priorities (`saved/[id]/page.tsx:855`) | 4 | FAIL |
| 10 | Metro filter | Toolbar `MetroPicker` `catalog-page-client.tsx:1373` (desktop) and `:1575`; filter sheet Metro chips `FilterSheet.tsx:270` | React state `filterMetro` (not persisted) | 2 on one screen | FAIL |
| 11 | Political lean filter | Filter sheet `FilterSheet.tsx:404`; quiz (`filterPoliticalLean` in payload, `quiz/page.tsx:26`) | `opts.filters.filterPoliticalLean` | 2 | FAIL (quiz as second home, owner decision, see G9) |
| 12 | Life stage (diversity preference) | Filter sheet `FilterSheet.tsx:430`; per-card selector `ScoreDisplay.tsx:641-645` and `PlaceView.tsx` diversity section | `opts.filters.filterLifeStage` and `opts.diversity_preference` (two fields, kept in step one way only, `catalog-page-client.tsx:154-157`) | 2 | FAIL |
| 13 | Natural beauty scenery | Weights panel chips `CatalogWeightPanel.tsx:218`; per-card `ScoreDisplay.tsx:625-628` and `PlaceView.tsx:1196-1226`; quiz | `opts.filters.filterNbTypes` vs `opts.natural_beauty_preference` (different fields, same concept) | 3 | FAIL |
| 14 | Built environment | Filter sheet area types `FilterSheet` (`filterAreaTypes`, not persisted); per-card `ScoreDisplay.tsx:635` and `PlaceView.tsx` | `filterAreaTypes` vs `opts.built_density_preference` | 2 | FAIL |
| 15 | Climate must-haves, 6 pillar must-haves | Filter sheet `FilterSheet.tsx:236-253`; quiz | `opts.dealbreakers`, `opts.filters.climatePrefs` | 2 (quiz as writer) | Owner decision (G9) |
| 16 | Trajectory, archetype, housing stock, tenure, local scene, Aura filters | Filter sheet only (some also quiz) | `opts.filters.*` | 1 (+quiz) | PASS (quiz: G9) |
| 17 | School type and grades, AO kinds | Weights panel `CatalogWeightPanel.tsx:219-243` only | `opts.filters.filterSchoolType/Levels/AoTypes` | 1 | PASS |
| 18 | Chain businesses | Per-card `ScoreDisplay.tsx:615-617` only (the toggle in `SearchOptions.tsx` is dead). Defaults disagree: `search/page.tsx:46` false, `saved/[id]/page.tsx:144` true | `opts.include_chains` | 1 | PASS for homes; default conflict noted in E |
| 19 | Premium code and school scoring | `PlaceView.tsx:1341-1385`; `saved/[id]/page.tsx:459-500` (the third, `SearchOptions.tsx:379`, is dead) | sessionStorage `homefit_premium_code`; `opts.enable_schools` | 2 | FAIL |
| 20 | Job categories | `PlaceView.tsx:1284` only (dead duplicate in `SearchOptions.tsx`) | `opts.job_categories` | 1 | PASS |
| 21 | Vacation trip type and traveler profile | `/vacation` `TripTypeSelector`, `TravelerProfileSelector` (`vacation/page.tsx:138,147`); `/vacation/explorer` own filter chips (`explorer/page.tsx:275-276`) | two separate React states, neither persisted | 2 | FAIL |
| 22 | Vacation month | `/vacation` only (`vacation/page.tsx:29`, defaults to current month) | React state | 1 | PASS |
| 23 | Saved-score metadata (name, notes) | No edit UI found (`grep -n "Rename\|rename" app/saved`: none) | n/a | 0 | N/A |
| 24 | Account, password | `AuthModal`, `/auth/update-password` | Supabase auth | 1 each | PASS |

Two stores hold personal data: `/api/me/profile` (income, home, work hub, mode, office days, people; `lib/userProfile.ts`) and `/api/me/preferences` (`explorer_options`, the catalog's priorities and filters). Both write to `user_preferences`. The profile page mirrors into localStorage (`profile/page.tsx:50-64`); the catalog restores from both (`catalog-page-client.tsx:404-473`).

---

## Level 2 pre-registration (written before any Level 2 check)

Written 2026-11-05 by the auditor. Not committed (the brief says commit only when asked), so there is no commit hash to record; the owner should say if they want this block committed first. **No Level 2 check has been run**, and none can be by this auditor (the same agent that found a FAIL does not grade its fix). These criteria are frozen. Any change after results is labelled "changed after results" and needs owner approval.

Level 2 pass criteria, per screen:
1. Every claim in C for that screen is re-run by an agent other than the one who built or fixed it.
2. Fresh-visitor walkthrough (cleared storage, signed out) of the screen's main task, at 375px and 1280px, with zero Rule 1, 3, 4 or 5 FAIL.
3. Every personal layer set on that screen can be reset on that screen or by a link to its single home, and reset returns the screen to its quiet default (commute off, no personal chips, priorities at `DEFAULT_PRIORITIES`).
4. Missing-data states of that screen were rendered and checked using a real place that lacks data (not invented).
5. These criteria existed before the results.

Walkthroughs (main task per screen): `/catalog` pick a place and read its score; `/profile` set a work address and see the nearest hub; `/search` search one place; `/vacation` choose a trip type and search; `/saved` save then compare two; `/neighborhoods/[slug]` read the place.

Launch scenarios (pass = finishes in the stated steps with no FAIL on Rules 1 to 6):
1. New visitor searches one place and reads the result (target 3 steps: type, submit, read).
2. New visitor opens the catalog, applies one filter, opens one place (target 4 steps).
3. Signed-in user sets a work address, sees commute on a card, then clears it (target 6 steps).
4. User saves two places and compares them (target 6 steps).
5. User changes one priority weight and sees the ranking respond (target 3 steps).
6. Vacation: trip type to explorer (target 4 steps).

Candidates A and B: owner confirmed 2026-11-05 that they count (this changes no criterion above; it adds rows).

---

## C. Per-rule results

Evidence key: screenshots are in `docs/ux_audit_screens/` (named `screen_state__viewport.png`). `code` means file:line. Level-relevant results are only those with evidence.

### C1. `/catalog` (and `/catalog/la`, same client)

| State | Rule | Result | Evidence |
|---|---|---|---|
| Fresh, desktop, map | 1 One primary action | FAIL | Primary should be "open a place". Four filled controls compete: coral "Take the quiz" CTA, coral active "Explorer" pill, purple active "HomeFit" sort pill, outlined "Adjust weights". `catalog_fresh_signedout__desktop.png`; code `catalog-page-client.tsx:1291-1296`, `:1438` |
| Fresh, 375px, map | 1 | FAIL | Coral "Take the quiz" and filled dark "Show list" both prominent; "Show list" sits on top of the bottom-sheet hint text. `catalog_fresh_signedout__m375.png`; code `catalog-page-client.tsx:1887` |
| Fresh | 2 | FAIL | Metro in two places (picker and sheet chips); commute four places; priorities four places (B rows 1 to 5, 9, 10) |
| Fresh | 3 | FAIL | See gap rows R3-1, R3-4, R3-5 |
| Fresh | 4 Quiet | PASS | Fresh storage, signed out. Defaults: `DEFAULT_PRIORITIES` `SearchOptions.tsx:71-89` (commute_time `'None'` :87, social_connection `'None'` :88, political_lean `'None'` :86, built_environment `'None'` :74, diversity `'None'` :84, others `'Medium'`); state defaults `filterCommuteMax 'all'` `catalog-page-client.tsx:198`, `workZoneId null` :205, `commuteMode null` :212, `officeDays null` :220, `people []` :236, `dealbreakers {}` :239. No personal chip on the first screen of the map or list (`catalog_list_fresh__desktop.png`, `__m375.png`). `Commute: N/A` pill only when commute priority above None (`CatalogListView.tsx:322`) |
| Fresh | 5 Suggestion | PASS (partial) | Weights panel starts at equal weights and links the quiz (`CatalogWeightPanel.tsx:158-165`); map shows places without any input. No suggested search terms in the catalog search box (Low) |
| Fresh | 6 Search finds | PASS | Catalog box filters the place list by name only (`catalog-page-client.tsx:1317-1321`); `MetroPicker` "Search metros" finds metros only (`MetroPicker.tsx:94`) |
| Filter sheet open, 375 and desktop | 1 | PASS | One filled button "Show N results" (`FilterSheet.tsx:507-522`), "Clear all" is plain text. `catalog_filtersheet_open__m375.png` |
| Filter sheet | 3 | FAIL | Price chip shown with no income set (`FilterSheet.tsx:236-253`); text "Add your income in your profile" |
| Filter sheet | 2, 4, 5, 6 | see B / PASS / PASS / PASS | Dead-end text with profile link, no weights or personal settings editable here except the commute cap (B row 4) |
| Weights panel open | 1 | PASS | One gradient "Done" (`CatalogWeightPanel.tsx:316-318`) plus per-pillar level chips, which are selection controls. `catalog_weights_open__desktop.png`, `__m375.png` |
| Weights panel | 3 | FAIL | Scenery, kind, school and grade chips show even when the parent pillar is None (`:218-243`, no guard). `catalog_weights_naturalbeauty_none__desktop.png` (Natural Beauty set to None, chips still visible) |
| Weights panel | 3, "Personal fit" | PASS | Commute and people levels hidden until a work hub or people exist; the unset state shows text plus a profile link, not a disabled control (`:255-285`) |
| Weights panel | 4 | PASS | Opens at equal weights |
| Weights panel | 5 | PASS | Quiz link and equal-weight start |
| Twin finder, empty | 1 | PASS | One thing to do: search a neighborhood. `catalog_twin_empty__desktop.png` |
| Twin finder, empty | 3 | FAIL | Cross-metro, Same metro, Same class and Pillars controls shown greyed (`catalog-page-client.tsx:1380-1417`, `disabled:opacity-40`, `twinControlsLocked` :1149). Same screenshot |
| Twin finder, empty | 5 | FAIL | Empty search and an empty-state paragraph, no suggested neighborhoods (`catalog_twin_empty__desktop.png`, `TwinFinderPanel.tsx:92` "No matches.") |
| Place selected | 1 | PASS | Row expands to the pillar breakdown; Compare and Twin are small secondary controls. `catalog_place_detail__desktop.png`, `catalog_place_selected__m375.png` |
| Compare tray, quiz modal, signed-in restore, loading | all | not run | Code-only; no result recorded (these are the coverage gap behind Level 0) |
| Explorer sort row, "Adjust weights" when sorting by Longevity or Happiness | 3 | FAIL | Button stays visible at opacity 0.4 with `pointerEvents: none` (`catalog-page-client.tsx:1434-1435`) |

### C2. `/profile`

| State | Rule | Result | Evidence |
|---|---|---|---|
| Fresh | 1 | PASS | One filled button "See your scores" (`profile/page.tsx:488-494`); "Clear my profile" is plain text. `profile_fresh__m375.png` |
| Fresh | 2 | PASS for income, home, people; FAIL for work hub, mode, days | B rows 1 to 3, 6 to 8 |
| Fresh | 3 | FAIL | Mode chips and office-day chips render with no work hub set (`profile/page.tsx:448-474`, no condition), and "Fastest" shows as the selected chip by default (`:452`, `mode === null`). `profile_fresh__m375.png` |
| Fresh | 4 | PASS | Nothing is on; footer shows "Clear my profile" only when something is set (`:494`) |
| Fresh | 5 | FAIL for income, current home, people (empty inputs, no preset or suggested value); PASS for work hub (typed address snaps to nearest hub, `:262`) | `profile_fresh__m375.png`, `PeopleYouKnowPicker.tsx:140-153` |
| Fresh | 6 | PASS | Home and hub search find places or hubs only |
| Signed in | all | not run | no account |

### C3. `/search` and its place and results screens

| State | Rule | Result | Evidence |
|---|---|---|---|
| Entry (fresh) | 1 | PASS | One Search button, "Try" chips are secondary, quiz is a text link. `search_fresh__m375.png`, `search_fresh__desktop.png`; `LocationSearch.tsx:297-300` |
| Entry | 3 | FAIL (Low) | Search button greyed until text is typed (`LocationSearch.tsx:297`, `disabled={disabled \|\| !location.trim()}`) |
| Entry | 4, 5, 6 | PASS | Nothing personal; example chips (`search/page.tsx:135`); box only searches places |
| Place screen (`PlaceView`) | 1 | FAIL | Per-pillar "Add" (`PlaceView.tsx:1101`) and "Rerun" (`:1064`) use `hf-btn-primary`, as does the full-width Run Score (`:1457-1480`). Code-only |
| Place screen | 3 | FAIL | "Run Score" shown disabled at opacity 0.6 when nothing is selected (`:1477-1485`). Code-only |
| Place screen | 6 | FAIL | Weights ("Importance" `:1172`), scenery and built preferences (`:1196-1226`), job categories (`:1264-1310`), school scoring and premium code (`:1339-1385`) are edited on the surface that follows a search. Code-only |
| Place screen | 2 | FAIL | B rows 9, 13, 14, 19. Plus data loss: `search/page.tsx:35-50` rebuilds the options object from only some fields and `:113` and `:176` write the whole object back to `homefit_search_options`, deleting `filters`, `commute_mode`, `office_days`, `current_home_match`, `dealbreakers` for signed-out users. Code-confirmed, not reproduced in a browser |
| Results (`ScoreDisplay`) | 1 | PASS | One save control per state (`ScoreDisplay.tsx:347` or `:357`) |
| Results | 2 | FAIL | Per-card importance and preference selectors duplicate the weights panel (B rows 9, 12 to 14) |

### C4. Other screens (coverage noted)

| Screen | Rule | Result | Evidence |
|---|---|---|---|
| `/vacation` entry | 1 | PASS | One Search control after trip type (`vacation/page.tsx:176-186`); `vacation_fresh__m375.png` |
| `/vacation` entry | 3 | FAIL | Search is disabled until a trip type is chosen, with helper text "Select a trip type above to enable search" (`:176-186`), and while disabled the button label reads "Searching..." (`LocationSearch.tsx:300`) |
| `/vacation` entry | 5 | FAIL | `tripType` starts null (`:27`), so the user cannot search without choosing; month does have a default (`:29`). Example place chips exist |
| `/vacation/explorer` | 2 | FAIL | Own trip-type and traveler state, not shared with `/vacation` (B row 21) |
| `/neighborhoods/[slug]` | 1 | PASS | Read-only page; breadcrumb and nav only |
| `/neighborhoods/[slug]` | 4 | PASS | Fresh storage, signed out; scores and summary only; personal block `NeighborhoodPersonal` hidden until a profile exists (`NeighborhoodPersonal.tsx`, `showCommute`) |
| `/saved`, `/saved/compare`, `/saved/[id]` signed out | 1, 5 | PASS | One "Explore catalog" link; `saved_signedout__m375.png` |
| `/saved` signed in empty | 5 | PASS | "Search a place" button (`saved/page.tsx:318`); code-only |
| `/auth/callback` error | 5 | FAIL | Text "Something went wrong." and nothing else (`auth/callback/page.tsx:13-33`; `auth_callback__desktop.png`) |
| `/auth/update-password` | 1 | PASS | One "Update password" button; `auth_update_password__desktop.png` |
| `/results` no params | 5 | PASS | "Back to search"; `results_noparams__desktop.png` |
| `/p/[id]` invalid | 5 | PASS | "Try Trovamo" link; `p_badid__desktop.png` (backend was not running, so the real not-found copy was not seen) |
| `AuthModal` | 1 | PASS | One submit per mode (`AuthModal.tsx:177,243`) |
| `ExportScoresModal` | 1 | PASS | One primary (`ExportScoresModal.tsx:198`) plus link-styled close |
| `/quiz` | 3, 5 | PASS | Questions are conditional on prior answers (`public/quiz.html:500,518,532,545` `showIf`) and every question has Skip |
| `/quiz` | 2 | see R2-1, R2-2, G9 | |

### C5. Candidates A and B (now counted, see D2)

| Where | A (basis at the number) | B (no silent gap) |
|---|---|---|
| Catalog list and sheet scores | FAIL: score column has no basis line; HomeFit, Longevity, Happiness basis only via `?` info buttons to a separate sheet (`IndexInfoButton`, `InfoSheet`) | FAIL: missing values render a dash glyph with no reason (`CatalogListView.tsx:90,118,156`, `CatalogDetailPanel.tsx:39`, `CatalogBottomSheet.tsx:40`) |
| Catalog "Commute: N/A" pill | PASS partly: tooltip gives the reason (`CatalogListView.tsx:322-327`) | PARTIAL: reason only on hover, none on touch |
| Pillar weight in expanded row | PASS: shows weight percent per pillar; "Natural Beauty 0%" when None (`catalog_place_detail__desktop.png`) | n/a |
| Neighborhood page | FAIL (inconsistency): map card says "15/15 pillars complete" while the page says "12 pillars" (`neighborhood_ridgewood_nj__desktop.png`) | FAIL: Community Safety shows `n/a` with no reason for Coconut Creek FL (`neighborhoods/[slug]/page.tsx:107,230`; `neighborhood_missing_pillar_coconut_creek__desktop.png`) |
| `NeighborhoodPersonal` commute | PASS: "No route to your work hub by your chosen mode" or "About N min" with office days (`NeighborhoodPersonal.tsx`) | PASS |
| `/saved/compare` | n/a | FAIL: "Not scored" with no reason (`saved/compare/page.tsx:774,888`) |
| `PillarCard` | n/a | PARTIAL: "Data unavailable" label (`PillarCard.tsx:447`), reason only if present in title text; many fields render a dash glyph (`:503-618`) |

Check of which pillars are missing in the stored catalog (read-only local read of `data/*_composites_recomputed.jsonl`, no API): `political_lean` null for all 1476 (opt-in, expected), `built_environment` 1227, `community_safety` 56, `healthcare_access` 14, `housing_value` 7, `quality_education` 4, `diversity` 3, `natural_beauty` 1. Real examples used for screenshots: Coconut Creek FL (community safety).

---

## D. Gap table (confirmed FAILs only)

Effort: S under 1 day, M 1 to 3, L more. Impact: High blocks or misleads most users, Med slows or confuses some, Low polish.

| ID | Screen | Rule | Violation | Recommended fix | Effort | Impact |
|---|---|---|---|---|---|---|
| R1-1 | `/catalog` | 1 | Four filled controls on the first screen (quiz CTA, Explorer pill, HomeFit pill, mobile "Show list" over the sheet hint) | One filled control per state: keep quiz CTA filled only until dismissed, render mode and sort as segmented tabs with outlines, move "Show list" into the sheet header | S | Med |
| R1-2 | `/search` place screen | 1 | Per-pillar "Add" and "Rerun" plus Run Score all styled primary (`PlaceView.tsx:1064,1101,1457`) | Style Add and Rerun secondary; keep one primary | S | Med |
| R2-1 | catalog, profile, quiz | 2 | Commute has 4 edit locations: profile (hub, mode, days), quiz, filter-sheet "Commute over", weights panel commute level | One home: profile. Filter sheet and weights panel show the current hub and link back; cap and level become read-through links or move into the profile commute block. Owner decision on the cap and level (G1) | M | High |
| R2-2 | `/quiz` route | 2 | Writes `filters.commuteMode` and `filters.officeDays` (`quiz/page.tsx:20-21`); catalog reads `opts.commute_mode`, `opts.office_days` and sessionStorage (`catalog-page-client.tsx:214-224`), so quiz mode and days are lost | Write the same fields the profile writes, via `saveProfile`/`persistLocal` | S | High |
| R2-3 | `/search` | 2 | Options rebuilt from a subset and written back to `homefit_search_options` (`search/page.tsx:35-50,113,176`), erasing profile mirror fields for signed-out users | Merge into existing storage object instead of replacing it | S | High |
| R2-4 | catalog, search, results, saved, quiz | 2 | Priorities edited in 4 live places with different storage (weights panel, PlaceView importance, per-card selector, quiz) | One home: the weights panel (or a shared panel component); other surfaces show weights read-only and link | L | High |
| R2-5 | `/catalog` | 2 | Metro chosen in toolbar picker and again in the filter sheet (`catalog-page-client.tsx:1373,1575`, `FilterSheet.tsx:270`) | Keep the picker; remove Metro from the sheet | S | Med |
| R2-6 | catalog, results | 2 | Life stage, political lean, scenery, built environment each edited in a filter and again in a per-card selector, stored in different fields (B rows 11 to 14) | One home per preference (the filter sheet or the weights panel); per-card selectors link back | M | Med |
| R2-7 | `/search`, `/saved/[id]` | 2 | Premium code editor in two places (`PlaceView.tsx:1341`, `saved/[id]/page.tsx:459`) | One component and one location, linked from both | S | Low |
| R2-8 | `/vacation`, `/vacation/explorer` | 2 | Trip type and traveler profile held in two unshared states | Persist once (query string or storage) and read on both | S | Med |
| R2-9 | `/quiz` | 2 | Quiz writes about 14 settings that each have their own editor (B rows 1 to 4, 9, 11, 13, 15, 16) | Owner decision: treat quiz as an initializer that writes through the same single homes, not a second home (G9) | M | Med |
| R3-1 | weights panel | 3 | Scenery, kind, school and grade chips show when the pillar is None | Render only when the pillar level is above None (`CatalogWeightPanel.tsx:218-243`) | S | Med |
| R3-2 | `/profile` | 3 | Mode and office-day chips show with no work hub; "Fastest" appears selected | Show after a hub is set; no pre-selected chip | S | Med |
| R3-3 | filter sheet | 3 | Price chip shown with no income | Hide until income exists, or show a link only | S | Med |
| R3-4 | twin finder | 3 | Four greyed controls before a neighborhood is chosen | Hide until a query is set | S | Med |
| R3-5 | catalog toolbar | 3 | "Adjust weights" dimmed to 0.4 on Longevity or Happiness | Hide it for those indexes | S | Low |
| R3-6 | `/vacation` | 3 | Search disabled until trip type, helper text, and label reads "Searching..." while disabled | Reveal the search field after trip type is chosen; fix label | S | Med |
| R3-7 | `/search`, `/vacation` | 3 | Search button greyed until text typed | Accept as standard form behaviour (owner decision) or enable always | S | Low |
| R3-8 | `/search` place screen | 3 | Run Score disabled at opacity 0.6 with nothing selected | Preselect a sensible default set so it is never inert | S | Med |
| R5-1 | twin finder | 5 | Empty search, no suggested neighborhoods | Show 4 to 6 well-known places or "your last viewed place" | S | Med |
| R5-2 | `/profile` | 5 | Income, current home and people start empty with no preset | Offer income bands and "use the place I selected" chips | M | Low |
| R5-3 | `/vacation` | 5 | No default trip type | Preselect the most common type or accept "Any" | S | Med |
| R5-4 | `/auth/callback` | 5 | Error page has no next step | Add "Back to home" and "Try signing in again" | S | Low |
| R6-1 | `/search` place and results | 6 | Weights, preferences, job categories and school scoring edited on the surface after a search | Move to the single weights and settings panels; keep search surface read-only | L | Med |

Candidate A and B FAILs are in D2 below (C5 has the detail).

### D2. Candidate A and B FAILs (counted from 2026-11-05, owner confirmed)

| ID | Screen | Rule | Violation | Recommended fix | Effort | Impact |
|---|---|---|---|---|---|---|
| CA-1 | `/catalog` list, sheet, detail | A | Scores show no basis line; HomeFit, Longevity, Happiness basis only behind `?` buttons to a separate sheet | One-line basis under each index ("12 pillars, your weights") | M | Med |
| CA-2 | `/neighborhoods/[slug]` | A | Map card says "15/15 pillars complete" while the page says "12 pillars" | Make both say the same count and what it means | S | Low |
| CB-1 | `/catalog` list, sheet, detail | B | Missing values render a dash glyph with no reason (`CatalogListView.tsx:90,118,156`, `CatalogDetailPanel.tsx:39`, `CatalogBottomSheet.tsx:40`) | Show "no data" plus reason | S | Med |
| CB-2 | `/neighborhoods/[slug]` | B | Community Safety shows `n/a` with no reason (Coconut Creek FL; `page.tsx:107,230`) | "No data" with reason | S | Med |
| CB-3 | `/saved/compare` | B | "Not scored" with no reason (`saved/compare/page.tsx:774,888`) | Add reason | S | Low |

Partial, not counted as FAIL: "Commute: N/A" reason only on hover (`CatalogListView.tsx:322-327`), and `PillarCard` "Data unavailable" (`PillarCard.tsx:447`). Level 3 still needs every number to pass A and B.


---

## E. Suspected items (not confirmed, cannot cite or reproduce)

1. Compare tray, quiz modal inside `/catalog`, and signed-in restore (`catalog-page-client.tsx:400-500`) were not rendered; any Rule 1 to 6 issue there is unknown. Compare buttons in the list were not reachable by role in my automation (they are not `button` elements), so I did not capture the tray.
2. `include_chains` defaults disagree between `search/page.tsx:46` (false) and `saved/[id]/page.tsx:144` (true) and line 363 (false). Likely affects whether a saved score re-opens with chains counted. Not run.
3. `search/page.tsx` data loss (R2-3) is code-confirmed but I did not reproduce it in a browser because the place screen needs the geocode backend. It is in D because the code is unambiguous.
4. Quiz iframe internals: I read the question list by grep of `public/quiz.html`, not by walking the flow. Primary-action styling inside the iframe (`.btn-apply` `:331`) was not captured.
5. `/saved/[id]` and `/saved/compare` signed-in screens (975 and 870 lines) were scanned by grep only.
6. Unequal "12 pillars" copy versus 15 pillar entries in `NeighborhoodMap` ("15/15 pillars complete"). The 15 may include opt-in pillars; I did not trace it.

---

## F. Proposed levels

Rule: Level 1 needs a result with evidence for every state of the screen for Rules 1 to 6 and no unaccepted FAIL, and Rule 2 clean for the screen's settings. No FAIL has an owner-accepted entry yet.

| Screen | Proposed level | The one reason it is not one level higher |
|---|---|---|
| `/catalog`, `/catalog/la` | 0 (audited, 11 FAIL rows touch it) | R2-1 and R2-4: commute and priorities each have multiple homes |
| `/profile` | 0 (audited) | R3-2 and R2-1: commute chips show without a work hub, and commute has other editors |
| `/search` | 0 (partial: place and results code-only) | R2-3 data loss plus R6-1 |
| `/results`, `/saved/[id]`, `/p/[id]` | 0 (partial) | R2-4 per-card selectors; signed-in states not run |
| `/quiz` | 0 (partial) | R2-1, R2-2, R2-9 |
| `/saved`, `/saved/compare` | 0 (partial) | Signed-in states not run (no account) |
| `/vacation`, `/vacation/explorer` | 0 (audited entry only) | R3-6, R5-3, R2-8 |
| `/neighborhoods/[slug]` | 0 (audited) | Passes Rules 1 to 6 in the states seen, but Candidate B n/a gap exists and the signed-in personal block was not run |
| `/auth/callback`, `/auth/update-password` | 0 (audited) | R5-4 on callback; update-password passes |
| **App** | **0** | Every screen must reach Level 1 first, and A3 lists 3 unreferenced components plus a dead `SearchOptions` panel to clear |

Note: `/neighborhoods/[slug]` and `/auth/update-password` have no Rule 1 to 6 FAIL in the states I rendered. They stay at Level 0 only because their signed-in or missing-data states were not all run. They are the likeliest first screens to reach Level 1.

---

## G. Recommended order of fixes (one order; each is a separate owner decision)

1. **R2-3 and R2-2 together** (S, High): stop the search page overwriting shared storage, and make `/quiz` write the fields the profile writes. Same storage object, one change set.
2. **R2-1 with R3-2** (M, High): one home for commute on the profile page; mode and days appear only after a hub; filter-sheet cap and weights-panel level link back. Group, because removing the other editors changes every surface that reads them.
3. **R3-1, R3-3, R3-4, R3-5** (S each, Med): hide dependent controls until their parent choice exists. Independent, ship in one pass.
4. **R2-5 and R1-1** (S, Med): remove the duplicate Metro control and clean the first-screen button weights on `/catalog`.
5. **R3-6, R5-3, R2-8** (S, Med): vacation flow: preselect a trip type, reveal search after it, share state with the explorer.
6. **R5-1, R5-4, R3-8, R1-2** (S, Med/Low): suggestions and dead-end fixes.
7. **R2-4, R2-6, R2-7, R6-1, R2-9** (L, High): priorities and preferences to one home, remove per-card selectors and the `PlaceView` editors. This is a design change and needs the owner to choose where the single weights home lives (G9 below). Delete the dead `SearchOptions` panel in the same change.
8. **R3-7, R5-2** (S/M, Low): polish.
9. Delete the unreferenced components (A3) with the next cleanup.

Open decisions for the owner:
- G1: commute cap and commute level, one home. The principles doc says profile only. Should the filter-sheet cap and weights-panel level stay as read-only chips that link to the profile, or move into the profile's commute block? Recommendation: keep both as read-only chips linking to the profile.
- G9: is the quiz an initializer that writes through the same single homes (recommendation), or a second home the rule allows?

---

## H. Verification statement

**Verified in code:** inventory graph (script over all imports), unreferenced component proof (grep), all default-state constants quoted in C1, every file:line in C and D, writer counts in B (greps listed under B), storage mismatch between `/quiz` and catalog, search-page overwrite, disabled and dimmed controls, missing-data render branches.

**Verified in the browser** (Chrome via Playwright against the local dev server, fresh context per capture so empty storage, signed out, no backend or API keys): `/catalog` fresh at 1280 and 375, filter sheet, weights panel (also with Natural Beauty at None), list view, place expanded, twin finder empty, `/search` entry, `/profile`, `/saved` signed out, `/vacation`, `/vacation/explorer`, `/neighborhoods/ridgewood-bergen-nj` and `coconut-creek-broward-fl`, `/results` without params, `/p/doesnotexist`, `/auth/*`, `/catalog/la`. 49 screenshots in `docs/ux_audit_screens/`.

**Not verified, and why:**
- Anything needing a signed-in account: profile save states, saved list, compare, preference restore.
- Anything needing the geocode or scoring backend or a keyed API: `/search` place and results screens, `/results` with data, `/vacation` results, `/p/[id]` real data.
- Compare tray, in-catalog quiz modal, and the quiz iframe flow (read by grep only).
- Real touch devices, assistive-technology and WCAG conformance, performance.
- The Level 2 checks: not run, by design (auditor does not grade fixes, and no fixes exist yet).
- Rule 4 PASS claims cover the default-state screens above only. They used a fresh browser context for each capture.

No contradiction between code and screenshot was found. One screenshot detail worth noting: the Natural Beauty `0%` weight in the expanded row came from my own earlier click setting it to None in that browser session, not from a default.

Nothing outside `docs/UX_AUDIT.md` and `docs/ux_audit_screens/` was modified. `npm install` was run inside `frontend/` (not tracked) and a dev server was run on port 3100 during the audit.

---

## I. Fix log

- 2026-11-05, owner approved starting with R2-3 and R2-2. Changed `frontend/app/search/page.tsx` (options now merge into the stored object instead of replacing it) and `frontend/app/quiz/page.tsx` (writes `commute_mode` and `office_days` where the profile and catalog read them, and no longer writes the unread `filters.commuteMode` and `filters.officeDays`). `tsc --noEmit` passes. Not browser-tested (the search place screen needs the backend), not committed, not pushed. Per the brief, a different agent must re-run the checks before these rows are marked fixed.

- 2026-11-05, shipped to `main` after owner approval (each built and type-checked; checked in a fresh browser where the screen renders without the backend): R2-2, R2-3 (storage); R2-1 partial, R3-1 to R3-5 (dependent controls hidden, commute edited on profile only; the commute cap and commute level stay as a filter and a priority with links back); R2-5, R1-1 (duplicate Metro removed, mode pills outlined); R3-6, R5-3, R2-8 (vacation); R5-1, R5-4, R3-8, R1-2 (suggestions, dead ends, search place buttons); R2-4 partial (results and saved views use the shared weights panel); dead `SearchOptions` panel and three unreferenced components removed; CB-1 to CB-3 ("No data" with a reason; catalog list reason is hover-only); CA-1 (one-line basis under the catalog toolbar); header (one HomeFit/TravelFit switch and one Search link, not previously a gap row). None of these is marked fixed until a different agent re-runs the checks (Level 2).

### Owner-accepted limits

- 2026-11-05, R2-6 (live-scoring card selectors): the scenery, built-environment, life-stage and chain-business selectors on result and saved cards stay on the card. They are inputs to that one live-scored number and trigger a rescore of it, so they are accepted as an exception to Rule 2. The catalog side keeps the weights panel and filter sheet as its homes.

- 2026-11-05 to 2026-11-06, shipped to `main` after owner approval, each type-checked and built: Filters and Priorities (Filters sheet hides places, Priorities panel ranks; one-line explainer on each; same right-side drawer on desktop; "Hide places with" choices sit under their own priority; count badges; Reset priorities), R6-1 partial (catalog side only); polish batch: R3-7 (search button always enabled, empty submit focuses the input), R5-2 partial (income quick picks on the profile), mobile "Show list" no longer overlaps the bottom sheet, live-progress badge removed on stored places. Still not marked fixed until a different agent re-runs the checks (Level 2).

- 2026-11-09, R1-1 (two filled controls on the first catalog screen): the owner ruled the active purple sort pill is a selected state, not a second primary action. Accepted, counts as PASS.
- 2026-11-09, R2-1 (commute cap in the Filters sheet and commute level in Priorities stay editable, each with a link to the profile): the owner accepted this as an exception to Rule 2.

- 2026-11-09, Compare score parity (found by the owner, not by the audit): "Your HomeFit" in Compare did not match the Explorer when a work address, commute mode, office days or people were set, because Compare never received those inputs or added the commute and social pillars. Fixed and merged to `main` (9e3ecf96). The audit missed it because it checked controls and copy, not whether one place shows the same personal score on every screen. New Level 2 check, added after results: for one place and one set of inputs (weights, income, work address, commute mode, office days, people, school and scenery filters), the personal HomeFit score must be identical on the Explorer map, the detail panel, the list, Compare and the saved view. Not yet run end to end (the Compare page did not load in the test browser; the pillar function was checked directly).

### Still open

R2-4 and R6-1 (search place screen importance buttons and weights, preferences and settings editing after a search), R2-7 (premium code in two places), R2-9 (quiz as initializer, treated as such), CA-2 (15 vs 12 pillars copy), signed-in and backend-only screens not rendered (saved, compare, in-catalog quiz modal). Level 2 re-check by a different agent has not run; the owner paused it on 2026-11-05 until all pillars are DPv2 L2 certified.

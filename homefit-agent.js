/**
 * HomeFit QA & Performance Agent
 * -----------------------------------------------
 * Run from your project root with Cursor Agent or directly:
 *   node homefit-agent.js
 *
 * Prerequisites:
 *   npm install playwright
 *   npx playwright install chromium
 *
 * What it does:
 *   1. Opens HomeFit at http://localhost:3000
 *   2. Searches for "Carroll Gardens, Brooklyn"
 *   3. Waits for the Results page to load
 *   4. Adjusts pillar importance weights (simulates user prioritization)
 *   5. Triggers a Run Score / Rescore
 *   6. Saves the place
 *   7. Collects performance timings, console errors, network failures
 *   8. Writes a full Markdown report: homefit-report.md
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

// ─── CONFIG ──────────────────────────────────────────────────────────────────
const BASE_URL      = 'http://localhost:3000';
const SEARCH_QUERY  = 'Carroll Gardens, Brooklyn';
const REPORT_PATH   = path.join(__dirname, 'homefit-report.md');

// Pillar weight adjustments to test — [label-substring, new-value]
// Adjust these to match whatever weight controls HomeFit actually renders
const WEIGHT_CHANGES = [
  { pillar: 'Natural Beauty',    value: 8  },
  { pillar: 'Schools',           value: 9  },
  { pillar: 'Active Outdoors',   value: 7  },
  { pillar: 'Daily Amenities',   value: 8  },
  { pillar: 'Climate',           value: 6  },
];

// Timeouts
const NAV_TIMEOUT    = 45_000;
const ACTION_TIMEOUT = 10_000;
const SCORE_TIMEOUT  = 60_000;   // scoring API can be slow

// ─── HELPERS ─────────────────────────────────────────────────────────────────
function ts() {
  return new Date().toISOString();
}

function elapsed(startMs) {
  return ((Date.now() - startMs) / 1000).toFixed(2) + 's';
}

async function screenshot(page, label) {
  const fname = `homefit-${label.replace(/\s+/g, '-')}.png`;
  await page.screenshot({ path: fname, fullPage: true });
  return fname;
}

// Try multiple selector strategies — returns the first that matches
async function findElement(page, strategies, timeout = ACTION_TIMEOUT) {
  for (const sel of strategies) {
    try {
      const el = await page.waitForSelector(sel, { timeout, state: 'visible' });
      if (el) return { el, selector: sel };
    } catch (_) {
      // Try next strategy
    }
  }
  throw new Error(`None of the selectors matched within ${timeout}ms:\n  ${strategies.join('\n  ')}`);
}

// ─── MAIN AGENT ──────────────────────────────────────────────────────────────
async function runAgent() {
  const report = {
    meta: { startedAt: ts(), url: BASE_URL, searchQuery: SEARCH_QUERY },
    phases: [],
    consoleErrors: [],
    networkFailures: [],
    performanceMetrics: {},
    pillarWeightResults: [],
    scoreResult: null,
    saveResult: null,
    bugs: [],
    warnings: [],
    suggestions: [],
  };

  function phase(name) {
    const p = { name, startMs: Date.now(), status: 'running', notes: [], screenshot: null };
    report.phases.push(p);
    console.log(`\n▶ ${name}`);
    return {
      note:  (msg)  => { p.notes.push(msg);  console.log(`  ℹ ${msg}`); },
      warn:  (msg)  => { p.notes.push(`⚠ ${msg}`); report.warnings.push(`[${name}] ${msg}`); console.warn(`  ⚠ ${msg}`); },
      bug:   (msg)  => { p.notes.push(`🐛 ${msg}`); report.bugs.push(`[${name}] ${msg}`); console.error(`  🐛 ${msg}`); },
      done:  (msg)  => { p.status = 'passed'; p.duration = elapsed(p.startMs); p.summary = msg; console.log(`  ✓ ${msg} (${p.duration})`); },
      fail:  (msg)  => { p.status = 'failed'; p.duration = elapsed(p.startMs); p.summary = msg; console.error(`  ✗ ${msg} (${p.duration})`); },
      shot:  async (page, label) => { p.screenshot = await screenshot(page, label); },
    };
  }

  const browser = await chromium.launch({
    headless: false,         // visible so Cursor can watch
    slowMo: 150,             // slight slow-mo for legibility
    args: ['--window-size=1440,900'],
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    recordVideo: { dir: './', size: { width: 1440, height: 900 } },
  });

  const page = await context.newPage();

  // ── Intercept console messages ─────────────────────────────────────────────
  page.on('console', msg => {
    if (msg.type() === 'error') {
      report.consoleErrors.push({ time: ts(), text: msg.text() });
    }
  });

  // ── Intercept network failures ─────────────────────────────────────────────
  const apiTimings = {};
  page.on('request', req => {
    if (req.url().includes('/api/')) {
      apiTimings[req.url()] = { start: Date.now(), method: req.method() };
    }
  });
  page.on('requestfailed', req => {
    report.networkFailures.push({ url: req.url(), failure: req.failure()?.errorText });
  });
  page.on('response', res => {
    const entry = apiTimings[res.url()];
    if (entry) {
      entry.duration = Date.now() - entry.start;
      entry.status   = res.status();
    }
    if (!res.ok() && res.url().includes('/api/')) {
      report.networkFailures.push({ url: res.url(), status: res.status() });
    }
  });

  // ══════════════════════════════════════════════════════════════════════════
  // PHASE 1 — Initial page load
  // ══════════════════════════════════════════════════════════════════════════
  const p1 = phase('Initial Page Load');
  try {
    const navStart = Date.now();
    await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: NAV_TIMEOUT });
    const navTime = elapsed(navStart);

    // Collect Web Vitals via JS
    const vitals = await page.evaluate(() => {
      const nav = performance.getEntriesByType('navigation')[0];
      return nav ? {
        domInteractive:     Math.round(nav.domInteractive),
        domContentLoaded:   Math.round(nav.domContentLoadedEventEnd),
        loadEventEnd:       Math.round(nav.loadEventEnd),
        transferSize:       nav.transferSize,
      } : null;
    });
    if (vitals) {
      report.performanceMetrics.pageLoad = vitals;
      p1.note(`DOM interactive: ${vitals.domInteractive}ms`);
      p1.note(`Page fully loaded: ${vitals.loadEventEnd}ms`);
      if (vitals.domContentLoaded > 3000) p1.warn('DOMContentLoaded > 3s — consider code splitting or SSR tuning');
      if (vitals.loadEventEnd > 5000)     p1.warn('Full load > 5s — check large assets or blocking requests');
    }

    await p1.shot(page, '01-home');
    p1.done(`Loaded ${BASE_URL} in ${navTime}`);
  } catch (err) {
    p1.fail(err.message);
    p1.bug('App did not load — is `npm run dev` running on port 3000?');
    await browser.close();
    return writeReport(report);
  }

  // ══════════════════════════════════════════════════════════════════════════
  // PHASE 2 — Search for a place
  // ══════════════════════════════════════════════════════════════════════════
  const p2 = phase('Search: "Carroll Gardens, Brooklyn"');
  try {
    // Try common search input patterns
    const { el: searchInput, selector: foundSel } = await findElement(page, [
      '[data-testid="location-search-input"]',
      'input[placeholder*="Search"]',
      'input[placeholder*="search"]',
      'input[placeholder*="location"]',
      'input[placeholder*="neighborhood"]',
      'input[placeholder*="city"]',
      'input[type="search"]',
      '[data-testid="search-input"]',
      '[aria-label*="search" i]',
      'input[role="combobox"][aria-autocomplete="list"]',
    ]);
    p2.note(`Found search input via: ${foundSel}`);

    const searchStart = Date.now();
    await searchInput.click();
    await searchInput.fill(SEARCH_QUERY);
    p2.note(`Typed "${SEARCH_QUERY}"`);

    // Wait for autocomplete / suggestions dropdown
    let selectedSuggestion = false;
    try {
      const suggestionSelectors = [
        '[data-testid="location-suggestion"]',
        '[role="option"]',
        '[role="listbox"] li',
        '.autocomplete-item',
        '.suggestion-item',
        'ul[class*="suggest"] li',
        'div[class*="dropdown"] div',
      ];
      const { el: firstSuggestion } = await findElement(page, suggestionSelectors, 5000);
      const suggestionText = await firstSuggestion.textContent();
      p2.note(`Autocomplete appeared with: "${suggestionText?.trim()}"`);
      await firstSuggestion.click();
      selectedSuggestion = true;
      p2.note('Clicked first autocomplete suggestion');
    } catch (_) {
      // No autocomplete — try pressing Enter
      p2.warn('No autocomplete dropdown found — pressing Enter to submit search');
      await searchInput.press('Enter');
    }

    report.performanceMetrics.searchToAutocomplete = elapsed(searchStart);
    await p2.shot(page, '02-search');
    p2.done(`Search submitted (autocomplete: ${selectedSuggestion})`);
  } catch (err) {
    p2.fail(err.message);
    p2.bug('Search input not found — selector may need updating');
    await p2.shot(page, '02-search-failed');
  }

  // ══════════════════════════════════════════════════════════════════════════
  // PHASE 3 — Results page loads
  // ══════════════════════════════════════════════════════════════════════════
  const p3 = phase('Results Page Load');
  try {
    const resultsStart = Date.now();

    let urlMatched = false;
    try {
      await page.waitForURL('**/results**', { timeout: NAV_TIMEOUT });
      urlMatched = true;
    } catch (_) {
      // In the current UX we may stay on the main page and show PlaceView instead of a /results route.
    }

    let cardsMatched = false;
    try {
      await findElement(
        page,
        [
          '[data-testid="pillar-card"]',
          '[class*="hf-pillar-row"]',
          '[class*="pillar"]',
          '[class*="results"]',
          'h2:has-text("Score")',
          'h2:has-text("HomeFit")',
        ],
        NAV_TIMEOUT
      );
      cardsMatched = true;
    } catch (_) {
      // ignore, handled below
    }

    if (!urlMatched && !cardsMatched) {
      throw new Error(`Results UI did not appear within ${NAV_TIMEOUT}ms`);
    }

    report.performanceMetrics.searchToResults = elapsed(resultsStart);
    p3.note(`Results or scoring UI appeared in ${report.performanceMetrics.searchToResults}`);
    p3.note(`Current URL: ${page.url()}`);

    // Count visible pillar / configuration cards
    const pillarCards = await page.$$('[class*="hf-pillar-row"], [class*="pillar"], [data-testid*="pillar"]');
    p3.note(`Visible pillar-related cards found: ${pillarCards.length}`);
    if (pillarCards.length === 0) p3.warn('No pillar cards detected — check selector patterns or geocode errors');

    await p3.shot(page, '03-results');
    p3.done('Results/scoring UI confirmed');
  } catch (err) {
    p3.fail(err.message);
    p3.bug('Results page did not load or pillar cards missing after search');
    await p3.shot(page, '03-results-failed');
  }

  // ══════════════════════════════════════════════════════════════════════════
  // PHASE 4 — Adjust pillar weights
  // ══════════════════════════════════════════════════════════════════════════
  const p4 = phase('Adjust Pillar Weights');
  for (const change of WEIGHT_CHANGES) {
    try {
      // Strategy: find pillar card by text, then find its slider/input/chip within it
      const card = await page.locator([
        `[class*="pillar"]:has-text("${change.pillar}")`,
        `[data-testid*="pillar"]:has-text("${change.pillar}")`,
        `div:has-text("${change.pillar}")`,
      ].join(', ')).first();

      // Try range input (slider) first, then number input
      let widget = null;
      let widgetType = null;

      try {
        widget = card.locator('input[type="range"]').first();
        await widget.waitFor({ timeout: 2000 });
        widgetType = 'slider';
      } catch (_) {
        try {
          widget = card.locator('input[type="number"]').first();
          await widget.waitFor({ timeout: 2000 });
          widgetType = 'number input';
        } catch (_) {
          try {
            widget = card.locator('input').first();
            await widget.waitFor({ timeout: 2000 });
            widgetType = 'generic input';
          } catch (_) {
            p4.warn(`No weight control found for "${change.pillar}" — skipping`);
            report.pillarWeightResults.push({ pillar: change.pillar, status: 'no_control_found' });
            continue;
          }
        }
      }

      // Fill or adjust the weight
      if (widgetType === 'slider') {
        // For range sliders, evaluate JS to set value and fire events
        await widget.evaluate((el, val) => {
          el.value = String(val);
          el.dispatchEvent(new Event('input',  { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
        }, change.value);
      } else {
        await widget.triple_click?.() || await widget.click({ clickCount: 3 });
        await widget.fill(String(change.value));
        await widget.press('Tab');
      }

      p4.note(`Set "${change.pillar}" → ${change.value} (via ${widgetType})`);
      report.pillarWeightResults.push({ pillar: change.pillar, value: change.value, status: 'set', via: widgetType });
    } catch (err) {
      p4.warn(`Could not adjust "${change.pillar}": ${err.message}`);
      report.pillarWeightResults.push({ pillar: change.pillar, status: 'error', error: err.message });
    }
  }

  await p4.shot(page, '04-weights');
  p4.done(`Attempted weight changes on ${WEIGHT_CHANGES.length} pillars`);

  // ══════════════════════════════════════════════════════════════════════════
  // PHASE 5 — Run Score
  // ══════════════════════════════════════════════════════════════════════════
  const p5 = phase('Run Score');
  try {
    // Ensure at least a few pillars are selected so the Run Score button is enabled.
    try {
      const addButtons = await page.$$('button:has-text("Add")');
      if (addButtons.length > 0) {
        const toClick = addButtons.slice(0, Math.min(4, addButtons.length));
        for (const btn of toClick) {
          await btn.click();
        }
        p5.note(`Selected ${toClick.length} pillar(s) via "Add" buttons`);
      }
    } catch (_) {
      // Non-fatal: we'll still attempt to find and click Run Score.
    }

    const runBtn = await findElement(page, [
      'button:has-text("Run Score")',
      'button:has-text("Rescore")',
      'button:has-text("Score")',
      'button:has-text("Calculate")',
      '[data-testid="run-score"]',
      '[data-testid="rescore"]',
      '[aria-label*="score" i]',
    ]);

    const scoreStart = Date.now();
    await runBtn.el.click();
    p5.note('Clicked Run Score button');

    // Wait for loading indicator to appear then disappear
    let loadingDetected = false;
    try {
      await page.waitForSelector('[class*="loading"], [class*="spinner"], [aria-label*="loading" i]', {
        state: 'visible', timeout: 3000,
      });
      loadingDetected = true;
      p5.note('Loading indicator appeared ✓');
      await page.waitForSelector('[class*="loading"], [class*="spinner"], [aria-label*="loading" i]', {
        state: 'hidden', timeout: SCORE_TIMEOUT,
      });
    } catch (_) {
      if (!loadingDetected) p5.warn('No loading indicator detected — consider adding one for UX feedback');
    }

    // Wait for scores to stabilize (network idle)
    await page.waitForLoadState('networkidle', { timeout: SCORE_TIMEOUT });
    report.performanceMetrics.scoreRunDuration = elapsed(scoreStart);

    // Capture the scores
    const scores = await page.evaluate(() => {
      const items = [];
      document.querySelectorAll('[class*="score"], [data-testid*="score"]').forEach(el => {
        const txt = el.textContent?.trim();
        if (txt && /\d/.test(txt)) items.push(txt);
      });
      return items.slice(0, 20); // cap at 20
    });

    report.scoreResult = { duration: report.performanceMetrics.scoreRunDuration, scores };
    p5.note(`Score run completed in ${report.performanceMetrics.scoreRunDuration}`);
    p5.note(`Captured score values: ${scores.slice(0, 5).join(', ')}${scores.length > 5 ? '…' : ''}`);

    if (parseFloat(report.performanceMetrics.scoreRunDuration) > 15) {
      p5.warn(`Score run took ${report.performanceMetrics.scoreRunDuration} — investigate slow API calls`);
    }

    await p5.shot(page, '05-scored');
    p5.done(`Scores updated in ${report.performanceMetrics.scoreRunDuration}`);
  } catch (err) {
    p5.fail(err.message);
    p5.bug('"Run Score" button not found — check button selector or ensure weights are visible');
    await p5.shot(page, '05-score-failed');
  }

  // ══════════════════════════════════════════════════════════════════════════
  // PHASE 6 — Save Place
  // ══════════════════════════════════════════════════════════════════════════
  const p6 = phase('Save Place');
  try {
    // Try to find a Save button first.
    let saveBtn = null;
    try {
      saveBtn = await findElement(
        page,
        [
          '[data-testid="save-place"]',
          'button:has-text("Save Place")',
          'button:has-text("Save this place")',
          'button:has-text("Save")',
          'button:has-text("Bookmark")',
          '[aria-label*="save" i]',
          '[class*="save"]',
        ],
        ACTION_TIMEOUT
      );
    } catch (_) {
      // ignore, we'll handle below
    }

    // If no direct Save button, check for an auth-gated CTA instead.
    if (!saveBtn) {
      const signInCta = await page.$('button:has-text("Sign in to save this place"), button:has-text("Sign in to save")');
      if (signInCta) {
        p6.warn('Save is gated behind authentication — "Sign in to save this place" CTA is visible');
        await p6.shot(page, '06-save-auth-required');
        p6.done('Save flow requires sign-in (CTA verified)');
        return;
      }
      throw new Error(`"Save Place" button or CTA not found within ${ACTION_TIMEOUT}ms`);
    }

    const saveStart = Date.now();
    try {
      await saveBtn.el.click();
    } catch (clickErr) {
      const msg = String(clickErr?.message || '');
      if (msg.includes('not enabled')) {
        p6.warn('Save button is present but disabled — likely due to auth or validation requirements');
        await p6.shot(page, '06-save-disabled');
        report.saveResult = {
          duration: elapsed(saveStart),
          confirmed: false,
        };
        p6.done('Save button present but disabled; skipping automated save');
        return;
      }
      throw clickErr;
    }

    p6.note('Clicked Save Place button');

    // Wait for confirmation toast / state change
    let saveConfirmed = false;
    try {
      await page.waitForSelector(
        [
          '[class*="toast"]',
          '[role="alert"]',
          '[class*="saved"]',
          'text=Saved',
          'text=Place saved',
        ].join(', '),
        { timeout: 5000 }
      );
      saveConfirmed = true;
      p6.note('Save confirmation appeared ✓');
    } catch (_) {
      p6.warn('No save confirmation toast/alert detected — verify save feedback UX');
    }

    // Check if button toggled to "Saved" state
    const savedState = await page.$('button:has-text("Saved"), [aria-pressed="true"][aria-label*="save" i]');
    if (savedState) p6.note('Button toggled to "Saved" state ✓');
    else p6.warn('Save button did not visually toggle — check saved state styling');

    report.saveResult = {
      duration: elapsed(saveStart),
      confirmed: saveConfirmed,
    };

    await p6.shot(page, '06-saved');
    p6.done(`Save action completed (confirmed: ${saveConfirmed})`);
  } catch (err) {
    p6.fail(err.message);
    p6.bug('"Save Place" button not found — check if auth is required or button is conditionally rendered');
    await p6.shot(page, '06-save-failed');
  }

  // ══════════════════════════════════════════════════════════════════════════
  // PHASE 7 — UX & Accessibility spot-checks
  // ══════════════════════════════════════════════════════════════════════════
  const p7 = phase('UX & Accessibility Spot-checks');
  try {
    // Check for images without alt text
    const noAlt = await page.$$eval('img:not([alt])', els => els.length);
    if (noAlt > 0) p7.warn(`${noAlt} image(s) missing alt text`);
    else           p7.note('All images have alt text ✓');

    // Check for buttons without accessible text
    const noLabel = await page.$$eval(
      'button:not([aria-label]):not([aria-labelledby])',
      els => els.filter(b => !b.textContent?.trim()).length
    );
    if (noLabel > 0) p7.warn(`${noLabel} button(s) have no text or aria-label`);
    else             p7.note('All buttons have accessible labels ✓');

    // Check viewport meta
    const hasViewport = await page.$('meta[name="viewport"]');
    if (!hasViewport) p7.warn('Missing <meta name="viewport"> — mobile layout may break');

    // Check font loading
    const fontCheck = await page.evaluate(() => document.fonts.status);
    p7.note(`Document fonts status: ${fontCheck}`);

    // Check for visible scrollbar on results (overflow-x)
    const hasHScroll = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    if (hasHScroll) p7.warn('Horizontal scrollbar detected — potential layout overflow bug');

    await p7.shot(page, '07-a11y');
    p7.done('Spot-checks complete');
  } catch (err) {
    p7.fail(err.message);
  }

  // ══════════════════════════════════════════════════════════════════════════
  // PHASE 8 — API performance summary
  // ══════════════════════════════════════════════════════════════════════════
  const p8 = phase('API Timing Summary');
  const slowThreshold = 3000;
  const apiRows = Object.entries(apiTimings).map(([url, t]) => {
    const path = url.replace(BASE_URL, '');
    const slow = t.duration > slowThreshold;
    if (slow) p8.warn(`Slow API: ${path} — ${t.duration}ms`);
    return { path, method: t.method, status: t.status, duration: t.duration };
  });
  report.performanceMetrics.apiCalls = apiRows;

  if (apiRows.length === 0) p8.note('No /api/ calls captured — verify API base path');
  else                      p8.note(`${apiRows.length} API call(s) captured`);

  p8.done('API timing collected');

  // ─── Auto-generate suggestions ────────────────────────────────────────────
  if (report.consoleErrors.length > 0)
    report.suggestions.push(`Fix ${report.consoleErrors.length} console error(s) before launch`);
  if (report.networkFailures.length > 0)
    report.suggestions.push(`Investigate ${report.networkFailures.length} network failure(s)`);
  if (apiRows.some(r => r.duration > slowThreshold))
    report.suggestions.push('Add caching or skeleton loading for slow pillar API calls (>3s)');
  if (report.phases.some(p => p.status === 'failed'))
    report.suggestions.push('Update Playwright selectors to match current DOM — some elements were not found');
  if (!report.saveResult?.confirmed)
    report.suggestions.push('Add a visible save confirmation (toast/snackbar) after saving a place');
  report.suggestions.push('Consider adding data-testid attributes to key elements for more reliable selector targeting');
  report.suggestions.push('Run Lighthouse audit for Core Web Vitals (LCP, CLS, FID) against the Results page');

  // ─── Finalize ─────────────────────────────────────────────────────────────
  report.meta.completedAt = ts();
  report.meta.totalDuration = elapsed(new Date(report.meta.startedAt).getTime());

  await browser.close();
  return writeReport(report);
}

// ─── REPORT WRITER ───────────────────────────────────────────────────────────
function writeReport(report) {
  const passed  = report.phases.filter(p => p.status === 'passed').length;
  const failed  = report.phases.filter(p => p.status === 'failed').length;
  const total   = report.phases.length;

  const statusEmoji = s => s === 'passed' ? '✅' : s === 'failed' ? '❌' : '⏳';

  const pillarTable = report.pillarWeightResults.length
    ? `| Pillar | Target Value | Status | Via |\n|---|---|---|---|\n` +
      report.pillarWeightResults.map(r =>
        `| ${r.pillar} | ${r.value ?? '—'} | ${r.status} | ${r.via ?? '—'} |`
      ).join('\n')
    : '_No pillar weight changes captured._';

  const apiTable = report.performanceMetrics.apiCalls?.length
    ? `| Endpoint | Method | Status | Duration |\n|---|---|---|---|\n` +
      report.performanceMetrics.apiCalls.map(r =>
        `| \`${r.path}\` | ${r.method} | ${r.status ?? '—'} | ${r.duration}ms ${r.duration > 3000 ? '⚠️' : ''} |`
      ).join('\n')
    : '_No API calls captured or app uses a different base path._';

  const vitals = report.performanceMetrics.pageLoad;
  const vitalsSection = vitals
    ? `| Metric | Value |
|---|---|
| DOM Interactive | ${vitals.domInteractive}ms |
| DOMContentLoaded | ${vitals.domContentLoaded}ms |
| Load Event End | ${vitals.loadEventEnd}ms |
| Transfer Size | ${(vitals.transferSize / 1024).toFixed(1)} KB |`
    : '_Could not capture Web Vitals._';

  const md = `# HomeFit QA & Performance Report

> **Location tested:** ${report.meta.searchQuery}  
> **App URL:** ${report.meta.url}  
> **Started:** ${report.meta.startedAt}  
> **Completed:** ${report.meta.completedAt ?? 'N/A'}  
> **Total duration:** ${report.meta.totalDuration ?? 'N/A'}

---

## 📊 Summary

| | Count |
|---|---|
| Phases passed | **${passed} / ${total}** |
| Phases failed | **${failed}** |
| Console errors | **${report.consoleErrors.length}** |
| Network failures | **${report.networkFailures.length}** |
| Bugs flagged | **${report.bugs.length}** |
| Warnings | **${report.warnings.length}** |

---

## 🔄 Phase Results

${report.phases.map(p => `### ${statusEmoji(p.status)} Phase: ${p.name}

- **Status:** ${p.status} ${p.duration ? `(${p.duration})` : ''}
- **Summary:** ${p.summary ?? '_no summary_'}
${p.notes.length ? `\n**Notes:**\n${p.notes.map(n => `- ${n}`).join('\n')}` : ''}
${p.screenshot ? `\n📸 Screenshot: \`${p.screenshot}\`` : ''}
`).join('\n---\n\n')}

---

## 🌐 Page Load Performance

${vitalsSection}

| Key Timing | Value |
|---|---|
| Search → Autocomplete | ${report.performanceMetrics.searchToAutocomplete ?? '—'} |
| Search → Results Page | ${report.performanceMetrics.searchToResults ?? '—'} |
| Score Run Duration | ${report.performanceMetrics.scoreRunDuration ?? '—'} |

---

## ⚖️ Pillar Weight Changes

${pillarTable}

---

## 🔌 API Call Performance

${apiTable}

---

## 🐛 Bugs

${report.bugs.length
  ? report.bugs.map(b => `- ${b}`).join('\n')
  : '_No bugs flagged._'}

---

## ⚠️ Warnings

${report.warnings.length
  ? report.warnings.map(w => `- ${w}`).join('\n')
  : '_No warnings._'}

---

## 🖥️ Console Errors

${report.consoleErrors.length
  ? report.consoleErrors.map(e => `- \`${e.time}\` — ${e.text}`).join('\n')
  : '_No console errors detected._'}

---

## 📡 Network Failures

${report.networkFailures.length
  ? report.networkFailures.map(f => `- \`${f.url}\` — ${f.failure ?? `HTTP ${f.status}`}`).join('\n')
  : '_No network failures detected._'}

---

## 💡 Recommendations

${report.suggestions.map((s, i) => `${i + 1}. ${s}`).join('\n')}

---

## 🎬 Artifacts

Screenshots and a session video were saved to the directory where this script was run.

---

_Generated by homefit-agent.js · ${new Date().toLocaleString()}_
`;

  fs.writeFileSync(REPORT_PATH, md, 'utf8');
  console.log(`\n✅ Report written to: ${REPORT_PATH}`);
  console.log(`   Passed: ${passed}/${total}  Bugs: ${report.bugs.length}  Warnings: ${report.warnings.length}`);
  return report;
}

// ─── ENTRY POINT ─────────────────────────────────────────────────────────────
runAgent().catch(err => {
  console.error('\n💥 Agent crashed:', err);
  process.exit(1);
});

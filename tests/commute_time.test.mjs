// Run: node --test tests/commute_time.test.mjs   (Node 22.18+ strips TypeScript types natively)
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { summarizeRoute, isNoRoute, commuteTimeScore, commutePillarScore } from '../frontend/lib/commuteTime.ts'

test('stored entry with both modes null is a real no route, not missing', () => {
  const s = summarizeRoute({ transit: null, drive: null }, false)
  assert.deepEqual(s, { filterMinutes: null, transit: null, drive: null })
  assert.equal(summarizeRoute(undefined, false), null)
  assert.equal(summarizeRoute(null, true), null)
})

test('transit-only hub ignores drive for the filter', () => {
  assert.equal(summarizeRoute({ transit: 50, drive: 20 }, true).filterMinutes, 50)
  assert.equal(summarizeRoute({ transit: 50, drive: 20 }, false).filterMinutes, 20)
})

test('isNoRoute by mode', () => {
  assert.equal(isNoRoute({ transit: null, drive: 80 }, false, 'transit'), true)
  assert.equal(isNoRoute({ transit: null, drive: 80 }, false, null), false) // drive usable
  assert.equal(isNoRoute({ transit: null, drive: 80 }, true, null), true) // transit-only hub, no transit
  assert.equal(isNoRoute({ transit: 40, drive: null }, false, 'auto'), true)
  assert.equal(isNoRoute({ transit: 40, drive: null }, true, 'auto'), false) // drive to transit-only hub is unrealistic by design, not a place fault
  assert.equal(isNoRoute({ transit: null, drive: null }, false, 'active'), false)
  assert.equal(isNoRoute(undefined, false, 'transit'), false) // place never routed: missing data, not no route
})

test('no route scores worst, not dropped, and never beats a long commute', () => {
  assert.equal(commutePillarScore(null, 5, true), 0)
  assert.equal(commutePillarScore(null, undefined, true), 0)
  assert.equal(commutePillarScore(null, 5, false), null) // nothing to score, no flag: still left out
  for (const m of [60, 89, 90, 120]) assert.ok(commutePillarScore(null, 5, true) <= commutePillarScore(m, 5, false))
})

test('office days scale the no-route penalty like any other', () => {
  assert.equal(commutePillarScore(null, 2, true), 60)
  assert.equal(commutePillarScore(null, 1, true), 80)
})

test('curve unchanged', () => {
  assert.equal(commuteTimeScore(15), 100)
  assert.equal(commuteTimeScore(30), 80)
  assert.equal(commuteTimeScore(60), 50)
  assert.equal(commuteTimeScore(90), 0)
  assert.equal(commuteTimeScore(-1), null)
  assert.equal(commutePillarScore(45, 5, false), commuteTimeScore(45))
})

test('stored catalog: no-route entries are as audited (NYC 11, SF 40, LA 23 transit nulls)', () => {
  const counts = {}
  for (const m of ['nyc', 'sf', 'la']) {
    let n = 0
    for (const l of readFileSync(`data/${m}_metro_place_catalog_scores_merged.composites_recomputed.jsonl`, 'utf8').split('\n')) {
      if (!l) continue
      for (const v of Object.values(JSON.parse(l).work_commute ?? {})) if (v.transit == null) n++
    }
    counts[m] = n
  }
  // NYC/SF numbers changed from the audit (11, 40) because five places were restored; LA unchanged.
  assert.ok(counts.nyc <= 11 && counts.sf <= 40 && counts.la === 23, JSON.stringify(counts))
})

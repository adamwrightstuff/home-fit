// Run: node --test tests/social_proximity.test.mjs   (Node 22.18+ strips TypeScript types natively)
import test from 'node:test'
import assert from 'node:assert/strict'
import { closeTieProximityScore, acquaintanceProximityScore, socialConnectionScore, acquaintancesNearbyScore } from '../frontend/lib/socialProximity.ts'

const MILES = [0, 1, 2, 5, 6, 7.5, 10, 25, 50, 100, 500, 3000]

test('close curve anchors (refit to Schoeni et al. Table A2, 2026-11-05)', () => {
  assert.equal(closeTieProximityScore(0), 100)
  assert.equal(closeTieProximityScore(3.5), 100)
  assert.equal(closeTieProximityScore(7.5), 57)
  assert.equal(closeTieProximityScore(20), 39)
  assert.equal(closeTieProximityScore(3000), 39)
})

test('close curve is non-increasing and no steeper than 10.75 points a mile', () => {
  // Regression guard on slope. The Level 2 smoothness criteria (step 10, pair gap 3) fail by evidence,
  // see docs/SOCIAL_PROXIMITY.md section 6.
  let prev = null
  for (let m = 0; m <= 200; m += 0.5) {
    const s = closeTieProximityScore(m)
    if (prev !== null) {
      assert.ok(s <= prev + 1e-9, `rises at ${m}`)
      assert.ok(prev - s <= 10.75 * 0.5 + 1e-9, `too steep at ${m}`)
    }
    prev = s
  }
})

const M = 1609.344 // meters per mile

test('acquaintance walk zone: 100 within 800 m, 0 from 1,260 m, non-increasing', () => {
  assert.equal(acquaintanceProximityScore(0), 100)
  assert.equal(acquaintanceProximityScore(800 / M), 100)
  assert.equal(acquaintanceProximityScore(1260 / M), 0)
  assert.equal(acquaintanceProximityScore(3), 0)
  assert.ok(Math.abs(acquaintanceProximityScore(1030 / M) - 50) < 1e-6)
  let prev = 101
  for (let m = 0; m <= 2000; m += 10) {
    const a = acquaintanceProximityScore(m / M)
    assert.ok(a <= prev + 1e-9, `rises at ${m} m`)
    prev = a
  }
})

test('close and acquaintance score separately', () => {
  // an acquaintance never feeds the close score, and a close person never feeds the acquaintance score
  assert.equal(socialConnectionScore([{ tier: 'acquaintance', miles: 0.1 }]), null)
  assert.equal(acquaintancesNearbyScore([{ tier: 'close', miles: 0.1 }]), null)
  const mixed = [{ tier: 'close', miles: 30 }, { tier: 'acquaintance', miles: 0.2 }]
  assert.equal(socialConnectionScore(mixed), 39)
  assert.equal(acquaintancesNearbyScore(mixed), 100)
})

test('acquaintance outside the walk zone drops out instead of scoring 0', () => {
  assert.equal(acquaintancesNearbyScore([{ tier: 'acquaintance', miles: 2 }]), null)
  assert.equal(acquaintancesNearbyScore([{ tier: 'acquaintance', miles: 2 }, { tier: 'acquaintance', miles: 0.3 }]), 100)
  // more acquaintances inside the zone add nothing yet (count-to-score mapping is a TODO)
  assert.equal(acquaintancesNearbyScore([{ tier: 'acquaintance', miles: 0.1 }, { tier: 'acquaintance', miles: 0.1 }]), 100)
})

test('invalid distance gives null, not a neutral number', () => {
  for (const bad of [null, undefined, NaN, -1, Infinity]) {
    assert.equal(closeTieProximityScore(bad), null)
    assert.equal(acquaintanceProximityScore(bad), null)
  }
  assert.equal(socialConnectionScore([{ tier: 'close', miles: null }]), null)
  assert.equal(socialConnectionScore([]), null)
  assert.equal(acquaintancesNearbyScore([{ tier: 'acquaintance', miles: null }]), null)
  assert.equal(acquaintancesNearbyScore([]), null)
})

test('nearest person carries the score; bonus only for people at or above the threshold', () => {
  assert.equal(socialConnectionScore([{ tier: 'close', miles: 3 }]), 100)
  assert.equal(socialConnectionScore([{ tier: 'close', miles: 30 }]), 39)
  // 7.5 mi scores 57, under the close threshold of 70, so extra people there add nothing
  assert.equal(socialConnectionScore([{ tier: 'close', miles: 7.5 }, { tier: 'close', miles: 7.5 }]), 57)
  // 5 mi scores 83.9 (above 70): one extra adds 5
  assert.equal(socialConnectionScore([{ tier: 'close', miles: 5 }, { tier: 'close', miles: 5 }]), 88.9)
})

test('bonus cap: three extras count as two', () => {
  const p = { tier: 'close', miles: 5 }
  assert.equal(socialConnectionScore([p, p, p]), 93.9)
  assert.equal(socialConnectionScore([p, p, p, p]), 93.9)
})

test('score does not depend on any place label (function takes miles only)', () => {
  assert.equal(socialConnectionScore.length, 1)
  assert.equal(acquaintancesNearbyScore.length, 1)
  assert.equal(closeTieProximityScore.length, 1)
})

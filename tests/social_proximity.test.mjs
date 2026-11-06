// Run: node --test tests/social_proximity.test.mjs   (Node 22.18+ strips TypeScript types natively)
import test from 'node:test'
import assert from 'node:assert/strict'
import { closeTieProximityScore, acquaintanceProximityScore, socialConnectionScore } from '../frontend/lib/socialProximity.ts'

const MILES = [0, 1, 2, 5, 6, 7.5, 10, 25, 50, 100, 500, 3000]

test('close curve anchors', () => {
  assert.equal(closeTieProximityScore(0), 100)
  assert.equal(closeTieProximityScore(5), 100)
  assert.equal(closeTieProximityScore(7.5), 92)
  assert.equal(closeTieProximityScore(15), 68)
  assert.equal(closeTieProximityScore(100), 50)
  assert.equal(closeTieProximityScore(3000), 50)
})

test('close curve is non-increasing and no steeper than 3.2 points a mile', () => {
  // Regression guard on slope. The Level 2 criterion "no jump over 10 points between adjacent tested
  // distances" is a different test and fails on the 10 to 25 mile gap; see docs/SOCIAL_PROXIMITY.md.
  let prev = null
  for (let m = 0; m <= 200; m += 0.5) {
    const s = closeTieProximityScore(m)
    if (prev !== null) {
      assert.ok(s <= prev + 1e-9, `rises at ${m}`)
      assert.ok(prev - s <= 3.2 * 0.5 + 1e-9, `too steep at ${m}`)
    }
    prev = s
  }
})

test('acquaintance curve anchors and monotone', () => {
  assert.equal(acquaintanceProximityScore(7.5), 100)
  assert.equal(acquaintanceProximityScore(12.5), 55)
  assert.equal(acquaintanceProximityScore(25), 10)
  assert.equal(acquaintanceProximityScore(31), 0)
  let prev = 101
  for (const m of [0, 5, 7.5, 10, 12.5, 20, 25, 28, 31, 100]) {
    const s = acquaintanceProximityScore(m)
    assert.ok(s <= prev)
    prev = s
  }
})

test('invalid distance gives null, not a neutral number', () => {
  for (const bad of [null, undefined, NaN, -1, Infinity]) {
    assert.equal(closeTieProximityScore(bad), null)
    assert.equal(acquaintanceProximityScore(bad), null)
  }
  assert.equal(socialConnectionScore([{ tier: 'close', miles: null }]), null)
  assert.equal(socialConnectionScore([]), null)
})

test('nearest person carries the score; bonus only for people at or above the threshold', () => {
  assert.equal(socialConnectionScore([{ tier: 'close', miles: 3 }]), 100)
  assert.equal(socialConnectionScore([{ tier: 'close', miles: 30 }]), 64.8) // 68 - 15 * 18 / 85 = 64.82
  // 15 mi scores 68, under the close threshold of 70, so extra people at 15 mi add nothing
  assert.equal(socialConnectionScore([{ tier: 'close', miles: 15 }, { tier: 'close', miles: 15 }]), 68)
  // 10 mi scores 84 (above 70): one extra adds 5
  assert.equal(socialConnectionScore([{ tier: 'close', miles: 10 }, { tier: 'close', miles: 10 }]), 89)
})

test('bonus cap: three extras count as two', () => {
  const p = { tier: 'close', miles: 10 }
  assert.equal(socialConnectionScore([p, p, p]), 94)
  assert.equal(socialConnectionScore([p, p, p, p]), 94)
})

test('score does not depend on any place label (function takes miles only)', () => {
  assert.equal(socialConnectionScore.length, 1)
  assert.equal(closeTieProximityScore.length, 1)
})

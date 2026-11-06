// Run: node --test tests/social_proximity.test.mjs   (Node 22.18+ strips TypeScript types natively)
import test from 'node:test'
import assert from 'node:assert/strict'
import { closeTieProximityScore, acquaintanceProximityScore, socialConnectionScore } from '../frontend/lib/socialProximity.ts'

const MILES = [0, 1, 2, 5, 6, 7.5, 10, 25, 50, 100, 500, 3000]

test('close curve anchors', () => {
  assert.equal(closeTieProximityScore(0), 100)
  assert.equal(closeTieProximityScore(5), 100)
  assert.equal(closeTieProximityScore(7.5), 68)
  assert.equal(closeTieProximityScore(100), 50)
  assert.equal(closeTieProximityScore(3000), 50)
})

test('close curve is non-increasing with no jump over 10 points between tested distances', () => {
  let prev = null
  for (const m of MILES) {
    const s = closeTieProximityScore(m)
    if (prev !== null) {
      assert.ok(s <= prev + 1e-9, `rises at ${m}`)
      assert.ok(prev - s <= 35, `step too large at ${m}`) // 5 to 7.5 mi is a 32 point segment by design
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
  assert.equal(socialConnectionScore([{ tier: 'close', miles: 30 }]), 63.6) // 68 - 22.5 * 18 / 92.5 = 63.62
  // 7.5 mi scores 68, under the close threshold of 70, so extra people at 7.5 mi add nothing
  assert.equal(socialConnectionScore([{ tier: 'close', miles: 7.5 }, { tier: 'close', miles: 7.5 }]), 68)
  // 6 mi scores 87.2 (above 70): one extra adds 5
  assert.equal(socialConnectionScore([{ tier: 'close', miles: 6 }, { tier: 'close', miles: 6 }]), 92.2)
})

test('bonus cap: three extras count as two', () => {
  const base = closeTieProximityScore(6.5) // between 5 and 7.5, above 70
  const two = socialConnectionScore([{ tier: 'close', miles: 6.5 }, { tier: 'close', miles: 6.5 }, { tier: 'close', miles: 6.5 }])
  const four = socialConnectionScore([{ tier: 'close', miles: 6.5 }, { tier: 'close', miles: 6.5 }, { tier: 'close', miles: 6.5 }, { tier: 'close', miles: 6.5 }])
  assert.equal(two, four)
  assert.equal(two, Math.min(100, Math.round((base + 10) * 10) / 10))
})

test('score does not depend on any place label (function takes miles only)', () => {
  assert.equal(socialConnectionScore.length, 1)
  assert.equal(closeTieProximityScore.length, 1)
})

'use client'

import React, { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Check, ChevronLeft, ChevronRight, Coins, RefreshCcw } from 'lucide-react'
import AppHeader from './AppHeader'
import { PILLAR_META, type PillarKey } from '@/lib/pillars'

type BucketKey = 'must' | 'nice' | 'not'

const TOTAL_COINS = 20

const PILLAR_ORDER: PillarKey[] = [
  'natural_beauty',
  'built_beauty',
  'neighborhood_amenities',
  'active_outdoors',
  'healthcare_access',
  'public_transit_access',
  'air_travel_access',
  'economic_security',
  'quality_education',
  'housing_value',
]

const BUCKETS: Array<{
  key: BucketKey
  label: string
  minCoins: number
  help: string
}> = [
  { key: 'must', label: 'Must‑Have', minCoins: 3, help: 'Costs 3 coins to declare as a must‑have.' },
  { key: 'nice', label: 'Nice‑to‑Have', minCoins: 1, help: 'Costs 1 coin to keep in play.' },
  { key: 'not', label: 'Not a Priority', minCoins: 0, help: 'Costs 0 coins and gets 0 weight.' },
]

const bucketMin: Record<BucketKey, number> = BUCKETS.reduce((acc, b) => {
  acc[b.key] = b.minCoins
  return acc
}, {} as Record<BucketKey, number>)

function buildEmptyBuckets(enableSchools: boolean): Record<PillarKey, BucketKey> {
  const out = {} as Record<PillarKey, BucketKey>
  for (const k of PILLAR_ORDER) {
    out[k] = k === 'quality_education' && !enableSchools ? 'not' : 'not'
  }
  return out
}

function buildEmptyCoins(enableSchools: boolean): Record<PillarKey, number> {
  const out = {} as Record<PillarKey, number>
  for (const k of PILLAR_ORDER) {
    out[k] = k === 'quality_education' && !enableSchools ? 0 : 0
  }
  return out
}

function coinsToTokensString(coins: Record<PillarKey, number>): string {
  return PILLAR_ORDER.map((k) => `${k}:${Math.max(0, Math.floor(coins[k] || 0))}`).join(',')
}

function safeSumCoins(coins: Record<PillarKey, number>): number {
  return PILLAR_ORDER.reduce((sum, k) => sum + (Number.isFinite(coins[k]) ? (coins[k] as number) : 0), 0)
}

export interface TokenWeightsGameProps {
  enableSchools: boolean
  onApplyTokens?: (tokens: string) => void
  onBack?: () => void
  initialTokens?: string | null
}

type Screen = 'intro' | 'categorize' | 'allocate' | 'summary'

export default function TokenWeightsGame({ enableSchools, onApplyTokens, onBack, initialTokens }: TokenWeightsGameProps) {
  const [screen, setScreen] = useState<Screen>('intro')
  const [bucketByPillar, setBucketByPillar] = useState<Record<PillarKey, BucketKey>>(() => buildEmptyBuckets(enableSchools))
  const [coinsByPillar, setCoinsByPillar] = useState<Record<PillarKey, number>>(() => buildEmptyCoins(enableSchools))
  const [toast, setToast] = useState<string | null>(null)

  const totalSpent = useMemo(() => safeSumCoins(coinsByPillar), [coinsByPillar])
  const purse = Math.max(0, TOTAL_COINS - totalSpent)

  // Optional: import an existing tokens string (pillar:count,...).
  // Backend normalizes to 100, but for UI we treat counts as coins and clamp to 0..20.
  useEffect(() => {
    if (!initialTokens) return
    try {
      const nextCoins = buildEmptyCoins(enableSchools)
      for (const pair of String(initialTokens).split(',')) {
        const [rawK, rawV] = pair.split(':')
        const k = rawK?.trim() as PillarKey
        const v = Number(rawV)
        if (!PILLAR_ORDER.includes(k)) continue
        if (k === 'quality_education' && !enableSchools) continue
        if (!Number.isFinite(v)) continue
        nextCoins[k] = Math.max(0, Math.min(TOTAL_COINS, Math.floor(v)))
      }

      // If imported totals exceed TOTAL_COINS, scale down proportionally (preserve rough intent).
      const sum = safeSumCoins(nextCoins)
      if (sum > TOTAL_COINS && sum > 0) {
        const factor = TOTAL_COINS / sum
        for (const k of PILLAR_ORDER) {
          if (k === 'quality_education' && !enableSchools) {
            nextCoins[k] = 0
            continue
          }
          nextCoins[k] = Math.floor((nextCoins[k] || 0) * factor)
        }
      }

      // Assign buckets based on coin minimums (best-effort).
      const nextBuckets = buildEmptyBuckets(enableSchools)
      for (const k of PILLAR_ORDER) {
        const c = nextCoins[k] || 0
        if (k === 'quality_education' && !enableSchools) {
          nextBuckets[k] = 'not'
          nextCoins[k] = 0
          continue
        }
        if (c >= 3) nextBuckets[k] = 'must'
        else if (c >= 1) nextBuckets[k] = 'nice'
        else nextBuckets[k] = 'not'
      }

      setCoinsByPillar(nextCoins)
      setBucketByPillar(nextBuckets)
    } catch {
      // ignore parse errors
    }
    // Only run on mount for initialTokens
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 2200)
    return () => clearTimeout(t)
  }, [toast])

  const resetAll = () => {
    setBucketByPillar(buildEmptyBuckets(enableSchools))
    setCoinsByPillar(buildEmptyCoins(enableSchools))
    setToast(null)
    setScreen('categorize')
  }

  const setBucket = (pillar: PillarKey, nextBucket: BucketKey) => {
    if (pillar === 'quality_education' && !enableSchools) {
      setToast('Schools scoring is currently disabled.')
      return
    }

    const min = bucketMin[nextBucket]
    const currentCoins = coinsByPillar[pillar] || 0
    const currentTotal = safeSumCoins(coinsByPillar)
    const currentPurse = TOTAL_COINS - currentTotal

    // Not a Priority forces 0 coins (keeps the mental model consistent).
    if (nextBucket === 'not') {
      setBucketByPillar((prev) => ({ ...prev, [pillar]: nextBucket }))
      setCoinsByPillar((prev) => ({ ...prev, [pillar]: 0 }))
      return
    }

    if (currentCoins >= min) {
      setBucketByPillar((prev) => ({ ...prev, [pillar]: nextBucket }))
      return
    }

    const delta = min - currentCoins
    if (currentPurse < delta) {
      setToast(`Not enough coins in your purse for ${BUCKETS.find((b) => b.key === nextBucket)?.label || 'that choice'}.`)
      return
    }

    setBucketByPillar((prev) => ({ ...prev, [pillar]: nextBucket }))
    setCoinsByPillar((prev) => ({ ...prev, [pillar]: currentCoins + delta }))
  }

  const addCoin = (pillar: PillarKey) => {
    if (pillar === 'quality_education' && !enableSchools) return
    const bucket = bucketByPillar[pillar]
    if (bucket === 'not') {
      setToast('Set this to Nice‑to‑Have or Must‑Have to add coins.')
      return
    }
    if (purse <= 0) {
      setToast('Purse is empty. Remove a coin from another pillar to add here.')
      return
    }
    setCoinsByPillar((prev) => ({ ...prev, [pillar]: (prev[pillar] || 0) + 1 }))
  }

  const removeCoin = (pillar: PillarKey) => {
    if (pillar === 'quality_education' && !enableSchools) return
    const bucket = bucketByPillar[pillar]
    const min = bucketMin[bucket]
    const current = coinsByPillar[pillar] || 0
    if (current <= min) {
      // If user wants to go lower than the min, they must demote the bucket.
      setToast('To remove more coins, move this pillar to a lower bucket.')
      return
    }
    setCoinsByPillar((prev) => ({ ...prev, [pillar]: Math.max(0, (prev[pillar] || 0) - 1) }))
  }

  const canContinueFromCategorize = useMemo(() => {
    // Must spend exactly TOTAL_COINS by the end, but we let users continue early.
    // We do require that all "not" pillars are 0 coins (enforced by setBucket).
    return true
  }, [])

  const allocationsForSummary = useMemo(() => {
    return PILLAR_ORDER.map((pillar) => {
      const coins = Math.max(0, Math.floor(coinsByPillar[pillar] || 0))
      const pct = (coins / TOTAL_COINS) * 100
      return {
        pillar,
        coins,
        pct,
        bucket: bucketByPillar[pillar],
      }
    }).sort((a, b) => b.coins - a.coins)
  }, [bucketByPillar, coinsByPillar])

  const tokensString = useMemo(() => coinsToTokensString(coinsByPillar), [coinsByPillar])

  const handleBack = () => {
    if (screen === 'intro') {
      if (onBack) onBack()
      return
    }
    if (screen === 'categorize') {
      setScreen('intro')
      return
    }
    if (screen === 'allocate') {
      setScreen('categorize')
      return
    }
    setScreen('allocate')
  }

  const handleApply = () => {
    if (purse !== 0) {
      setToast('Spend all 20 coins before applying.')
      return
    }
    if (onApplyTokens) onApplyTokens(tokensString)
  }

  if (screen === 'intro') {
    return (
      <main className="hf-page">
        <AppHeader />
        <div className="hf-container">
          <div className="hf-card" style={{ maxWidth: 920, margin: '0 auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'center' }}>
              {onBack ? (
                <button onClick={onBack} className="hf-btn-link" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                  <ArrowLeft size={18} />
                  Back
                </button>
              ) : (
                <span />
              )}
              <div className="hf-label" style={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Coin Weights
              </div>
              <span />
            </div>

            <div style={{ marginTop: '1.5rem', textAlign: 'center' }}>
              <div
                style={{
                  width: 72,
                  height: 72,
                  borderRadius: 18,
                  margin: '0 auto 1.5rem',
                  background: 'rgba(102,126,234,0.12)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Coins size={34} color="var(--hf-primary-1)" />
              </div>
              <h2 className="hf-section-title" style={{ marginBottom: '0.75rem' }}>
                Spend 20 coins on what matters most
              </h2>
              <p className="hf-muted" style={{ maxWidth: 760, margin: '0 auto 1.25rem' }}>
                First, label each pillar as Must‑Have / Nice‑to‑Have / Not a Priority. Then use your remaining coins to power up your favorites.
                Each coin is 5% of your final weights.
              </p>

              {!enableSchools ? (
                <div className="hf-panel" style={{ maxWidth: 760, margin: '0 auto 1.5rem' }}>
                  <div className="hf-muted" style={{ margin: 0 }}>
                    Note: <strong>Schools</strong> weighting is disabled unless you enable school scoring. We’ll lock it to 0 for now.
                  </div>
                </div>
              ) : null}

              <button
                onClick={() => setScreen('categorize')}
                className="hf-btn-primary"
                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
              >
                Start <ChevronRight size={18} />
              </button>
            </div>
          </div>
        </div>
      </main>
    )
  }

  const header = (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', marginBottom: '1.25rem' }}>
      <button onClick={handleBack} className="hf-btn-link" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
        <ChevronLeft size={18} />
        Back
      </button>
      <div className="hf-label" style={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>
        {screen === 'categorize' ? 'Stage 1: Buckets' : screen === 'allocate' ? 'Stage 2: Power‑Ups' : 'Summary'}
      </div>
      <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontWeight: 800 }}>
        <Coins size={16} /> {purse} left
      </div>
    </div>
  )

  if (screen === 'categorize') {
    return (
      <main className="hf-page">
        <AppHeader />
        <div className="hf-container">
          {header}

          {toast ? (
            <div className="hf-panel" style={{ marginBottom: '1rem', borderColor: 'rgba(255, 193, 7, 0.35)', background: 'rgba(255, 193, 7, 0.10)' }}>
              <div className="hf-muted" style={{ margin: 0 }}>
                {toast}
              </div>
            </div>
          ) : null}

          <div className="hf-card" style={{ marginBottom: '1.25rem' }}>
            <div className="hf-label" style={{ marginBottom: '0.75rem' }}>
              Pick a bucket for each pillar (buckets have minimum coin costs)
            </div>
            <div className="hf-grid-3" style={{ gap: '1rem' }}>
              {BUCKETS.map((b) => (
                <div key={b.key} className="hf-panel">
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', alignItems: 'baseline' }}>
                    <div style={{ fontWeight: 900, color: 'var(--hf-text-primary)' }}>{b.label}</div>
                    <div className="hf-muted" style={{ fontWeight: 800 }}>
                      Min {b.minCoins}
                    </div>
                  </div>
                  <div className="hf-muted" style={{ fontSize: '0.95rem', marginTop: '0.5rem' }}>
                    {b.help}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="hf-card">
            <div className="hf-grid-2" style={{ gap: '1rem' }}>
              {PILLAR_ORDER.map((pillar) => {
                const meta = PILLAR_META[pillar]
                const bucket = bucketByPillar[pillar]
                const coins = coinsByPillar[pillar] || 0
                const disabled = pillar === 'quality_education' && !enableSchools

                return (
                  <div key={pillar} className="hf-panel" style={{ opacity: disabled ? 0.55 : 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'flex-start' }}>
                      <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                        <div style={{ fontSize: '1.6rem' }}>{meta.icon}</div>
                        <div>
                          <div style={{ fontWeight: 900, color: 'var(--hf-text-primary)' }}>{meta.name}</div>
                          <div className="hf-muted" style={{ fontSize: '0.95rem' }}>
                            {meta.description}
                          </div>
                        </div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div className="hf-label">Coins</div>
                        <div style={{ fontWeight: 900, color: 'var(--hf-text-primary)' }}>{coins}</div>
                      </div>
                    </div>

                    <div style={{ marginTop: '0.9rem', display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                      {BUCKETS.map((b) => {
                        const active = bucket === b.key
                        return (
                          <button
                            key={b.key}
                            type="button"
                            disabled={disabled}
                            onClick={() => setBucket(pillar, b.key)}
                            className={active ? 'hf-btn-primary' : 'hf-btn-link'}
                            style={{
                              padding: active ? '0.55rem 0.9rem' : '0.55rem 0.9rem',
                              borderRadius: 999,
                              border: active ? undefined : '1px solid var(--hf-border)',
                              background: active ? 'var(--hf-primary-gradient)' : 'transparent',
                              color: active ? '#fff' : 'var(--hf-text-primary)',
                              fontWeight: 850,
                            }}
                          >
                            {b.label}
                          </button>
                        )
                      })}
                    </div>

                    {disabled ? (
                      <div className="hf-muted" style={{ marginTop: '0.75rem', fontSize: '0.92rem' }}>
                        Schools weighting is disabled unless you enable school scoring.
                      </div>
                    ) : null}
                  </div>
                )
              })}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', marginTop: '1.5rem' }}>
              <button type="button" className="hf-btn-link" onClick={resetAll} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                <RefreshCcw size={16} /> Reset
              </button>
              <button
                type="button"
                className="hf-btn-primary"
                disabled={!canContinueFromCategorize}
                onClick={() => setScreen('allocate')}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
              >
                Continue <ChevronRight size={18} />
              </button>
            </div>
          </div>
        </div>
      </main>
    )
  }

  if (screen === 'allocate') {
    return (
      <main className="hf-page">
        <AppHeader />
        <div className="hf-container">
          {header}

          {toast ? (
            <div className="hf-panel" style={{ marginBottom: '1rem', borderColor: 'rgba(255, 193, 7, 0.35)', background: 'rgba(255, 193, 7, 0.10)' }}>
              <div className="hf-muted" style={{ margin: 0 }}>
                {toast}
              </div>
            </div>
          ) : null}

          <div className="hf-card" style={{ marginBottom: '1.25rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'baseline' }}>
              <div>
                <div className="hf-section-title" style={{ marginBottom: '0.4rem' }}>
                  Power‑ups
                </div>
                <div className="hf-muted" style={{ fontSize: '0.95rem' }}>
                  Tap <strong>+</strong> to drop a coin into a pillar. If your purse is empty, you’ll need to remove a coin elsewhere first.
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div className="hf-label">Purse</div>
                <div style={{ fontWeight: 950, color: 'var(--hf-text-primary)', fontSize: '1.2rem' }}>{purse}</div>
              </div>
            </div>
          </div>

          <div className="hf-card">
            <div className="hf-grid-3" style={{ gap: '1rem' }}>
              {PILLAR_ORDER.map((pillar) => {
                const meta = PILLAR_META[pillar]
                const bucket = bucketByPillar[pillar]
                const coins = Math.max(0, Math.floor(coinsByPillar[pillar] || 0))
                const min = bucketMin[bucket]
                const disabledSchools = pillar === 'quality_education' && !enableSchools
                const canAdd = !disabledSchools && bucket !== 'not' && purse > 0
                const canRemove = !disabledSchools && coins > min
                const towerHeight = 10 + coins * 7

                return (
                  <div key={pillar} className="hf-panel" style={{ opacity: disabledSchools ? 0.55 : 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', alignItems: 'flex-start' }}>
                      <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                        <div style={{ fontSize: '1.7rem' }}>{meta.icon}</div>
                        <div>
                          <div style={{ fontWeight: 900, color: 'var(--hf-text-primary)' }}>{meta.name}</div>
                          <div className="hf-muted" style={{ fontSize: '0.9rem' }}>
                            {bucket === 'must' ? 'Must‑Have' : bucket === 'nice' ? 'Nice‑to‑Have' : 'Not a Priority'}
                          </div>
                        </div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div className="hf-label">Coins</div>
                        <div style={{ fontWeight: 950, color: 'var(--hf-text-primary)', fontSize: '1.15rem' }}>{coins}</div>
                      </div>
                    </div>

                    <div style={{ marginTop: '0.9rem', display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: '0.75rem' }}>
                      <div style={{ flex: '1 1 auto' }}>
                        <div
                          aria-hidden="true"
                          style={{
                            height: towerHeight,
                            borderRadius: 12,
                            background: coins > 0 ? 'var(--hf-primary-gradient)' : '#f1f3f5',
                            transition: 'height 160ms ease, background 160ms ease',
                          }}
                        />
                        <div className="hf-muted" style={{ fontSize: '0.9rem', marginTop: '0.5rem' }}>
                          {Math.round((coins / TOTAL_COINS) * 100)}%
                        </div>
                      </div>

                      <div style={{ display: 'grid', gap: '0.5rem', justifyItems: 'end' }}>
                        <button
                          type="button"
                          className="hf-btn-primary"
                          onClick={() => addCoin(pillar)}
                          disabled={!canAdd}
                          style={{ minWidth: 46, padding: '0.55rem 0.85rem', borderRadius: 12, fontWeight: 950 }}
                        >
                          +
                        </button>
                        <button
                          type="button"
                          className="hf-btn-link"
                          onClick={() => removeCoin(pillar)}
                          disabled={!canRemove}
                          style={{
                            minWidth: 46,
                            padding: '0.55rem 0.85rem',
                            borderRadius: 12,
                            border: '1px solid var(--hf-border)',
                            fontWeight: 950,
                            color: 'var(--hf-text-primary)',
                          }}
                        >
                          –
                        </button>
                      </div>
                    </div>

                    {bucket === 'not' ? (
                      <div className="hf-muted" style={{ marginTop: '0.75rem', fontSize: '0.9rem' }}>
                        Move to Nice/Must in Stage 1 to add coins.
                      </div>
                    ) : coins === min ? (
                      <div className="hf-muted" style={{ marginTop: '0.75rem', fontSize: '0.9rem' }}>
                        Minimum for this bucket is {min}. To go lower, demote the bucket.
                      </div>
                    ) : null}
                  </div>
                )
              })}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', marginTop: '1.5rem' }}>
              <button type="button" className="hf-btn-link" onClick={resetAll} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                <RefreshCcw size={16} /> Reset
              </button>
              <button
                type="button"
                className="hf-btn-primary"
                onClick={() => {
                  if (purse !== 0) {
                    setToast('Spend all 20 coins to lock in a full weighting.')
                    return
                  }
                  setScreen('summary')
                }}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
              >
                Review <ChevronRight size={18} />
              </button>
            </div>
          </div>
        </div>
      </main>
    )
  }

  return (
    <main className="hf-page">
      <AppHeader />
      <div className="hf-container">
        {header}

        {toast ? (
          <div className="hf-panel" style={{ marginBottom: '1rem', borderColor: 'rgba(255, 193, 7, 0.35)', background: 'rgba(255, 193, 7, 0.10)' }}>
            <div className="hf-muted" style={{ margin: 0 }}>
              {toast}
            </div>
          </div>
        ) : null}

        <div className="hf-card">
          <h2 className="hf-section-title" style={{ marginBottom: '0.75rem' }}>
            Your weights
          </h2>
          <div className="hf-muted" style={{ marginBottom: '1.25rem' }}>
            Each coin is 5%. This will be used to personalize your HomeFit score.
          </div>

          <div className="hf-grid-3" style={{ marginBottom: '1.5rem' }}>
            {allocationsForSummary.map(({ pillar, coins, pct, bucket }) => {
              const meta = PILLAR_META[pillar]
              const disabledSchools = pillar === 'quality_education' && !enableSchools
              return (
                <div key={pillar} className="hf-panel" style={{ opacity: disabledSchools ? 0.55 : 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'flex-start' }}>
                    <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                      <div style={{ fontSize: '1.6rem' }}>{meta.icon}</div>
                      <div>
                        <div style={{ fontWeight: 900, color: 'var(--hf-text-primary)' }}>{meta.name}</div>
                        <div className="hf-muted" style={{ fontSize: '0.9rem' }}>
                          {bucket === 'must' ? 'Must‑Have' : bucket === 'nice' ? 'Nice‑to‑Have' : 'Not a Priority'}
                        </div>
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div className="hf-label">Weight</div>
                      <div style={{ fontWeight: 950, color: 'var(--hf-text-primary)' }}>{pct.toFixed(0)}%</div>
                      <div className="hf-muted" style={{ fontSize: '0.9rem' }}>
                        {coins} coins
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          <div className="hf-panel" style={{ marginBottom: '1.25rem' }}>
            <div className="hf-label" style={{ marginBottom: '0.35rem' }}>
              Tokens payload
            </div>
            <div className="hf-muted" style={{ wordBreak: 'break-word', fontSize: '0.95rem' }}>
              {tokensString}
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
            <button
              type="button"
              className="hf-btn-link"
              onClick={() => setScreen('allocate')}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
            >
              <ChevronLeft size={18} /> Edit
            </button>
            <button
              type="button"
              className="hf-btn-primary"
              onClick={handleApply}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
            >
              <Check size={18} /> Apply weights
            </button>
          </div>
        </div>
      </div>
    </main>
  )
}


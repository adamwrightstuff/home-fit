'use client'

import React, { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft, Coins } from 'lucide-react'

type AllocationMap = Record<string, number>

export interface CoinWeightingPillar {
  id: string
  label: string
  icon: string
  description: string
  disabled?: boolean
}

export interface CoinWeightingInterfaceProps {
  pillars: CoinWeightingPillar[]
  totalCoins?: number
  onComplete: (weights: Record<string, number>) => void
  onBack?: () => void
}

const STORAGE_KEY = 'homefit_coin_allocations_v1'
const LOCKS_KEY = 'homefit_coin_locks_v1'

function clampInt(n: number, min: number, max: number): number {
  if (!Number.isFinite(n)) return min
  return Math.max(min, Math.min(max, Math.round(n)))
}

function sumValues(obj: AllocationMap): number {
  return Object.values(obj).reduce((s, v) => s + (Number.isFinite(v) ? v : 0), 0)
}

function buildInitialAllocations(pillars: CoinWeightingPillar[]): AllocationMap {
  const out: AllocationMap = {}
  for (const p of pillars) out[p.id] = 0
  return out
}

export default function CoinWeightingInterface({
  pillars,
  totalCoins = 20,
  onComplete,
  onBack,
}: CoinWeightingInterfaceProps) {
  const [allocations, setAllocations] = useState<AllocationMap>(() => buildInitialAllocations(pillars))
  const [lockedAtZero, setLockedAtZero] = useState<Record<string, boolean>>(() =>
    pillars.reduce((acc, p) => {
      acc[p.id] = false
      return acc
    }, {} as Record<string, boolean>)
  )
  const [showSkipModal, setShowSkipModal] = useState(false)
  const [shakeCounter, setShakeCounter] = useState(0)
  const shakeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const modalConfirmRef = useRef<HTMLButtonElement | null>(null)

  // Restore persisted state (localStorage).
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      const rawLocks = localStorage.getItem(LOCKS_KEY)
      const parsed = raw ? JSON.parse(raw) : null
      const parsedLocks = rawLocks ? JSON.parse(rawLocks) : null

      if (parsed && typeof parsed === 'object') {
        const next = buildInitialAllocations(pillars)
        for (const p of pillars) {
          if (p.disabled) {
            next[p.id] = 0
            continue
          }
          const v = (parsed as any)[p.id]
          next[p.id] = clampInt(Number(v), 0, totalCoins)
        }

        // If the saved total exceeds the purse, scale down proportionally.
        const sum = sumValues(next)
        if (sum > totalCoins && sum > 0) {
          const factor = totalCoins / sum
          for (const p of pillars) {
            next[p.id] = p.disabled ? 0 : Math.floor((next[p.id] || 0) * factor)
          }
        }
        setAllocations(next)
      }

      if (parsedLocks && typeof parsedLocks === 'object') {
        const nextLocks = pillars.reduce((acc, p) => {
          acc[p.id] = Boolean((parsedLocks as any)[p.id])
          return acc
        }, {} as Record<string, boolean>)
        setLockedAtZero(nextLocks)
      }
    } catch {
      // ignore
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Persist state.
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(allocations))
    } catch {
      // ignore
    }
  }, [allocations])

  useEffect(() => {
    try {
      localStorage.setItem(LOCKS_KEY, JSON.stringify(lockedAtZero))
    } catch {
      // ignore
    }
  }, [lockedAtZero])

  // Ensure disabled pillars stay at 0 and locked at 0.
  useEffect(() => {
    setAllocations((prev) => {
      let changed = false
      const next = { ...prev }
      for (const p of pillars) {
        if (p.disabled && (next[p.id] || 0) !== 0) {
          next[p.id] = 0
          changed = true
        }
      }
      return changed ? next : prev
    })
    setLockedAtZero((prev) => {
      let changed = false
      const next = { ...prev }
      for (const p of pillars) {
        if (p.disabled && next[p.id] !== true) {
          next[p.id] = true
          changed = true
        }
      }
      return changed ? next : prev
    })
  }, [pillars])

  const spent = useMemo(() => sumValues(allocations), [allocations])
  const remaining = Math.max(0, totalCoins - spent)
  const allocated = Math.min(totalCoins, Math.max(0, spent))

  const triggerShake = () => {
    setShakeCounter((n) => n + 1)
    if (shakeTimerRef.current) clearTimeout(shakeTimerRef.current)
    shakeTimerRef.current = setTimeout(() => {
      // no-op: shake is keyed by counter
    }, 450)
  }

  const setPillarCoins = (pillarId: string, desired: number) => {
    setAllocations((prev) => {
      const current = clampInt(prev[pillarId] || 0, 0, totalCoins)
      const desiredInt = clampInt(desired, 0, totalCoins)

      // If increasing, enforce global purse.
      const delta = desiredInt - current
      if (delta <= 0) {
        return { ...prev, [pillarId]: desiredInt }
      }
      const maxAllowed = current + remaining
      const nextVal = Math.min(desiredInt, maxAllowed)
      if (nextVal !== desiredInt) triggerShake()
      return { ...prev, [pillarId]: nextVal }
    })
  }

  const handleIncrement = (pillarId: string) => {
    const isLocked = Boolean(lockedAtZero[pillarId])
    if (isLocked) return
    if (remaining <= 0) {
      triggerShake()
      return
    }
    setAllocations((prev) => ({ ...prev, [pillarId]: clampInt((prev[pillarId] || 0) + 1, 0, totalCoins) }))
  }

  const handleDecrement = (pillarId: string) => {
    setAllocations((prev) => ({ ...prev, [pillarId]: clampInt((prev[pillarId] || 0) - 1, 0, totalCoins) }))
  }

  const toggleLockAtZero = (pillarId: string, enabled: boolean) => {
    setLockedAtZero((prev) => ({ ...prev, [pillarId]: enabled }))
    if (enabled) {
      setAllocations((prev) => ({ ...prev, [pillarId]: 0 }))
    }
  }

  const totalAllocated = allocated
  const canContinue = totalAllocated > 0

  const weights = useMemo(() => {
    const out: Record<string, number> = {}
    for (const p of pillars) {
      const coins = clampInt(allocations[p.id] || 0, 0, totalCoins)
      if (coins <= 0) continue
      out[p.id] = coins / totalCoins
    }
    return out
  }, [allocations, pillars, totalCoins])

  const resetAll = () => {
    setAllocations(buildInitialAllocations(pillars))
    setLockedAtZero(
      pillars.reduce((acc, p) => {
        acc[p.id] = Boolean(p.disabled) // disabled pillars effectively locked at 0
        return acc
      }, {} as Record<string, boolean>)
    )
    try {
      localStorage.removeItem(STORAGE_KEY)
      localStorage.removeItem(LOCKS_KEY)
    } catch {
      // ignore
    }
  }

  const openSkip = () => setShowSkipModal(true)

  const closeSkip = () => setShowSkipModal(false)

  const confirmSkip = () => {
    setShowSkipModal(false)
    onComplete({})
  }

  const handleContinue = () => {
    if (!canContinue) {
      openSkip()
      return
    }
    onComplete(weights)
  }

  useEffect(() => {
    if (showSkipModal) {
      setTimeout(() => modalConfirmRef.current?.focus(), 0)
    }
  }, [showSkipModal])

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (!showSkipModal) return
      if (e.key === 'Escape') {
        e.preventDefault()
        closeSkip()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [showSkipModal])

  const filledDots = Math.min(totalCoins, Math.max(0, totalAllocated))

  return (
    <main className="hf-page">
      <div className="hf-container" style={{ marginTop: 0, paddingTop: '2rem' }}>
        <div className="hf-card" style={{ maxWidth: 1100, margin: '0 auto' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              {onBack ? (
                <button onClick={onBack} className="hf-btn-link" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                  <ArrowLeft size={18} /> Back
                </button>
              ) : null}
            </div>
            <div style={{ textAlign: 'center', flex: '1 1 auto', minWidth: 240 }}>
              <div className="hf-label" style={{ textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                💰 COIN WEIGHTS
              </div>
              <div style={{ fontSize: '1.8rem', fontWeight: 850, color: 'var(--hf-text-primary)', marginTop: '0.35rem' }}>
                Spend {totalCoins} coins on what matters most
              </div>
              <div className="hf-muted" style={{ marginTop: '0.35rem' }}>
                Drag sliders or tap +/- to show what’s important to you. Each coin = {(100 / totalCoins).toFixed(0)}% weight.
              </div>
            </div>
            <div style={{ width: 220, display: 'flex', justifyContent: 'flex-end' }}>
              <button
                type="button"
                className="hf-btn-link"
                onClick={resetAll}
                style={{ border: '1px solid var(--hf-border)', color: 'var(--hf-text-primary)' }}
              >
                Reset
              </button>
            </div>
          </div>

          <div style={{ marginTop: '1.5rem' }}>
            <div
              className={shakeCounter ? `hf-coin-counter hf-coin-counter--shake-${shakeCounter}` : 'hf-coin-counter'}
              role="status"
              aria-live="polite"
              aria-atomic="true"
              style={{
                display: 'grid',
                gap: '0.75rem',
                padding: '1.25rem 1.25rem',
                borderRadius: 16,
                border: '1px solid var(--hf-border)',
                background: 'rgba(102,126,234,0.06)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '1rem', flexWrap: 'wrap' }}>
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontWeight: 900 }}>
                  <Coins size={18} /> Coins remaining: <span style={{ fontSize: '1.2rem' }}>{remaining}</span> / {totalCoins}
                </div>
                <div className="hf-muted" style={{ fontWeight: 800 }}>
                  {filledDots} spent
                </div>
              </div>
              <div aria-hidden="true" style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {Array.from({ length: totalCoins }).map((_, i) => {
                  const filled = i < filledDots
                  return (
                    <div
                      key={i}
                      style={{
                        width: 12,
                        height: 12,
                        borderRadius: 999,
                        background: filled ? 'var(--hf-primary-gradient)' : '#e5e7eb',
                        boxShadow: filled ? '0 6px 16px rgba(102,126,234,0.22)' : 'none',
                        transition: 'transform 140ms ease, background 140ms ease',
                        transform: filled ? 'scale(1.03)' : 'scale(1)',
                      }}
                    />
                  )
                })}
              </div>
            </div>
          </div>

          <div style={{ marginTop: '1.5rem', display: 'grid', gap: '1rem' }}>
            {pillars.map((pillar) => {
              const coins = clampInt(allocations[pillar.id] || 0, 0, totalCoins)
              const disabled = Boolean(pillar.disabled)
              const locked = Boolean(lockedAtZero[pillar.id])
              const canInc = !disabled && !locked && remaining > 0
              const canDec = !disabled && coins > 0

              const maxRange = disabled || locked ? 0 : Math.min(totalCoins, coins + remaining)

              return (
                <div
                  key={pillar.id}
                  className="hf-panel"
                  style={{
                    opacity: disabled ? 0.55 : 1,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'flex-start', flexWrap: 'wrap' }}>
                    <div style={{ display: 'flex', gap: '0.85rem', alignItems: 'center' }}>
                      <div style={{ fontSize: '1.75rem' }}>{pillar.icon}</div>
                      <div>
                        <div style={{ fontWeight: 900, color: 'var(--hf-text-primary)', fontSize: '1.1rem' }}>{pillar.label}</div>
                        <div className="hf-muted" style={{ fontSize: '0.95rem', maxWidth: 720 }}>
                          {pillar.description}
                        </div>
                      </div>
                    </div>
                    <div style={{ textAlign: 'right', minWidth: 110 }}>
                      <div className="hf-label">Coins</div>
                      <div style={{ fontWeight: 950, color: 'var(--hf-text-primary)', fontSize: '1.25rem' }}>{coins}</div>
                      {disabled ? (
                        <div className="hf-muted" style={{ fontSize: '0.9rem' }}>
                          Unlock via school scoring
                        </div>
                      ) : null}
                    </div>
                  </div>

                  <div style={{ marginTop: '1.1rem', display: 'grid', gap: '0.75rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <button
                        type="button"
                        className="hf-btn-primary"
                        onClick={() => handleDecrement(pillar.id)}
                        disabled={!canDec}
                        aria-label={`Remove coin from ${pillar.label}. Currently ${coins} coins allocated.`}
                        style={{ padding: '0.7rem 1rem', borderRadius: 12, minWidth: 48, fontWeight: 950 }}
                      >
                        –
                      </button>

                      <div aria-hidden="true" style={{ flex: '1 1 auto', display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                        {Array.from({ length: totalCoins }).map((_, i) => {
                          const filled = i < coins
                          return (
                            <div
                              key={i}
                              style={{
                                width: 10,
                                height: 10,
                                borderRadius: 999,
                                background: filled ? 'var(--hf-primary-gradient)' : '#e5e7eb',
                                transition: 'transform 140ms ease, background 140ms ease',
                                transform: filled ? 'scale(1.06)' : 'scale(1)',
                              }}
                            />
                          )
                        })}
                      </div>

                      <button
                        type="button"
                        className="hf-btn-primary"
                        onClick={() => handleIncrement(pillar.id)}
                        disabled={!canInc}
                        aria-label={`Add coin to ${pillar.label}. Currently ${coins} coins allocated.`}
                        style={{ padding: '0.7rem 1rem', borderRadius: 12, minWidth: 48, fontWeight: 950 }}
                      >
                        +
                      </button>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                      <input
                        type="range"
                        min={0}
                        max={maxRange}
                        value={coins}
                        disabled={disabled || locked}
                        onChange={(e) => setPillarCoins(pillar.id, Number(e.target.value))}
                        aria-label={`${pillar.label} coin slider. Current ${coins} of ${totalCoins}.`}
                        style={{ flex: '1 1 320px' }}
                      />
                      <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', cursor: disabled ? 'not-allowed' : 'pointer' }}>
                        <input
                          type="checkbox"
                          disabled={disabled}
                          checked={locked}
                          onChange={(e) => toggleLockAtZero(pillar.id, e.target.checked)}
                        />
                        <span className="hf-muted" style={{ fontWeight: 700 }}>
                          Lock at 0
                        </span>
                      </label>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          <div
            style={{
              marginTop: '1.5rem',
              position: 'sticky',
              bottom: 12,
              paddingTop: '1rem',
            }}
          >
            <div
              className="hf-panel"
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: '1rem',
                flexWrap: 'wrap',
                borderColor: 'rgba(102,126,234,0.25)',
                background: 'rgba(102,126,234,0.06)',
              }}
            >
              <div className="hf-muted" style={{ fontSize: '0.95rem' }}>
                {totalAllocated === 0 ? (
                  <>Allocate coins to personalize your score, or skip for equal weighting.</>
                ) : remaining === 0 ? (
                  <strong style={{ color: 'var(--hf-text-primary)' }}>All coins allocated. Ready to continue.</strong>
                ) : (
                  <>You can continue now, or spend the remaining coins for more precision.</>
                )}
              </div>
              <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  className="hf-btn-link"
                  onClick={openSkip}
                  style={{ border: '1px solid var(--hf-border)', color: 'var(--hf-text-primary)' }}
                >
                  Skip this step
                </button>
                <button
                  type="button"
                  className="hf-btn-primary"
                  onClick={handleContinue}
                  style={{
                    paddingLeft: '2.25rem',
                    paddingRight: '2.25rem',
                    boxShadow: remaining === 0 && totalAllocated > 0 ? '0 0 0 4px rgba(102,126,234,0.14)' : undefined,
                  }}
                >
                  Continue →
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {showSkipModal ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Skip weighting confirmation"
          onMouseDown={(e) => {
            // click outside to close
            if (e.target === e.currentTarget) closeSkip()
          }}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.45)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1.25rem',
            zIndex: 50,
          }}
        >
          <div className="hf-card" style={{ maxWidth: 520, width: '100%' }}>
            <div style={{ fontSize: '1.4rem', fontWeight: 900, color: 'var(--hf-text-primary)' }}>Skip weighting?</div>
            <div className="hf-muted" style={{ marginTop: '0.5rem' }}>
              You haven’t allocated any coins. We’ll weight all pillars equally.
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.5rem' }}>
              <button
                type="button"
                className="hf-btn-link"
                onClick={closeSkip}
                style={{ border: '1px solid var(--hf-border)', color: 'var(--hf-text-primary)' }}
              >
                Cancel
              </button>
              <button
                ref={modalConfirmRef}
                type="button"
                className="hf-btn-primary"
                onClick={confirmSkip}
                style={{ paddingLeft: '2.25rem', paddingRight: '2.25rem' }}
              >
                Continue without weighting
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  )
}


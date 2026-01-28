'use client'

import React, { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft, Coins, RefreshCcw } from 'lucide-react'

export interface PokerPillar {
  id: string
  label: string
  icon: string
  description: string
  disabled?: boolean
}

export interface PokerCoinWeightingProps {
  pillars: PokerPillar[]
  totalChips?: number // default 20
  onComplete: (weights: Record<string, number>) => void
  onBack?: () => void
}

type Allocations = Record<string, number>

// Token budget interface persistence
const STORAGE_KEY = 'homefit_token_budget_allocations_v1'
const SOUND_KEY = 'homefit_token_budget_sounds_v1'

function clampInt(n: number, min: number, max: number): number {
  if (!Number.isFinite(n)) return min
  return Math.max(min, Math.min(max, Math.round(n)))
}

function sum(obj: Allocations): number {
  return Object.values(obj).reduce((s, v) => s + (Number.isFinite(v) ? v : 0), 0)
}

function buildAllocations(pillars: PokerPillar[]): Allocations {
  const out: Allocations = {}
  for (const p of pillars) out[p.id] = 0
  return out
}

function playClick(kind: 'place' | 'remove' | 'complete') {
  // Simple synthesis so we don't need audio assets.
  try {
    const AudioCtx = (window as any).AudioContext || (window as any).webkitAudioContext
    if (!AudioCtx) return
    const ctx = new AudioCtx()
    const o = ctx.createOscillator()
    const g = ctx.createGain()

    const now = ctx.currentTime
    const base = kind === 'place' ? 320 : kind === 'remove' ? 260 : 420
    const dur = kind === 'complete' ? 0.12 : 0.08

    o.type = 'triangle'
    o.frequency.setValueAtTime(base, now)
    o.frequency.exponentialRampToValueAtTime(base * 1.25, now + dur)

    g.gain.setValueAtTime(0.0001, now)
    g.gain.exponentialRampToValueAtTime(0.06, now + 0.015)
    g.gain.exponentialRampToValueAtTime(0.0001, now + dur)

    o.connect(g)
    g.connect(ctx.destination)
    o.start(now)
    o.stop(now + dur)

    setTimeout(() => {
      try {
        ctx.close()
      } catch {
        // ignore
      }
    }, Math.ceil((dur + 0.05) * 1000))
  } catch {
    // ignore
  }
}

type FlyChip = {
  id: string
  from: { x: number; y: number }
  to: { x: number; y: number }
  kind: 'place' | 'remove' | 'allin'
}

export default function PokerCoinWeighting({ pillars, totalChips = 20, onComplete, onBack }: PokerCoinWeightingProps) {
  const [allocations, setAllocations] = useState<Allocations>(() => buildAllocations(pillars))
  const [soundsEnabled, setSoundsEnabled] = useState(true)
  const [showAllIn, setShowAllIn] = useState(false)
  const [allInTarget, setAllInTarget] = useState<string>('')
  const [showSkipModal, setShowSkipModal] = useState(false)
  const [shake, setShake] = useState(0)
  const [flyChip, setFlyChip] = useState<FlyChip | null>(null)

  const stackRef = useRef<HTMLDivElement | null>(null)
  const circleRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const flyRef = useRef<HTMLDivElement | null>(null)

  // Restore persisted allocations + sound preference
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      const rawSound = localStorage.getItem(SOUND_KEY)
      if (rawSound !== null) setSoundsEnabled(rawSound === '1')

      if (raw) {
        const parsed = JSON.parse(raw)
        if (parsed && typeof parsed === 'object') {
          const next = buildAllocations(pillars)
          for (const p of pillars) {
            if (p.disabled) {
              next[p.id] = 0
              continue
            }
            next[p.id] = clampInt(Number((parsed as any)[p.id] || 0), 0, totalChips)
          }
          // If saved total exceeds purse, scale down.
          const s = sum(next)
          if (s > totalChips && s > 0) {
            const factor = totalChips / s
            for (const p of pillars) {
              next[p.id] = p.disabled ? 0 : Math.floor((next[p.id] || 0) * factor)
            }
          }
          setAllocations(next)
        }
      }
    } catch {
      // ignore
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(allocations))
    } catch {
      // ignore
    }
  }, [allocations])

  useEffect(() => {
    try {
      localStorage.setItem(SOUND_KEY, soundsEnabled ? '1' : '0')
    } catch {
      // ignore
    }
  }, [soundsEnabled])

  // Ensure disabled pillars stay at 0.
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
  }, [pillars])

  const placed = useMemo(() => sum(allocations), [allocations])
  const remaining = Math.max(0, totalChips - placed)

  const weights = useMemo(() => {
    const out: Record<string, number> = {}
    for (const p of pillars) {
      const chips = clampInt(allocations[p.id] || 0, 0, totalChips)
      if (chips > 0) out[p.id] = chips / totalChips
    }
    return out
  }, [allocations, pillars, totalChips])

  const triggerShake = () => setShake((n) => n + 1)

  const getCenter = (el: Element | null): { x: number; y: number } | null => {
    if (!el) return null
    const r = (el as HTMLElement).getBoundingClientRect()
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 }
  }

  const startFly = (toId: string, kind: FlyChip['kind']) => {
    const fromEl = stackRef.current
    const toEl = circleRefs.current[toId]
    const from = getCenter(fromEl)
    const to = getCenter(toEl)
    if (!from || !to) return
    setFlyChip({
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      from,
      to,
      kind: kind === 'allin' ? 'place' : kind,
    })
  }

  // Drive the chip flight animation by updating inline styles.
  useEffect(() => {
    if (!flyChip) return
    const el = flyRef.current
    if (!el) return

    const from = flyChip.from
    const to = flyChip.to
    const dx = to.x - from.x
    const dy = to.y - from.y
    const lift = Math.min(120, Math.max(60, Math.abs(dx) * 0.15 + 60))

    // Initial state
    el.style.opacity = '1'
    el.style.transform = `translate(${from.x}px, ${from.y}px) translate(-50%, -50%) scale(1)`

    // Next frame: animate to destination with a pseudo-arc using translateY offset.
    requestAnimationFrame(() => {
      el.style.transition = 'transform 420ms cubic-bezier(0.22, 0.61, 0.36, 1), opacity 420ms ease'
      el.style.transform = `translate(${from.x + dx}px, ${from.y + dy}px) translate(-50%, -50%) translateY(${-lift}px) scale(1.05)`
    })

    const t1 = setTimeout(() => {
      // Drop down to the circle center (landing bounce)
      el.style.transition = 'transform 160ms cubic-bezier(0.34, 1.56, 0.64, 1)'
      el.style.transform = `translate(${to.x}px, ${to.y}px) translate(-50%, -50%) scale(1)`
    }, 420)

    const t2 = setTimeout(() => {
      el.style.opacity = '0'
      el.style.transition = 'opacity 120ms ease'
      setFlyChip(null)
    }, 620)

    return () => {
      clearTimeout(t1)
      clearTimeout(t2)
    }
  }, [flyChip])

  const handlePlaceOne = (pillarId: string) => {
    const p = pillars.find((x) => x.id === pillarId)
    if (!p || p.disabled) return
    if (remaining <= 0) {
      triggerShake()
      return
    }

    startFly(pillarId, 'place')
    setAllocations((prev) => ({ ...prev, [pillarId]: clampInt((prev[pillarId] || 0) + 1, 0, totalChips) }))
    if (soundsEnabled) playClick('place')
    if (remaining === 1 && soundsEnabled) {
      // We'll hit zero after state applies; give a small celebratory tick now.
      setTimeout(() => playClick('complete'), 220)
    }
  }

  const handleRemoveOne = (pillarId: string) => {
    const p = pillars.find((x) => x.id === pillarId)
    if (!p || p.disabled) return
    const current = clampInt(allocations[pillarId] || 0, 0, totalChips)
    if (current <= 0) return

    // Fly back to stack: reverse (origin circle -> stack)
    const fromEl = circleRefs.current[pillarId]
    const toEl = stackRef.current
    const from = getCenter(fromEl)
    const to = getCenter(toEl)
    if (from && to) {
      setFlyChip({
        id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
        from,
        to,
        kind: 'remove',
      })
    }
    setAllocations((prev) => ({ ...prev, [pillarId]: clampInt((prev[pillarId] || 0) - 1, 0, totalChips) }))
    if (soundsEnabled) playClick('remove')
  }

  const handleAllIn = (pillarId: string) => {
    const p = pillars.find((x) => x.id === pillarId)
    if (!p || p.disabled) return
    if (remaining <= 0) return

    // Stagger chips in a quick waterfall.
    const count = remaining
    for (let i = 0; i < count; i++) {
      setTimeout(() => startFly(pillarId, 'allin'), i * 55)
    }
    setAllocations((prev) => ({ ...prev, [pillarId]: clampInt((prev[pillarId] || 0) + remaining, 0, totalChips) }))
    if (soundsEnabled) {
      // Crescendo-ish sequence
      for (let i = 0; i < Math.min(6, count); i++) {
        setTimeout(() => playClick('place'), i * 70)
      }
      setTimeout(() => playClick('complete'), 420)
    }
  }

  const reset = () => {
    setAllocations(buildAllocations(pillars))
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      // ignore
    }
  }

  const continueToResults = () => {
    if (placed <= 0) {
      setShowSkipModal(true)
      return
    }
    onComplete(weights)
  }

  const title =
    placed === 0
      ? 'Continue →'
      : remaining === 0
        ? 'Continue →'
        : `Continue (${placed} tokens) →`

  // Arc-ish layout offsets for desktop: push middle rows downward slightly.
  const desktopOffsets = [0, 10, 22, 10, 0, 0, 10, 22, 10, 0]

  return (
    <main className="hf-page hf-poker-page">
      <div className="hf-poker-ambient" aria-hidden="true" />

      <div className="hf-poker-topbar">
        <div className="hf-container" style={{ marginTop: 0, paddingTop: '1.25rem', paddingBottom: '0.75rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              {onBack ? (
                <button onClick={onBack} className="hf-btn-link hf-poker-btn" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                  <ArrowLeft size={18} /> Back
                </button>
              ) : null}
            </div>

            <div style={{ textAlign: 'center', flex: '1 1 auto', minWidth: 280 }}>
              <div className="hf-poker-title">💰 Spend your tokens</div>
              <div className="hf-poker-subtitle">
                You have {totalChips} tokens. Spend them on what matters most.
              </div>
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <label className="hf-poker-toggle">
                <input type="checkbox" checked={soundsEnabled} onChange={(e) => setSoundsEnabled(e.target.checked)} />
                <span>Sounds</span>
              </label>
              <button onClick={reset} className="hf-btn-link hf-poker-btn" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                <RefreshCcw size={16} /> Reset
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="hf-container" style={{ marginTop: 0, paddingTop: '1rem', paddingBottom: '6rem' }}>
        {/* Chip stack */}
        <div
          ref={stackRef}
          className={shake ? `hf-chip-stack hf-chip-stack--shake-${shake}` : 'hf-chip-stack'}
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          <div className="hf-chip-stack__label">
            <Coins size={16} /> Your token stack
          </div>
          <div className="hf-chip-stack__row" aria-hidden="true">
            {Array.from({ length: Math.min(remaining, 10) }).map((_, i) => (
              <div key={i} className="hf-chip hf-chip--stack" style={{ transform: `translate(${i * 6}px, ${-i * 2}px)` }} />
            ))}
          </div>
          <div className="hf-chip-stack__count">
            <span className="hf-chip-stack__countValue">{remaining}</span> tokens left
          </div>
        </div>

        {/* Felt table */}
        <div className="hf-felt">
          <div className="hf-felt__inner">
            <div className="hf-felt__grid">
              {pillars.map((p, idx) => {
                const chips = clampInt(allocations[p.id] || 0, 0, totalChips)
                const disabled = Boolean(p.disabled)
                const offset = desktopOffsets[idx] ?? 0
                return (
                  <div
                    key={p.id}
                    className={disabled ? 'hf-bet-circle hf-bet-circle--disabled' : chips > 0 ? 'hf-bet-circle hf-bet-circle--active' : 'hf-bet-circle'}
                    style={{ ['--hf-circle-offset' as any]: `${offset}px` }}
                    ref={(el) => {
                      circleRefs.current[p.id] = el
                    }}
                  >
                    <button
                      type="button"
                      className="hf-bet-circle__hit"
                      onClick={() => handlePlaceOne(p.id)}
                      disabled={disabled}
                      aria-label={
                        disabled
                          ? `${p.label} is locked.`
                          : `Add 1 token to ${p.label}. Currently ${chips} tokens allocated. ${remaining} remaining.`
                      }
                      title={disabled ? 'Locked' : 'Tap to add 1 token'}
                    >
                      <div className="hf-bet-circle__icon">{p.icon}</div>
                      <div className="hf-bet-circle__label">{p.label}</div>
                      <div className="hf-bet-circle__chips" aria-hidden="true">
                        {chips > 0 ? (
                          <div className="hf-chip-stack-mini">
                            {Array.from({ length: Math.min(chips, 6) }).map((_, i) => (
                              <div
                                key={i}
                                className="hf-chip hf-chip--mini"
                                style={{ transform: `translate(${i * 2}px, ${-i * 3}px)` }}
                              />
                            ))}
                          </div>
                        ) : (
                          <div className="hf-bet-circle__empty">No tokens</div>
                        )}
                        <div className="hf-bet-circle__count">{chips}</div>
                      </div>
                    </button>

                    <div className="hf-bet-circle__actions">
                      <button
                        type="button"
                        className="hf-bet-circle__btn"
                        onClick={() => handleRemoveOne(p.id)}
                        disabled={disabled || chips <= 0}
                        aria-label={`Remove 1 token from ${p.label}. Currently ${chips} tokens allocated.`}
                        title="Remove 1 token"
                      >
                        –1
                      </button>
                      <button
                        type="button"
                        className="hf-bet-circle__btn"
                        onClick={() => {
                          setAllInTarget(p.id)
                          setShowAllIn(true)
                        }}
                        disabled={disabled || remaining <= 0}
                        aria-label={`Add all remaining tokens to ${p.label}.`}
                        title="Add all remaining"
                      >
                        Add all
                      </button>
                    </div>

                    <div className="hf-bet-circle__hint">
                      <span className="hf-bet-circle__desc">{p.description}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Flying chip overlay */}
      <div className="hf-fly-layer" aria-hidden="true">
        <div ref={flyRef} className={flyChip?.kind === 'remove' ? 'hf-chip hf-chip--fly hf-chip--fly-remove' : 'hf-chip hf-chip--fly'} />
      </div>

      {/* Bottom action bar */}
      <div className="hf-poker-footer">
        <div className="hf-container" style={{ marginTop: 0, paddingTop: '0.9rem', paddingBottom: '0.9rem' }}>
          <div className="hf-poker-footer__row">
            <div className="hf-poker-footer__left">
              {remaining === 0 ? (
                <div className="hf-poker-footer__status hf-poker-footer__status--good">All tokens allocated. Ready to continue.</div>
              ) : (
                <div className="hf-poker-footer__status">Tokens left to allocate: {remaining}</div>
              )}
            </div>
            <div className="hf-poker-footer__right">
              <button
                type="button"
                className="hf-btn-link hf-poker-btn"
                onClick={() => setShowSkipModal(true)}
                style={{ border: '1px solid rgba(255,255,255,0.22)', color: '#f8f9fa' }}
              >
                Skip
              </button>
              <button
                type="button"
                className={remaining === 0 && placed > 0 ? 'hf-poker-primary hf-poker-primary--glow' : 'hf-poker-primary'}
                onClick={continueToResults}
              >
                {title}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* All-in confirm modal */}
      {showAllIn ? (
        <div
          className="hf-modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label="Add all remaining confirmation"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setShowAllIn(false)
          }}
        >
          <div className="hf-card" style={{ maxWidth: 560, width: '100%' }}>
            <div style={{ fontSize: '1.35rem', fontWeight: 900, color: 'var(--hf-text-primary)' }}>Add all remaining tokens?</div>
            <div className="hf-muted" style={{ marginTop: '0.5rem' }}>
              This will place <strong>all remaining tokens</strong> on{' '}
              <strong>{pillars.find((p) => p.id === allInTarget)?.label || 'this pillar'}</strong>.
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.5rem' }}>
              <button
                type="button"
                className="hf-btn-link"
                onClick={() => setShowAllIn(false)}
                style={{ border: '1px solid var(--hf-border)', color: 'var(--hf-text-primary)' }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="hf-btn-primary"
                onClick={() => {
                  const id = allInTarget
                  setShowAllIn(false)
                  handleAllIn(id)
                }}
              >
                Add all
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {/* Skip confirm modal */}
      {showSkipModal ? (
        <div
          className="hf-modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label="Skip token budgeting confirmation"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setShowSkipModal(false)
          }}
        >
          <div className="hf-card" style={{ maxWidth: 560, width: '100%' }}>
            <div style={{ fontSize: '1.35rem', fontWeight: 900, color: 'var(--hf-text-primary)' }}>Skip priorities?</div>
            <div className="hf-muted" style={{ marginTop: '0.5rem' }}>
              We’ll weight all pillars equally.
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.5rem' }}>
              <button
                type="button"
                className="hf-btn-link"
                onClick={() => setShowSkipModal(false)}
                style={{ border: '1px solid var(--hf-border)', color: 'var(--hf-text-primary)' }}
              >
                Go back
              </button>
              <button
                type="button"
                className="hf-btn-primary"
                onClick={() => {
                  setShowSkipModal(false)
                  onComplete({})
                }}
              >
                Skip
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  )
}


'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import { getSavedScore, type SavedScoreRow } from '@/lib/savedScores'
import { reweightScoreResponseFromPriorities } from '@/lib/reweight'
import { PILLAR_META, PILLAR_ORDER, isLongevityPillar, type PillarKey } from '@/lib/pillars'
import type { ScoreResponse } from '@/types/api'
import { DEFAULT_PRIORITIES, type PillarPriorities } from '@/components/SearchOptions'

function prioritiesFromRow(row: SavedScoreRow): PillarPriorities {
  const p = row.priorities as Record<string, string> | null | undefined
  if (!p || typeof p !== 'object') return { ...DEFAULT_PRIORITIES }
  const levels = ['None', 'Low', 'Medium', 'High'] as const
  const out: Record<string, (typeof levels)[number]> = { ...DEFAULT_PRIORITIES }
  for (const k of Object.keys(out)) {
    const v = String(p[k] ?? '').trim()
    if (levels.includes(v as (typeof levels)[number])) {
      out[k] = v as (typeof levels)[number]
    }
  }
  return out as unknown as PillarPriorities
}

function placeDisplayName(row: SavedScoreRow): string {
  const input = typeof row.input === 'string' ? row.input.trim() : ''
  if (input) return input
  const loc = row.location_info as { city?: string; state?: string; zip?: string }
  const fallback = [loc.city ?? '', loc.state ?? '', loc.zip ?? ''].filter(Boolean).join(', ')
  return fallback || 'Unknown location'
}

type ComparePillarSide = {
  score: number | null
  confidence: number | null
  hasScore: boolean
}

type ComparePillarRow = {
  key: PillarKey
  meta: (typeof PILLAR_META)[PillarKey]
  isLongevity: boolean
  a: ComparePillarSide
  b: ComparePillarSide
}

type SortBy = 'diff' | 'a' | 'b'

function getTier(score: number): { label: string } {
  if (score >= 90) return { label: 'Excellent' }
  if (score >= 75) return { label: 'Good' }
  if (score >= 60) return { label: 'Fair' }
  return { label: 'Poor' }
}

export default function ComparePage() {
  const { user, loading: authLoading } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()
  const idA = searchParams.get('a')
  const idB = searchParams.get('b')

  const [rowA, setRowA] = useState<SavedScoreRow | null>(null)
  const [rowB, setRowB] = useState<SavedScoreRow | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [sortBy, setSortBy] = useState<SortBy>('diff')

  useEffect(() => {
    if (!idA || !idB || idA === idB) {
      setError('Select two different saved places to compare.')
      setLoading(false)
      return
    }
    if (!user) {
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    Promise.all([getSavedScore(idA), getSavedScore(idB)])
      .then(([a, b]) => {
        if (cancelled) return
        setRowA(a)
        setRowB(b)
      })
      .catch((e) => {
        if (cancelled) return
        setError(e instanceof Error ? e.message : 'Failed to load places for compare.')
      })
      .finally(() => {
        if (cancelled) return
        setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [idA, idB, user])

  if (!authLoading && !user) {
    router.replace('/saved')
    return null
  }

  const scoredA = rowA?.score_payload as ScoreResponse | undefined
  const scoredB = rowB?.score_payload as ScoreResponse | undefined

  const displayA = useMemo(() => {
    if (!rowA || !scoredA) return null
    const pri = prioritiesFromRow(rowA)
    return reweightScoreResponseFromPriorities(scoredA, pri)
  }, [rowA, scoredA])

  const displayB = useMemo(() => {
    if (!rowB || !scoredB) return null
    const pri = prioritiesFromRow(rowB)
    return reweightScoreResponseFromPriorities(scoredB, pri)
  }, [rowB, scoredB])

  const homefitA = typeof displayA?.total_score === 'number' ? displayA.total_score : null
  const homefitB = typeof displayB?.total_score === 'number' ? displayB.total_score : null
  const longevityA = typeof displayA?.longevity_index === 'number' ? displayA.longevity_index : null
  const longevityB = typeof displayB?.longevity_index === 'number' ? displayB.longevity_index : null

  const placeNameA = rowA ? placeDisplayName(rowA) : 'Place A'
  const placeNameB = rowB ? placeDisplayName(rowB) : 'Place B'

  const pillars: ComparePillarRow[] = useMemo(() => {
    if (!displayA || !displayB) return []
    const aPillars = displayA.livability_pillars as unknown as Record<string, { score?: number; confidence?: number }>
    const bPillars = displayB.livability_pillars as unknown as Record<string, { score?: number; confidence?: number }>
    return PILLAR_ORDER.map((key) => {
      const pa = aPillars[key]
      const pb = bPillars[key]
      const scoreA = typeof pa?.score === 'number' ? pa.score : null
      const scoreB = typeof pb?.score === 'number' ? pb.score : null
      const confA = typeof pa?.confidence === 'number' ? pa.confidence : null
      const confB = typeof pb?.confidence === 'number' ? pb.confidence : null
      return {
        key,
        meta: PILLAR_META[key],
        isLongevity: isLongevityPillar(key),
        a: { score: scoreA, confidence: confA, hasScore: scoreA != null },
        b: { score: scoreB, confidence: confB, hasScore: scoreB != null },
      }
    })
  }, [displayA, displayB])

  const wins = useMemo(() => {
    let aWins = 0
    let bWins = 0
    pillars.forEach((p) => {
      if (!p.a.hasScore || !p.b.hasScore) return
      if (p.a.score! > p.b.score!) aWins += 1
      else if (p.b.score! > p.a.score!) bWins += 1
    })
    return { aWins, bWins }
  }, [pillars])

  const sortedPillars: ComparePillarRow[] = useMemo(() => {
    const base = [...pillars]
    const value = (p: ComparePillarRow) => {
      const a = p.a.score
      const b = p.b.score
      if (a == null || b == null) return -1
      if (sortBy === 'diff') return Math.abs(a - b)
      if (sortBy === 'a') return a
      return b
    }
    base.sort((p1, p2) => {
      const v1 = value(p1)
      const v2 = value(p2)
      if (v1 === -1 && v2 === -1) return 0
      if (v1 === -1) return 1
      if (v2 === -1) return -1
      return v2 - v1
    })
    return base
  }, [pillars, sortBy])

  const summary = useMemo(() => {
    if (!pillars.length) {
      return { aLeads: [] as string[], bLeads: [] as string[], aUnscored: 0, bUnscored: 0 }
    }
    type Lead = { key: PillarKey; delta: number }
    const aLeads: Lead[] = []
    const bLeads: Lead[] = []
    let aUnscored = 0
    let bUnscored = 0
    pillars.forEach((p) => {
      if (!p.a.hasScore) aUnscored += 1
      if (!p.b.hasScore) bUnscored += 1
      if (p.a.hasScore && p.b.hasScore) {
        const delta = (p.a.score ?? 0) - (p.b.score ?? 0)
        if (delta > 0) aLeads.push({ key: p.key, delta })
        else if (delta < 0) bLeads.push({ key: p.key, delta: -delta })
      }
    })
    const byDelta = (arr: Lead[]) =>
      arr
        .sort((x, y) => y.delta - x.delta)
        .slice(0, 3)
        .map((item) => PILLAR_META[item.key].name)
    return {
      aLeads: byDelta(aLeads),
      bLeads: byDelta(bLeads),
      aUnscored,
      bUnscored,
    }
  }, [pillars])

  const homefitWinner =
    homefitA != null && homefitB != null
      ? homefitA > homefitB
        ? 'a'
        : homefitB > homefitA
          ? 'b'
          : 'tie'
      : 'tie'

  const totalPillars = PILLAR_ORDER.length

  return (
    <main className="hf-page hf-page-no-hero">
      <div className="hf-container">
        <nav
          style={{
            position: 'sticky',
            top: 0,
            zIndex: 100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '0.75rem',
            padding: '0.75rem 0.25rem',
            backdropFilter: 'blur(12px)',
            background: 'color-mix(in srgb, var(--hf-page-bg) 80%, transparent)',
            borderBottom: '1px solid var(--hf-border)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0 }}>
            <Link href="/saved" className="hf-btn-link" style={{ fontSize: '0.9rem' }}>
              ← My places
            </Link>
            <span className="hf-muted" style={{ fontSize: '0.85rem' }}>
              Comparing
            </span>
            <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--hf-homefit-green)', whiteSpace: 'nowrap' }}>
              {placeNameA}
            </span>
            <span className="hf-muted" style={{ fontSize: '0.85rem' }}>
              vs
            </span>
            <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--hf-longevity-purple)', whiteSpace: 'nowrap' }}>
              {placeNameB}
            </span>
          </div>
        </nav>

        {loading && (
          <p className="hf-muted" style={{ marginTop: '1.5rem' }}>
            Loading comparison…
          </p>
        )}
        {!loading && error && (
          <div className="hf-card" style={{ marginTop: '1.5rem' }}>
            <p className="hf-auth-error" role="alert">
              {error}
            </p>
            <Link href="/saved" className="hf-btn-link" style={{ marginTop: '0.5rem', display: 'inline-block' }}>
              ← Back to My places
            </Link>
          </div>
        )}

        {!loading && !error && displayA && displayB && (
          <>
            <section
              aria-label="Overall comparison"
              style={{
                position: 'sticky',
                top: 48,
                zIndex: 90,
                marginTop: '0.75rem',
                background: 'var(--hf-card-bg)',
                borderRadius: 16,
                border: '1px solid var(--hf-border)',
                boxShadow: '0 6px 18px rgba(0,0,0,0.05)',
                overflow: 'hidden',
              }}
            >
              <div style={{ display: 'flex', height: 4 }}>
                <div
                  style={{
                    flex: 1,
                    background:
                      homefitWinner === 'a'
                        ? 'var(--hf-homefit-green)'
                        : 'color-mix(in srgb, var(--hf-border) 70%, transparent)',
                  }}
                />
                <div
                  style={{
                    flex: 1,
                    background:
                      homefitWinner === 'b'
                        ? 'var(--hf-longevity-purple)'
                        : 'color-mix(in srgb, var(--hf-border) 70%, transparent)',
                  }}
                />
              </div>
              <div
                style={{
                  padding: '0.9rem 1.25rem 0.4rem',
                  display: 'grid',
                  gridTemplateColumns: 'minmax(0,1fr) auto minmax(0,1fr)',
                  gap: '1.25rem',
                  alignItems: 'center',
                }}
              >
                <div style={{ textAlign: 'left', minWidth: 0 }}>
                  <div className="hf-label" style={{ marginBottom: '0.25rem', fontSize: '0.8rem' }}>
                    {placeNameA.toUpperCase()}
                  </div>
                  <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--hf-homefit-green)' }}>
                    {homefitA != null ? homefitA.toFixed(1) : '—'}
                  </div>
                  <div className="hf-muted" style={{ fontSize: '0.85rem', marginTop: '0.15rem' }}>
                    HomeFit Score
                  </div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 600, marginTop: '0.35rem', color: 'var(--hf-longevity-purple)' }}>
                    {longevityA != null ? `Longevity ${longevityA.toFixed(1)}` : 'Longevity —'}
                  </div>
                  <div className="hf-muted" style={{ fontSize: '0.8rem', marginTop: '0.15rem' }}>
                    Wins {wins.aWins} of {totalPillars} pillars
                  </div>
                </div>

                <div style={{ textAlign: 'center' }}>
                  <div
                    style={{
                      width: 56,
                      height: 56,
                      borderRadius: '50%',
                      border: '2px solid var(--hf-border)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 700,
                      fontSize: '0.9rem',
                    }}
                  >
                    VS
                  </div>
                </div>

                <div style={{ textAlign: 'right', minWidth: 0 }}>
                  <div className="hf-label" style={{ marginBottom: '0.25rem', fontSize: '0.8rem' }}>
                    {placeNameB.toUpperCase()}
                  </div>
                  <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--hf-longevity-purple)' }}>
                    {homefitB != null ? homefitB.toFixed(1) : '—'}
                  </div>
                  <div className="hf-muted" style={{ fontSize: '0.85rem', marginTop: '0.15rem' }}>
                    HomeFit Score
                  </div>
                  <div style={{ fontSize: '0.95rem', fontWeight: 600, marginTop: '0.35rem', color: 'var(--hf-homefit-green)' }}>
                    {longevityB != null ? `Longevity ${longevityB.toFixed(1)}` : 'Longevity —'}
                  </div>
                  <div className="hf-muted" style={{ fontSize: '0.8rem', marginTop: '0.15rem' }}>
                    Wins {wins.bWins} of {totalPillars} pillars
                  </div>
                </div>
              </div>

              <div
                style={{
                  borderTop: '1px solid var(--hf-border)',
                  padding: '0.5rem 1.25rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '0.75rem',
                  flexWrap: 'wrap',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <span className="hf-label" style={{ fontSize: '0.75rem' }}>
                    SORT BY
                  </span>
                  <div style={{ display: 'inline-flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      onClick={() => setSortBy('diff')}
                      className={sortBy === 'diff' ? 'hf-btn-secondary' : 'hf-btn-link'}
                      style={{
                        fontSize: '0.85rem',
                        padding: '0.3rem 0.75rem',
                        borderRadius: 999,
                      }}
                    >
                      Biggest difference
                    </button>
                    <button
                      type="button"
                      onClick={() => setSortBy('a')}
                      className={sortBy === 'a' ? 'hf-btn-secondary' : 'hf-btn-link'}
                      style={{
                        fontSize: '0.85rem',
                        padding: '0.3rem 0.75rem',
                        borderRadius: 999,
                      }}
                    >
                      {placeNameA}
                    </button>
                    <button
                      type="button"
                      onClick={() => setSortBy('b')}
                      className={sortBy === 'b' ? 'hf-btn-secondary' : 'hf-btn-link'}
                      style={{
                        fontSize: '0.85rem',
                        padding: '0.3rem 0.75rem',
                        borderRadius: 999,
                      }}
                    >
                      {placeNameB}
                    </button>
                  </div>
                </div>
                <div className="hf-muted" style={{ fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      background: 'var(--hf-homefit-green)',
                    }}
                  />
                  <span>Longevity pillar</span>
                </div>
              </div>
            </section>

            <section style={{ marginTop: '1rem' }}>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '200px minmax(0,1fr) 80px minmax(0,1fr)',
                  gap: '0.5rem',
                  padding: '0.5rem 0.75rem',
                  borderBottom: '1px solid var(--hf-border)',
                  fontSize: '0.8rem',
                  textTransform: 'uppercase',
                  color: 'var(--hf-text-secondary)',
                }}
              >
                <div>Pillar</div>
                <div style={{ textAlign: 'center', color: 'var(--hf-homefit-green)', fontWeight: 600 }}>
                  {placeNameA.toUpperCase()}
                </div>
                <div />
                <div style={{ textAlign: 'center', color: 'var(--hf-longevity-purple)', fontWeight: 600 }}>
                  {placeNameB.toUpperCase()}
                </div>
              </div>

              <div
                style={{
                  borderRadius: 16,
                  border: '1px solid var(--hf-border)',
                  overflow: 'hidden',
                  marginTop: '0.5rem',
                }}
              >
                {sortedPillars.map((p, idx) => {
                  const aScore = p.a.score
                  const bScore = p.b.score
                  const bothScored = p.a.hasScore && p.b.hasScore
                  const winner =
                    bothScored && aScore != null && bScore != null
                      ? aScore > bScore
                        ? 'a'
                        : bScore > aScore
                          ? 'b'
                          : 'tie'
                      : 'none'
                  const delta = bothScored && aScore != null && bScore != null ? aScore - bScore : null
                  const absDelta = delta != null ? Math.abs(delta) : 0
                  const maxDelta = 50
                  const fillPct = Math.min(1, absDelta / maxDelta) * 100
                  return (
                    <div
                      key={p.key}
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '200px minmax(0,1fr) 80px minmax(0,1fr)',
                        gap: '0.75rem',
                        padding: '0.75rem 0.75rem',
                        background: idx % 2 === 0 ? 'var(--hf-card-bg)' : 'var(--hf-bg-subtle)',
                        borderTop: idx === 0 ? 'none' : '1px solid var(--hf-border)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span style={{ fontSize: '1.2rem' }}>{p.meta.icon}</span>
                        <div>
                          <div style={{ fontWeight: 700, color: 'var(--hf-text-primary)', fontSize: '0.95rem' }}>
                            {p.meta.name}
                          </div>
                          {p.isLongevity && (
                            <div style={{ marginTop: '0.15rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                              <span
                                style={{
                                  width: 8,
                                  height: 8,
                                  borderRadius: '50%',
                                  background: 'var(--hf-homefit-green)',
                                }}
                              />
                              <span className="hf-muted" style={{ fontSize: '0.8rem' }}>
                                Longevity
                              </span>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Place A column */}
                      <div
                        style={{
                          textAlign: 'center',
                          paddingLeft: '0.5rem',
                          borderLeft:
                            winner === 'a'
                              ? '3px solid var(--hf-homefit-green)'
                              : '3px solid transparent',
                        }}
                      >
                        {p.a.hasScore && aScore != null ? (
                          <>
                            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--hf-text-primary)' }}>
                              {aScore.toFixed(0)}
                            </div>
                            <div
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                padding: '0.15rem 0.5rem',
                                borderRadius: 999,
                                border: '1px solid var(--hf-border)',
                                fontSize: '0.75rem',
                                marginTop: '0.1rem',
                              }}
                            >
                              {getTier(aScore).label}
                            </div>
                            <div className="hf-muted" style={{ fontSize: '0.75rem', marginTop: '0.2rem' }}>
                              {p.a.confidence != null ? `${p.a.confidence.toFixed(0)}% confidence` : '—'}
                            </div>
                          </>
                        ) : (
                          <div className="hf-muted" style={{ opacity: 0.5, fontSize: '0.85rem' }}>
                            —<br />
                            <span style={{ fontSize: '0.75rem' }}>Not scored</span>
                            <br />
                            <button
                              type="button"
                              onClick={() => router.push(`/saved/${idA ?? ''}?pillar=${p.key}`)}
                              className="hf-btn-link"
                              style={{ fontSize: '0.8rem', paddingTop: '0.15rem' }}
                            >
                              + Score
                            </button>
                          </div>
                        )}
                      </div>

                      {/* Delta bar */}
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '0.8rem',
                          color: 'var(--hf-text-secondary)',
                        }}
                      >
                        {bothScored && delta != null ? (
                          <div
                            style={{
                              width: '100%',
                              display: 'flex',
                              alignItems: 'center',
                              gap: 2,
                            }}
                          >
                            <div
                              style={{
                                flex: 1,
                                height: 4,
                                background: 'var(--hf-border)',
                                borderRadius: 999,
                                overflow: 'hidden',
                              }}
                            >
                              {delta > 0 && (
                                <div
                                  style={{
                                    width: `${fillPct}%`,
                                    height: '100%',
                                    background: 'var(--hf-homefit-green)',
                                  }}
                                />
                              )}
                            </div>
                            <div style={{ minWidth: 24, textAlign: 'center', fontSize: '0.8rem' }}>
                              {absDelta < 0.5 ? '=' : `${delta > 0 ? '+' : '-'}${absDelta.toFixed(0)}`}
                            </div>
                            <div
                              style={{
                                flex: 1,
                                height: 4,
                                background: 'var(--hf-border)',
                                borderRadius: 999,
                                overflow: 'hidden',
                              }}
                            >
                              {delta < 0 && (
                                <div
                                  style={{
                                    width: `${fillPct}%`,
                                    height: '100%',
                                    background: 'var(--hf-longevity-purple)',
                                  }}
                                />
                              )}
                            </div>
                          </div>
                        ) : null}
                      </div>

                      {/* Place B column */}
                      <div
                        style={{
                          textAlign: 'center',
                          paddingRight: '0.5rem',
                          borderRight:
                            winner === 'b'
                              ? '3px solid var(--hf-longevity-purple)'
                              : '3px solid transparent',
                        }}
                      >
                        {p.b.hasScore && bScore != null ? (
                          <>
                            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--hf-text-primary)' }}>
                              {bScore.toFixed(0)}
                            </div>
                            <div
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                padding: '0.15rem 0.5rem',
                                borderRadius: 999,
                                border: '1px solid var(--hf-border)',
                                fontSize: '0.75rem',
                                marginTop: '0.1rem',
                              }}
                            >
                              {getTier(bScore).label}
                            </div>
                            <div className="hf-muted" style={{ fontSize: '0.75rem', marginTop: '0.2rem' }}>
                              {p.b.confidence != null ? `${p.b.confidence.toFixed(0)}% confidence` : '—'}
                            </div>
                          </>
                        ) : (
                          <div className="hf-muted" style={{ opacity: 0.5, fontSize: '0.85rem' }}>
                            —<br />
                            <span style={{ fontSize: '0.75rem' }}>Not scored</span>
                            <br />
                            <button
                              type="button"
                              onClick={() => router.push(`/saved/${idB ?? ''}?pillar=${p.key}`)}
                              className="hf-btn-link"
                              style={{ fontSize: '0.8rem', paddingTop: '0.15rem' }}
                            >
                              + Score
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </section>

            <section
              style={{
                marginTop: '1.75rem',
                marginBottom: '2.5rem',
                padding: '1rem 1.25rem',
                borderRadius: 12,
                background: 'var(--hf-bg-subtle)',
                border: '1px solid var(--hf-border)',
                maxWidth: 700,
              }}
            >
              <div className="hf-label" style={{ marginBottom: '0.5rem' }}>
                Summary
              </div>
              <p
                style={{
                  margin: 0,
                  fontSize: '0.98rem',
                  lineHeight: 1.5,
                  color: 'var(--hf-text-primary)',
                }}
              >
                <strong style={{ color: 'var(--hf-homefit-green)' }}>{placeNameA}</strong> leads on{' '}
                {summary.aLeads.length ? summary.aLeads.join(', ') : 'no pillars yet'}.
                {' '}
                <strong style={{ color: 'var(--hf-longevity-purple)' }}>{placeNameB}</strong> leads on{' '}
                {summary.bLeads.length ? summary.bLeads.join(', ') : 'no pillars yet'}.
                {(summary.aUnscored > 0 || summary.bUnscored > 0) && (
                  <>
                    {' '}
                    {summary.aUnscored > 0 && (
                      <>
                        {summary.aUnscored} pillar{summary.aUnscored === 1 ? '' : 's'} unscored for {placeNameA}.
                      </>
                    )}
                    {summary.bUnscored > 0 && (
                      <>
                        {' '}
                        {summary.bUnscored} pillar{summary.bUnscored === 1 ? '' : 's'} unscored for {placeNameB}.
                      </>
                    )}{' '}
                    Use the <span style={{ fontWeight: 600 }}>+ Score</span> links above to fill the gaps.
                  </>
                )}
              </p>
            </section>
          </>
        )}
      </div>
    </main>
  )
}


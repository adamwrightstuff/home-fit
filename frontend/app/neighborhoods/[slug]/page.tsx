import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import {
  findNeighborhoodBySlug,
  getAllNeighborhoodSlugs,
  type NeighborhoodEntry,
} from '@/lib/catalogServer'
import {
  PILLAR_ORDER,
  PILLAR_META,
  getScoreBand,
  HOMEFIT_COPY,
  LONGEVITY_COPY,
  HAPPINESS_INDEX_COPY,
} from '@/lib/pillars'
import { CATALOG_METRO_META } from '@/lib/catalogMetros'
import NeighborhoodMap from '@/components/NeighborhoodMap'
import NeighborhoodPersonal from '@/components/NeighborhoodPersonal'

export const dynamicParams = false

const SITE_URL = 'https://www.trovamo.co'

export async function generateStaticParams() {
  return getAllNeighborhoodSlugs().map((slug) => ({ slug }))
}

function pillarScores(entry: NeighborhoodEntry): Record<string, number | null> {
  const pillars = (entry.score.livability_pillars ?? {}) as Record<string, { score?: number }>
  const out: Record<string, number | null> = {}
  for (const key of PILLAR_ORDER) {
    const v = pillars[key]?.score
    out[key] = typeof v === 'number' && Number.isFinite(v) ? v : null
  }
  return out
}

function pageTitle(entry: NeighborhoodEntry): string {
  const { catalog, score } = entry
  const total = typeof score.total_score === 'number' ? Math.round(score.total_score) : null
  const where = [catalog.county_borough, catalog.state_abbr].filter(Boolean).join(', ')
  return `${catalog.name}${where ? `, ${where}` : ''}: HomeFit${total != null ? ` ${total}` : ''} | Trovamo`
}

function pageDescription(entry: NeighborhoodEntry): string {
  const summary = entry.score.place_summary
  if (typeof summary === 'string' && summary.trim()) {
    return summary.length > 160 ? summary.slice(0, 157).trimEnd() + '…' : summary
  }
  const { catalog, score } = entry
  const total = typeof score.total_score === 'number' ? Math.round(score.total_score) : null
  return `${catalog.name} scores${total != null ? ` ${total}` : ''} for livability across Trovamo's 12 pillars: schools, safety, transit, nature, and more.`
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>
}): Promise<Metadata> {
  const { slug } = await params
  const entry = findNeighborhoodBySlug(slug)
  if (!entry) return { title: 'Neighborhood not found | Trovamo' }
  const title = pageTitle(entry)
  const description = pageDescription(entry)
  const url = `${SITE_URL}/neighborhoods/${slug}`
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: {
      title,
      description,
      url,
      siteName: 'Trovamo',
      type: 'website',
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
    },
  }
}

function ScoreHero({
  label,
  value,
  tooltip,
  accent,
}: {
  label: string
  value: number | null
  tooltip: string
  accent: string
}) {
  return (
    <div
      className="flex flex-col items-center rounded-2xl border border-[var(--hf-border)] bg-[var(--hf-card-bg)] px-4 py-5"
      title={tooltip}
    >
      <div className="text-[0.65rem] font-semibold uppercase tracking-[0.08em] text-[var(--hf-text-tertiary)]">
        {label}
      </div>
      <div className="mt-1 text-4xl font-bold tabular-nums" style={{ color: accent }}>
        {value != null && Number.isFinite(value) ? value.toFixed(0) : 'n/a'}
      </div>
      <div className="mt-1 text-[0.7rem] text-[var(--hf-text-tertiary)]">out of 100</div>
    </div>
  )
}

export default async function NeighborhoodPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  const entry = findNeighborhoodBySlug(slug)
  if (!entry) notFound()

  const { catalog, score, metro, work_commute } = entry
  const metroLabel = CATALOG_METRO_META[metro]?.label ?? metro.toUpperCase()
  const scores = pillarScores(entry)
  const twinKey = encodeURIComponent(
    `${catalog.name}|${catalog.county_borough ?? ''}|${catalog.state_abbr ?? ''}`
  )
  const typeLabel = catalog.type
    ? catalog.type.charAt(0).toUpperCase() + catalog.type.slice(1)
    : null

  return (
    <main className="mx-auto w-full max-w-3xl px-4 pb-16 pt-6">
      {/* Breadcrumb */}
      <nav className="mb-4 text-xs text-[var(--hf-text-tertiary)]" aria-label="Breadcrumb">
        <Link href="/catalog" className="hover:underline">
          Neighborhoods
        </Link>
        <span className="mx-1.5">/</span>
        <span>{metroLabel}</span>
        <span className="mx-1.5">/</span>
        <span className="text-[var(--hf-text-secondary)]">{catalog.name}</span>
      </nav>

      {/* Header */}
      <header className="mb-6">
        <h1
          className="text-3xl font-bold leading-tight text-[var(--hf-text-primary)]"
          style={{ fontFamily: 'var(--hf-font-display, inherit)' }}
        >
          {catalog.name}
        </h1>
        <p className="mt-1 text-sm text-[var(--hf-text-secondary)]">
          {[catalog.county_borough, catalog.state_abbr].filter(Boolean).join(', ')}
          {typeLabel ? ` · ${typeLabel}` : ''}
        </p>
      </header>

      {/* Map */}
      <div className="mb-6">
        <NeighborhoodMap
          location={`${catalog.name}, ${catalog.county_borough ?? ''} ${catalog.state_abbr ?? ''}`.replace(/\s+/g, ' ').trim()}
          score={score}
        />
      </div>

      {/* Score hero */}
      <section className="mb-6 grid grid-cols-3 gap-3" aria-label="Scores">
        <ScoreHero
          label="HomeFit"
          value={typeof score.total_score === 'number' ? score.total_score : null}
          tooltip={HOMEFIT_COPY.tooltip}
          accent="var(--hf-primary-1)"
        />
        <ScoreHero
          label="Longevity"
          value={typeof score.longevity_index === 'number' ? score.longevity_index : null}
          tooltip={LONGEVITY_COPY.tooltip}
          accent="var(--hf-primary-2)"
        />
        <ScoreHero
          label="Happiness"
          value={typeof score.happiness_index === 'number' ? score.happiness_index : null}
          tooltip={HAPPINESS_INDEX_COPY.tooltip}
          accent="var(--tr-accent-800)"
        />
      </section>

      {/* Summary */}
      {typeof score.place_summary === 'string' && score.place_summary.trim() && (
        <p className="mb-8 text-[0.95rem] leading-relaxed text-[var(--hf-text-secondary)]">
          {score.place_summary}
        </p>
      )}

      {/* Pillar breakdown */}
      <section className="mb-8" aria-label="Pillar breakdown">
        <h2 className="mb-3 text-lg font-bold text-[var(--hf-text-primary)]">
          The 12 pillars
        </h2>
        <div className="overflow-hidden rounded-2xl border border-[var(--hf-border)] bg-[var(--hf-card-bg)]">
          {PILLAR_ORDER.map((key, i) => {
            const meta = PILLAR_META[key]
            const v = scores[key]
            const band = v != null ? getScoreBand(v) : null
            return (
              <div
                key={key}
                className={`px-4 py-3 ${i > 0 ? 'border-t border-[var(--hf-border)]' : ''}`}
                title={meta.description}
              >
                <div className="flex items-baseline justify-between gap-3">
                  <div className="min-w-0">
                    <span className="mr-1.5">{meta.icon}</span>
                    <span className="text-sm font-semibold text-[var(--hf-text-primary)]">
                      {meta.name}
                    </span>
                  </div>
                  <div className="flex shrink-0 items-baseline gap-2">
                    {band && (
                      <span
                        className="text-[0.7rem] font-semibold"
                        style={{ color: band.color }}
                      >
                        {band.label}
                      </span>
                    )}
                    <span className="w-8 text-right text-sm font-bold tabular-nums text-[var(--hf-text-primary)]">
                      {v != null ? v.toFixed(0) : 'n/a'}
                    </span>
                  </div>
                </div>
                <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-[var(--hf-bg-subtle)]">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${v != null ? Math.max(0, Math.min(100, v)) : 0}%`,
                      background: band?.color ?? 'var(--hf-border)',
                    }}
                  />
                </div>
              </div>
            )
          })}
        </div>
        <p className="mt-3 text-xs leading-relaxed text-[var(--hf-text-tertiary)]">
          Scores are computed across 12 pillars with equal weights by default.{' '}
          <Link href="/quiz" className="font-semibold text-[var(--hf-primary-1)] hover:underline">
            Take the quiz
          </Link>{' '}
          to re-weight them around what matters most to you.
        </p>
      </section>

      {/* Who lives here: neutral description, no score and no weight */}
      {(() => {
        const age = (score.livability_pillars as any)?.diversity?.raw_shares?.age as
          | { under_18?: number; age_18_64?: number; age_65_plus?: number }
          | undefined
        if (!age || typeof age.under_18 !== 'number') return null
        // Largest-remainder rounding so the three whole-number shares always add to 100.
        const raw = [age.under_18, age.age_18_64, age.age_65_plus].map((v) => (typeof v === 'number' ? v : 0))
        const total = raw.reduce((a, b) => a + b, 0)
        const scaled = total > 0 ? raw.map((v) => (v / total) * 100) : raw
        const floors = scaled.map(Math.floor)
        let left = 100 - floors.reduce((a, b) => a + b, 0)
        const order = scaled.map((v, i) => [v - Math.floor(v), i] as const).sort((a, b) => b[0] - a[0])
        for (const [, i] of order) { if (left <= 0) break; floors[i] += 1; left -= 1 }
        const rows: Array<[string, number | undefined]> = [
          ['Under 18', floors[0]],
          ['18 to 64', floors[1]],
          ['65 and over', floors[2]],
        ]
        return (
          <section className="mb-8" aria-label="Who lives here">
            <h2 className="mb-1 text-lg font-bold text-[var(--hf-text-primary)]">Who lives here</h2>
            <p className="mb-3 text-xs leading-relaxed text-[var(--hf-text-tertiary)]">
              Age mix of residents (Census ACS 2022). A description, not a score, and not counted in the total.
            </p>
            <div className="grid grid-cols-3 gap-3">
              {rows.map(([label, v]) => (
                <div key={label} className="rounded-2xl border border-[var(--hf-border)] bg-[var(--hf-card-bg)] p-3 text-center">
                  <div className="text-xl font-bold text-[var(--hf-text-primary)]">{typeof v === 'number' ? `${v}%` : 'n/a'}</div>
                  <div className="text-xs text-[var(--hf-text-tertiary)]">{label}</div>
                </div>
              ))}
            </div>
          </section>
        )
      })()}

      <NeighborhoodPersonal score={score} workCommute={work_commute} />

      {/* CTAs */}
      <section className="flex flex-col gap-2 sm:flex-row" aria-label="Next steps">
        <Link
          href="/quiz"
          className="flex-1 rounded-xl py-3 text-center text-sm font-bold text-white"
          style={{ background: 'var(--hf-primary-gradient)' }}
        >
          Take the quiz →
        </Link>
        <Link
          href={`/catalog?mode=twin&key=${twinKey}`}
          className="flex-1 rounded-xl border border-[var(--hf-border)] bg-[var(--hf-card-bg)] py-3 text-center text-sm font-bold text-[var(--hf-text-primary)]"
        >
          Find its twin →
        </Link>
        <Link
          href="/catalog"
          className="flex-1 rounded-xl border border-[var(--hf-border)] bg-[var(--hf-card-bg)] py-3 text-center text-sm font-bold text-[var(--hf-text-primary)]"
        >
          Browse all →
        </Link>
      </section>
    </main>
  )
}

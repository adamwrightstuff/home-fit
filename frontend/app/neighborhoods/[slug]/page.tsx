import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import {
  findNeighborhoodBySlug,
  getAllNeighborhoodSlugs,
  type NeighborhoodEntry,
} from '@/lib/catalogServer'
import { CATALOG_METRO_META } from '@/lib/catalogMetros'
import NeighborhoodBreakdown from '@/components/NeighborhoodBreakdown'

export const dynamicParams = false

const SITE_URL = 'https://www.trovamo.co'

export async function generateStaticParams() {
  return getAllNeighborhoodSlugs().map((slug) => ({ slug }))
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
  return `${catalog.name} scores${total != null ? ` ${total}` : ''} for livability across Trovamo's 13 pillars: schools, safety, transit, nature, and more.`
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

export default async function NeighborhoodPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  const entry = findNeighborhoodBySlug(slug)
  if (!entry) notFound()

  const { catalog, score, metro } = entry
  const metroLabel = CATALOG_METRO_META[metro]?.label ?? metro.toUpperCase()
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

      <NeighborhoodBreakdown
        score={score}
        locationLabel={`${catalog.name}, ${catalog.county_borough ?? ''} ${catalog.state_abbr ?? ''}`.replace(/\s+/g, ' ').trim()}
        twinHref={`/catalog?mode=twin&key=${twinKey}`}
      />
    </main>
  )
}

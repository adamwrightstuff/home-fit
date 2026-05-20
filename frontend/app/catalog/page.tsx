import { Suspense } from 'react'
import CatalogPageClient from './catalog-page-client'

export const metadata = {
  title: 'Explore neighborhoods — Trovamo',
  description: 'Browse and compare neighborhoods by livability score across 13 pillars.',
}

export default function CatalogPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[50dvh] items-center justify-center text-sm text-[var(--hf-text-secondary)]">
          Loading catalog…
        </div>
      }
    >
      <CatalogPageClient initialMetroFilter="all" />
    </Suspense>
  )
}

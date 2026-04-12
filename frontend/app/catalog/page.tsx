import { Suspense } from 'react'
import CatalogPageClient from './catalog-page-client'

export const metadata = {
  title: 'Catalog · HomeFit',
  description: 'Explore neighborhood scores and find metro twins on the map.',
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

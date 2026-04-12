import { Suspense } from 'react'
import CatalogPageClient from '../catalog-page-client'

export const metadata = {
  title: 'LA metro catalog · HomeFit',
  description: 'Explore LA metro neighborhood scores and twins.',
}

export default function LaCatalogPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[50dvh] items-center justify-center text-sm text-[var(--hf-text-secondary)]">
          Loading catalog…
        </div>
      }
    >
      <CatalogPageClient initialMetroFilter="la" />
    </Suspense>
  )
}

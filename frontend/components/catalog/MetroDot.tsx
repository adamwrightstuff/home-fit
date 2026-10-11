'use client'

import { CATALOG_METRO_META, type CatalogMetro } from '@/lib/catalogMetros'

export default function MetroDot({ metro }: { metro: CatalogMetro }) {
  return (
    <span
      className="inline-block h-2 w-2 shrink-0 rounded-full"
      style={{ background: CATALOG_METRO_META[metro].color }}
      title={CATALOG_METRO_META[metro].label}
      aria-hidden
    />
  )
}
